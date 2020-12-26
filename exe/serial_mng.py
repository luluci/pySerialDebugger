from math import trunc
from typing import Union, List
import serial
from serial.tools import list_ports, list_ports_common
from multiprocessing import Value
import queue
import time

class serial_manager:
	
	def __init__(self) -> None:
		self._serial: serial.Serial = None
		self._is_open: bool = False
		self._write_buf: bytes = None

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
			self._serial = serial.Serial(port, bps, _bs, _parity, _sb)
			self._is_open = True
			return True
		except:
			print("SerialPort open failed.")
			self._serial = None
			self._is_open = False
			return False

	def close(self) -> None:
		if self._is_open:
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

	def autoresp_build(self, autoresp_data: List[List[any]]) -> None:
		"""
		受信データ解析テーブルを構築
		初回のみ実施。ツール起動後は応答データのみ更新できる。
		"""
		# Response Table
		self._autoresp_resp = {}
		for resp in autoresp_data:
			self._autoresp_resp[resp[0]] = resp[2]
		# Analyze Table
		self._autoresp_rcv = self.autoresp_node()
		for resp in autoresp_data:
			node_ref = self._autoresp_rcv
			# bytesを辞書に登録
			for byte in resp[1]:
				if byte not in node_ref.next:
					node_ref.next[byte] = self.autoresp_node()
				node_ref = node_ref.next[byte]
			# 末端ノードに応答データをセット
			node_ref.is_tail = True
			node_ref.resp = self._autoresp_resp[resp[0]]



	def autoresp_update(self, autoresp_data: List[List[any]]) -> None:
		"""
		応答データ更新
		"""
		# Response Table
		for resp in autoresp_data:
			self._autoresp_resp[resp[0]] = resp[2]

	def connect(self, exit_flag: queue.Queue, recv_data: queue.Queue, resp_data: queue.Queue) -> None:
		"""
		Serial open and communicate.
		無限ループで通信を続けるのでスレッド化して実施する。
		スレッド終了後は
		"""
		"""
		# init
		self._serial.open()
		self._serial.reset_input_buffer()
		self._autoresp_rcv_pos = self._autoresp_rcv
		# listening
		while not exit_flag.empty():
			recv = self._serial.read(1)
			trans_req = self._recv_analyze(recv, recv_data)
			if trans_req:
				if self._serial.out_waiting > 0:
					self._serial.write(self._write_buf)
					self._serial.flush()
		"""
		count = 0
		try:
			while exit_flag.empty():
				recv_data.put(bytes.fromhex('AA'), block=True, timeout=1)
				recv_data.put(bytes.fromhex('BB'), block=True, timeout=1)
				resp_data.put(bytes.fromhex('FFFFFFEE'), block=True, timeout=1)
				count += 1
				if count > 10:
					count = 0
					recv_data.put(True, block=True, timeout=1)
				#print("Run: connect()")
				time.sleep(1)
			print("Exit: connect()")
		except:
			import traceback
			traceback.print_exc()

	def _thread_msg_data(self):
		pass

	def _thread_msg_next(self):
		pass

	def _recv_analyze(self, data: bytes, recv_data: queue.Queue) -> bool:
		"""
		受信解析を実施
		送信が必要であれば返り値で示す。
		"""
		resp_ok = False
		if data[0] in self._autoresp_rcv_pos.next:
			# 受信解析OK
			self._recv_analyze_ok(data, recv_data)
		else:
			# 受信解析NG
			self._recv_analyze_ng(data, recv_data)
		return resp_ok

	def _recv_analyze_ok(self, data: bytes, recv_data: queue.Queue) -> bool:
		# 受信解析OK
		resp_ok = False
		recv_data.put(data)
		frame_end = False
		# 次状態へ
		self._autoresp_rcv_pos = self._autoresp_rcv_pos.next[data[0]]
		# 末尾チェック
		if self._autoresp_rcv_pos.is_tail:
				self._write_buf = self._autoresp_rcv_pos.resp
				resp_ok = True
				frame_end = True
		# 遷移先が空なら先頭へ戻る
		if not self._autoresp_rcv_pos.next:
			self._autoresp_rcv_pos = self._autoresp_rcv
			frame_end = True
		if frame_end:
			recv_data.put(True)
		return resp_ok

	def _recv_analyze_ng(self, data: bytes, recv_data: queue.Queue) -> bool:
		# 受信解析NG
		resp_ok = False
		recv_data.put(True)
		recv_data.put(data)
		# 先頭へ戻る
		self._autoresp_rcv_pos = self._autoresp_rcv
		# 先頭からマッチするかチェック
		if data[0] in self._autoresp_rcv_pos.next:
			# 受信解析OK
			resp_ok = self._recv_analyze_ok(data)
		return resp_ok
