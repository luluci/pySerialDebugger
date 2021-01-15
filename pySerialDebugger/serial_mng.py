from math import trunc
from typing import Union, List
import serial
from serial.tools import list_ports, list_ports_common
from multiprocessing import Value
import queue
import time
import enum

DEBUG = True

class ThreadNotify(enum.Enum):
	"""
	スレッド間通信メッセージ
	"""
	# GUIへの通知
	PUSH_RX_BYTE = enum.auto()				# 受信データをバッファに追加
	PUSH_RX_BYTE_AND_COMMIT = enum.auto()	# 受信データをバッファに追加して、バッファ出力(正常異常問わず解析終了した)
	COMMIT_AND_PUSH_RX_BYTE = enum.auto()	# 既存バッファ出力後、受信データをバッファに追加
	COMMIT_TX_BYTES = enum.auto()			# 自動応答データを出力
	DISCONNECTED = enum.auto()				# シリアル切断
	# Serialへの通知
	TX_BYTES = enum.auto()					# シリアル送信(手動)
	AUTORESP_UPDATE = enum.auto()			# 自動応答データ更新
	EXIT_TASK = enum.auto()					# シリアルタスク終了

class serial_manager:
	
	def __init__(self) -> None:
		self._serial: serial.Serial = None
		self._is_open: bool = False
		self._write_buf: bytes = None
		# フレーム受信中に手動送信することを防ぐ
		# 前回受信から特定時間経過するまで手動送信しない
		self._send_tx_delay: int = 0
		# Response Table
		self._autoresp_resp = {}
		# Analyze Table
		self._autoresp_rcv = self.autoresp_node()

	def __del__(self) -> None:
		self.close()

	def open(self, port:str, bps:int, bytesize:int, parity:str, stopbit:int) -> bool:
		# Check:
		# port
		# null
		# bps
		# null
		# bytesize
		bytesize_tbl = {
			5: serial.FIVEBITS,
			6: serial.SIXBITS,
			7: serial.SEVENBITS,
			8: serial.EIGHTBITS,
		}
		if bytesize in bytesize_tbl:
			_bs = bytesize_tbl[bytesize]
		else:
			return False
		# parity
		parity_tbl = {
			"None": serial.PARITY_NONE,
			"EVEN": serial.PARITY_EVEN,
			"ODD": serial.PARITY_ODD,
			"MARK": serial.PARITY_MARK,
			"SPACE": serial.PARITY_SPACE,
		}
		if parity in parity_tbl:
			_parity = parity_tbl[parity]
		else:
			return False
		# stopbit
		stopbit_tbl = {
			1: serial.STOPBITS_ONE,
			1.5: serial.STOPBITS_ONE_POINT_FIVE,
			2: serial.STOPBITS_TWO,
		}
		if stopbit in stopbit_tbl:
			_sb = stopbit_tbl[stopbit]
		else:
			return False
		# Serial Open
		try:
			self._serial = serial.Serial(port, bps, _bs, _parity, _sb, 0)
			self._is_open = True
			return True
		except:
			print("SerialPort open failed.")
			self._serial = None
			self._is_open = False
			return False

	def close(self) -> None:
		if self._serial is not None:
			if self._serial.is_open:
				print("SerialPort closed.")
				self._serial.close()
		self._is_open = False

	def is_open(self) -> bool:
		return self._is_open

	def get_com_list(self) -> List[list_ports_common.ListPortInfo]:
		return list_ports.comports()

	class autoresp_node:
		def __init__(self):
			self.is_tail = False
			self.next = {}
			self.resp = None
			self.name = ""

	def autoresp_build(self, name: str, rx_bytes: bytes, tx_bytes: bytes) -> None:
		"""
		受信データ解析テーブルを構築
		初回のみ実施。ツール起動後は応答データのみ更新できる。
		"""
		node_ref = self._autoresp_rcv
		# bytesを辞書に登録
		for byte in rx_bytes:
			if byte not in node_ref.next:
				node_ref.next[byte] = self.autoresp_node()
			node_ref = node_ref.next[byte]
		# 末端ノードに応答データをセット
		node_ref.is_tail = True
		node_ref.name = name
		node_ref.resp = tx_bytes
		self._autoresp_resp[name] = node_ref

	def autoresp_update(self, name:str, tx_bytes:bytes) -> None:
		"""
		応答データ更新
		"""
		self._autoresp_resp[name].resp = tx_bytes

	def sendopt_txdelay_update(self, time: int) -> None:
		"""
		@param time マイクロ病秒 
		"""
		# ナノ秒に直しておく
		self._send_tx_delay = time * 1000

	def connect(self, recv_notify: queue.Queue, send_notify: queue.Queue, exit: queue.Queue) -> None:
		"""
		Serial open and communicate.
		無限ループで通信を続けるのでスレッド化して実施する。
		スレッド終了後は
		"""
		# init
		timeout = None
		self._autoresp_rcv_pos = self._autoresp_rcv
		self._time_stamp: int = 0

		if not DEBUG:
			# シリアルポートオープン
			if not self._serial.is_open:
				try:
					self._serial.open()
				except:
					import traceback
					traceback.print_exc()
					# 処理を終了することを通知
					notify_msg = [ThreadNotify.DISCONNECTED, None, None, None]
					send_notify.put(notify_msg, block=True, timeout=timeout)
					print("Cannot open COM port!")
					return
			# 念のためシリアル通信受信バッファを空にする
			self._serial.reset_input_buffer()
		else:
			self._debug_serial_read_init()
		# listening
		while exit.empty():
			if not DEBUG:
				# シリアル通信バッファチェック
				recv = self._serial.read(1)
			else:
				recv = self._debug_serial_read(1)
			# データを受信した場合
			if len(recv) > 0:
				# 受信時の現在時間取得
				self._time_stamp = time.perf_counter_ns()
				# 受信解析実行
				trans_req, frame_name = self._recv_analyze(recv, send_notify)
				if (trans_req) and (len(self._write_buf) > 0):
					#if self._serial.out_waiting > 0:
					self._serial.write(self._write_buf)
					self._serial.flush()
					notify_msg = [ThreadNotify.COMMIT_TX_BYTES, self._write_buf, frame_name, self._time_stamp]
					send_notify.put(notify_msg, block=True, timeout=timeout)
			# GUIからの通知チェック
			if not recv_notify.empty():
				curr_timestamp = time.perf_counter_ns()
				if (curr_timestamp - self._time_stamp) >= self._send_tx_delay:
					msg, data, name = recv_notify.get_nowait()
					if msg == ThreadNotify.TX_BYTES:
						self._serial.write(data)
						self._serial.flush()
						notify_msg = [ThreadNotify.COMMIT_TX_BYTES, data, name, self._time_stamp]
						send_notify.put(notify_msg, block=True, timeout=timeout)
					if msg == ThreadNotify.AUTORESP_UPDATE:
						data()
					if msg == ThreadNotify.EXIT_TASK:
						break


		# シリアル通信切断
		self.close()
		# queueを空にしておく
		while not exit.empty():
			exit.get_nowait()
		# 処理を終了することを通知
		notify_msg = [ThreadNotify.DISCONNECTED, None, None, None]
		send_notify.put(notify_msg, block=True, timeout=timeout)
		print("Exit: connect()")

	def _debug_serial_read_init(self) -> None:
		self._debug_buff = bytes.fromhex("ABCD0102898989ABCDEF01028989")
		self._debug_buff_pos = 0
		self._debug_buff_len = len(bytes.fromhex("ABCD0102898989ABCDEF01028989"))
		self._debug_buff_recv_size = 20

	def _debug_serial_read(self, size:int) -> bytes:
		result = None
		# recv
		if self._debug_buff_pos < self._debug_buff_len:
			result = self._debug_buff[self._debug_buff_pos].to_bytes(1, "little")
		else:
			result = b''
		# pos
		self._debug_buff_pos += 1
		if self._debug_buff_pos >= self._debug_buff_recv_size:
			self._debug_buff_pos = 0
		#
		time.sleep(1)
		return result

	def _thread_msg_data(self):
		pass

	def _thread_msg_next(self):
		pass

	def _recv_analyze(self, data: bytes, notify: queue.Queue):
		"""
		受信解析を実施
		送信が必要であれば返り値で示す。
		queueへの通知：[今回取得バイト, ログ出力要求, 詳細]
		"""
		resp_ok = False
		frame_name = ""
		timeout = None
		notify_msg = []
		if data[0] in self._autoresp_rcv_pos.next:
			# 受信解析OK
			resp_ok, frame_end, frame_name = self._recv_analyze_ok(data)
			# OK + resp_ok=True  + frame_end=any   -> 自動応答マッチ
			# OK + resp_ok=False + frame_end=True  -> 自動応答解析継続中だが、解析テーブルの末尾に到達しているので解析終了
			# OK + resp_ok=False + frame_end=False -> 自動応答解析継続中
			if resp_ok:
				notify_msg = [ThreadNotify.PUSH_RX_BYTE_AND_COMMIT, data, frame_name, self._time_stamp]
			else:
				if frame_end:
					notify_msg = [ThreadNotify.PUSH_RX_BYTE_AND_COMMIT, data, frame_name, self._time_stamp]
				else:
					notify_msg = [ThreadNotify.PUSH_RX_BYTE, data, frame_name, self._time_stamp]
		else:
			# 受信解析NG
			resp_ok, frame_end, frame_name = self._recv_analyze_ng(data)
			# NG + resp_ok=True  -> これまでの解析は失敗＋次の解析開始
			# NG + resp_ok=False -> これまでの解析は失敗＋次回解析にもマッチしない
			if resp_ok:
				# 既存データはノイズとしてアウトプット
				# 今回データは現時点でOKなのでアウトプットしない
				notify_msg = [ThreadNotify.COMMIT_AND_PUSH_RX_BYTE, data, frame_name, self._time_stamp]
			else:
				# 既存データ＋今回データはノイズとしてアウトプット
				notify_msg = [ThreadNotify.PUSH_RX_BYTE_AND_COMMIT, data, frame_name, self._time_stamp]
		# 通知を実施
		notify.put(notify_msg, block=True, timeout=timeout)
		return [resp_ok,frame_name]

	def _recv_analyze_ok(self, data: bytes):
		# 受信解析OK
		resp_ok = False
		frame_end = False
		frame_name = ""
		# 次状態へ
		self._autoresp_rcv_pos = self._autoresp_rcv_pos.next[data[0]]
		# 末尾チェック
		if self._autoresp_rcv_pos.is_tail:
			self._write_buf = self._autoresp_rcv_pos.resp
			resp_ok = True
			frame_end = True
			frame_name = self._autoresp_rcv_pos.name
		# 遷移先が空なら先頭へ戻る
		if not self._autoresp_rcv_pos.next:
			self._autoresp_rcv_pos = self._autoresp_rcv
			frame_end = True
		return [resp_ok, frame_end, frame_name]

	def _recv_analyze_ng(self, data: bytes):
		# 受信解析NG
		resp_ok = False
		frame_end = False
		frame_name = ""
		# 先頭へ戻る
		self._autoresp_rcv_pos = self._autoresp_rcv
		# 先頭からマッチするかチェック
		if data[0] in self._autoresp_rcv_pos.next:
			# 受信解析OK
			resp_ok, frame_end, frame_name = self._recv_analyze_ok(data)
		return [resp_ok, frame_end, frame_name]
