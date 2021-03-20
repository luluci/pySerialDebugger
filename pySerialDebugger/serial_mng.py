from math import trunc
from typing import Union, List
import serial
from serial.tools import list_ports, list_ports_common
from multiprocessing import Value
import queue
import time
import enum

from .autoresp import autoresp_data, autoresp_list, autoresp_mng
from .autosend import autosend_data, autosend_mng, autosend_node, autosend_list, autosend_result
from . import thread



DEBUG = True

class ThreadNotify(enum.Enum):
	"""
	スレッド間通信メッセージ
	"""
	# GUIへの通知
	COMMIT_RX = enum.auto()					# 受信バッファ出力
	PUSH_RX = enum.auto()					# 受信データをバッファに追加
	COMMIT_TX = enum.auto()					# 自動応答データを出力
	DISCONNECTED = enum.auto()				# シリアル切断
	AUTORESP_UPDATE_FIN = enum.auto()		# 自動応答データ更新完了
	# Serialへの通知
	TX_BYTES = enum.auto()					# シリアル送信(手動)
	AUTORESP_UPDATE = enum.auto()			# 自動応答データ更新
	EXIT_TASK = enum.auto()					# シリアルタスク終了



class serial_manager:
	
	def __init__(self) -> None:
		self._serial: serial.Serial = None
		self._is_open: bool = False
		# フレーム受信中に手動送信することを防ぐ
		# 前回受信から特定時間経過するまで手動送信しない
		self._send_tx_delay: int = 0
		# autoresp管理
		self._autoresp_mng: autoresp_mng = None
		# autosend管理
		self._autosend_mng: autosend_mng = None


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

	def autoresp(self, mng: autoresp_mng):
		# 自動応答マネージャを参照登録
		self._autoresp_mng = mng

	def autosend(self, mng: autosend_mng):
		# 自動応答マネージャを参照登録
		self._autosend_mng = mng
		self._autosend_mng.set_send_cb(self.cb_autosend)

	def cb_autosend(self, data: bytes):
		"""
		自動送信用コールバック関数
		"""
		if len(data) > 0:
			#if self._serial.out_waiting > 0:
			self._serial.write(data)
			self._serial.flush()

	def sendopt_txdelay_update(self, time: int) -> None:
		"""
		@param time マイクロ病秒 
		"""
		# ナノ秒に直しておく
		self._send_tx_delay = time * 1000

	def connect(self, recv_notify: queue.Queue, send_notify: queue.Queue) -> None:
		"""
		Serial open and communicate.
		無限ループで通信を続けるのでスレッド化して実施する。
		スレッド終了後は
		"""
		# init
		timeout = None
		self._time_stamp: int = 0
		self._time_stamp_rx: int = 0
		self._time_stamp_rx_prev: int = 0
		self._recv_analyze_result = False

		# 自動応答初期化
		self._autoresp_mng.recv_analyze_init()
		as_result = autosend_result()

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
		while not thread.messenger.has_exit_serial():
			if not DEBUG:
				# シリアル通信バッファチェック
				recv = self._serial.read(1)
			else:
				recv = self._debug_serial_read(1)
				#recv = b''
			# 受信時の現在時間取得
			self._time_stamp = time.perf_counter_ns()
			# データを受信した場合
			if len(recv) > 0:
				# 受信時の現在時間取得
				self._time_stamp_rx = self._time_stamp
				# 受信解析実行
				result = self._autoresp_mng.recv_analyze(recv[0])
				# 自動送信実行
				# 受信解析結果から送信要求があればこの中で実施される
				as_result = self._autosend_mng.run(0, self._time_stamp_rx)
				# 解析結果処理
				# GUI通知を実行
				if result.prev_buff_commit():
					notify_msg = [ThreadNotify.COMMIT_RX, None, "", self._time_stamp_rx_prev]
					send_notify.put(notify_msg, block=True, timeout=timeout)
				if result.new_data_push():
					notify_msg = [ThreadNotify.PUSH_RX, recv, result.id, self._time_stamp_rx]
					send_notify.put(notify_msg, block=True, timeout=timeout)
				if result.buff_commit():
					notify_msg = [ThreadNotify.COMMIT_RX, None, result.id, self._time_stamp_rx]
					send_notify.put(notify_msg, block=True, timeout=timeout)
				if as_result.is_send():
					# 自動応答送信データが有効なときだけ送信実行
					data = as_result.send_ref
					if data.size > 0:
						notify_msg = [ThreadNotify.COMMIT_TX, data.data_bytes, data.id, self._time_stamp_rx]
						send_notify.put(notify_msg, block=True, timeout=timeout)
				# 前回受信時間
				self._time_stamp_rx_prev = self._time_stamp_rx
			else:
				# 自動送信実行
				# 受信解析結果から送信要求があればこの中で実施される
				as_result = self._autosend_mng.run(0, self._time_stamp)
				if as_result.is_send():
					# 自動応答送信データが有効なときだけ送信実行
					data = as_result.send_ref
					if data.size > 0:
						notify_msg = [ThreadNotify.COMMIT_TX, data.data_bytes, data.id, self._time_stamp]
						send_notify.put(notify_msg, block=True, timeout=timeout)
			# GUIからの通知チェック
			if thread.messenger.has_notify_serial():
				# 前回シリアル受信から一定時間内は受信中とみなし送信を抑制する
				# この待機時間はGUIから設定する
				curr_timestamp = time.perf_counter_ns()
				if (curr_timestamp - self._time_stamp_rx) >= self._send_tx_delay:
					msg = thread.messenger.get_notify_serial()
					if msg.notify == thread.ThreadNotify.AUTORESP_UPDATE:
						# コールバック関数で更新を実施
						msg.cb()
						# 自動応答データ設定更新完了を通知
						thread.messenger.notify_hdlr_autoresp_updated()
			if not recv_notify.empty():
				# 前回シリアル受信から一定時間内は受信中とみなし送信を抑制する
				# この待機時間はGUIから設定する
				curr_timestamp = time.perf_counter_ns()
				if (curr_timestamp - self._time_stamp_rx) >= self._send_tx_delay:
					# 通知をdequeue
					msg, data, name = recv_notify.get_nowait()
					if msg == ThreadNotify.TX_BYTES:
						# 手動送信
						self._serial.write(data)
						self._serial.flush()
						notify_msg = [ThreadNotify.COMMIT_TX, data, name, curr_timestamp]
						send_notify.put(notify_msg, block=True, timeout=timeout)
					#if msg == ThreadNotify.AUTORESP_UPDATE:
					#	# 自動応答データ更新
					#	data()
					#	# 自動応答更新完了を通知
					#	notify_msg = [ThreadNotify.AUTORESP_UPDATE_FIN, None, None, None]
					#	send_notify.put(notify_msg, block=True, timeout=timeout)
					#if msg == ThreadNotify.EXIT_TASK:
					#	# 
					#	break

		# 自動送信停止
		# 本スレッドが稼働しなければ自動送信も動かないので、
		# とりあえず動作を止めずに終了する。
		# self._autosend_mng.stop()
		# シリアル通信切断
		self.close()
		# exit通知クリア
		thread.messenger.clear_exit_serial()
		# 処理を終了することを通知
		notify_msg = [ThreadNotify.DISCONNECTED, None, None, None]
		send_notify.put(notify_msg, block=True, timeout=timeout)
		print("Exit: connect()")

	def _debug_serial_read_init(self) -> None:
		self._debug_data = [
			bytes.fromhex("00AA0101"),
			200*1000*1000,
			bytes.fromhex("00BB0101"),
			200*1000*1000,
			bytes.fromhex("00AA0202"),
			200*1000*1000,
			bytes.fromhex("00BB0202"),
			200*1000*1000,
			bytes.fromhex("00FF02"),
			200*1000*1000,
		]
		self._debug_data_pos = 0
		self._debug_data_len = len(self._debug_data)
		# bytes用データ
		self._debug_bytes_pos = 0
		self._debug_bytes_delay = 5 * 1000
		# wait用データ
		self._debug_wait_begin = 0
		# timestamp
		self._debug_timestamp = 0
		self._debug_timestamp_prev = 0

	def _debug_serial_read(self, size:int) -> bytes:
		# timestamp
		self._debug_timestamp = time.perf_counter_ns()
		timestamp_diff = self._debug_timestamp - self._debug_timestamp_prev
		result = b''
		# debug data check
		data = self._debug_data[self._debug_data_pos]
		if isinstance(data, bytes):
			# bytesのときは疑似シリアル受信
			# 受信ディレイ待機
			if timestamp_diff > self._debug_bytes_delay:
				# 受信データ作成
				result = data[self._debug_bytes_pos].to_bytes(1, 'little')
				# 受信データ数チェック
				self._debug_bytes_pos += 1
				if self._debug_bytes_pos >= len(data):
					self._debug_bytes_pos = 0
					self._debug_data_pos += 1
					if self._debug_data_pos >= self._debug_data_len:
						self._debug_data_pos = 0
					self._debug_wait_begin = self._debug_timestamp
		elif isinstance(data, int):
			waittime = self._debug_timestamp - self._debug_wait_begin
			# intのときはwait
			if waittime > data:
				# wait経過で次へ
				self._debug_bytes_pos = 0
				self._debug_data_pos += 1
				if self._debug_data_pos >= self._debug_data_len:
					self._debug_data_pos = 0
				self._debug_wait_begin = self._debug_timestamp

		self._debug_timestamp_prev = self._debug_timestamp
		return result

	def _thread_msg_data(self):
		pass

	def _thread_msg_next(self):
		pass
