import time
import concurrent.futures
from typing import Any, Union, List, Type, Dict, Tuple
import PySimpleGUI as sg
from PySimpleGUI.PySimpleGUI import Input
from . import serial_mng
from multiprocessing import Array, Value
import queue
import re
import enum

class gui_input:
	"""

	"""
	# inputノードタイプ
	INPUT, SELECT, FIX = range(0,3)
	
	def __init__(self, type: int, size: int, name: str, value: int, values: Dict[str,int], endian:str) -> None:
		# inputノードタイプを設定
		if (type is None) or (size is None):
			raise Exception("gui_input node require [type, size]")
		self.type = type
		# データサイズ(bit長)
		self.size = size
		# エンディアン
		if endian is None:
			endian = 'little'
		self.endian = endian
		# タイプごとに処理
		if type == gui_input.INPUT:
			self._init_input(name, value)
		if type == gui_input.SELECT:
			self._init_select(name, values)
		if type == gui_input.FIX:
			self._init_input(name, value)

	def _init_input(self, name: str, value: int):
		if (name is None) or (value is None):
			raise Exception("gui_input: INPUT node require [name, value]")
		self.name = name
		self.value = value

	def _init_select(self, name: str, values: Dict[str, int]):
		if (name is None) or (values is None):
			raise Exception("gui_input: SELECT node require [name, values]")
		self.name = name
		self.values = values
		# 初期値設定
		for val in values.values():
			self.value = val
			break

	@classmethod
	def input(cls, hex: str):
		return gui_input(gui_input.INPUT, 8, "kari", int(hex, 16), None, None)

	@classmethod
	def input_16(cls, hex: str):
		return gui_input(gui_input.INPUT, 16, "kari", int(hex, 16), None, "little")

	@classmethod
	def input_16be(cls, hex: str):
		return gui_input(gui_input.INPUT, 16, "kari", int(hex, 16), None, "big")

	@classmethod
	def select(cls, values: Dict[str, int]):
		return gui_input(gui_input.SELECT, 8, "kari", None, values, None)

	@classmethod
	def select_16(cls, values: Dict[str, int]):
		return gui_input(gui_input.SELECT, 16, "kari", None, values, None)

	@classmethod
	def fix(cls, hex: str):
		return gui_input(gui_input.FIX, 8, "kari", int(hex, 16), None, None)

	def get_size(self) -> int:
		return int(self.size / 8)

	def get_value(self, gui_data: str) -> bytes:
		"""
		GUI設定値を値に直して返す
		"""
		# タイプごとに処理
		if self.type == gui_input.INPUT:
			return self.get_value_input(gui_data)
		if self.type == gui_input.SELECT:
			return self.get_value_select(gui_data)
		if self.type == gui_input.FIX:
			return self.get_value_input(gui_data)

	def get_value_input(self, gui_data: str) -> bytes:
		# size取得
		byte_size = self.get_size()
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		# 入力テキストをゼロ埋めで2桁にする
		data = gui_data.zfill(byte_size * 2)
		# 16進数文字列でなかったら 00 に強制置換
		if (hex_ptn.match(data) is None) or (len(data) > byte_size * 2):
			data = "00"
		self.value = int(data, 16)
		return self.value.to_bytes(byte_size, self.endian)

	def get_value_select(self, gui_data: str) -> bytes:
		# size取得
		byte_size = self.get_size()
		# keyが存在しなければ先頭データに強制置換
		if gui_data not in self.values:
			gui_data = list(self.values.keys())[0]
		self.value = self.values[gui_data]
		return self.values[gui_data].to_bytes(byte_size, self.endian)

	def set_value(self, tx_data: bytes, idx: int) -> None:
		# size取得
		byte_size = self.get_size()
		self.value = int.from_bytes(tx_data[idx:idx+byte_size], byteorder=self.endian, signed=False)

	def get_bytes(self) -> bytes:
		# タイプごとに処理
		if self.type == gui_input.INPUT:
			return self._get_bytes_input()
		if self.type == gui_input.SELECT:
			return self._get_bytes_select()
		if self.type == gui_input.FIX:
			return self._get_bytes_input()
		raise Exception("unknown node type detected!")

	def _get_bytes_input(self) -> bytes:
		# size取得
		byte_size = self.get_size()
		return self.value.to_bytes(byte_size, self.endian)

	def _get_bytes_select(self) -> bytes:
		# size取得
		byte_size = self.get_size()
		def_val = None
		for data in self.values:
			if def_val is None:
				def_val = self.values[data]
		return def_val.to_bytes(byte_size, self.endian)

	def get_gui(self, key, size, pad, font) -> Any:
		# タイプごとに処理
		if self.type == gui_input.INPUT:
			return self._get_gui_input(key, size, pad, font)
		if self.type == gui_input.SELECT:
			return self._get_gui_select(key, size, pad, font)
		if self.type == gui_input.FIX:
			return self._get_gui_fix(key, size, pad, font)
		raise Exception("unknown node type detected!")

	def _get_gui_input(self, key, size, pad, font):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		size_offset = 1 * (byte_size - 1)
		size = (size[0] * byte_size + size_offset, size[1])
		return sg.Input(format(self.value, gui_form), key=key, size=size, pad=pad, font=font, enable_events=False)

	def _get_gui_select(self, key, size, pad, font):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		list = []
		def_val = None
		size = (size[0]*byte_size-2, size[1])
		for data in self.values:
			if def_val is None:
				def_val = data
			list.append(data)
		return sg.Combo(list, default_value=def_val, key=key, size=size, pad=pad, font=font, auto_size_text=True, enable_events=False)

	def _get_gui_fix(self, key, size, pad, font):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		size = (size[0] * byte_size, size[1])
		return sg.Input(format(self.value, gui_form), key=key, size=size, pad=pad, font=font, enable_events=False, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())

	def get_gui_value(self) -> str:
		# タイプごとに処理
		if self.type == gui_input.INPUT:
			return self._get_gui_value_input()
		if self.type == gui_input.SELECT:
			return self._get_gui_value_select()
		if self.type == gui_input.FIX:
			return self._get_gui_value_input()
		raise Exception("unknown node type detected!")

	def _get_gui_value_input(self) -> str:
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		return format(self.value, gui_form)

	def _get_gui_value_select(self) -> str:
		def_val = None
		for key, value in self.values.items():
			if def_val is None:
				def_val = key
			if self.value == value:
				return key
		return def_val



class DataConf:
	"""
	GUI構築定義データ
	"""
	NAME = 0		# 定義名
	RX = 1			# 受信データ
	TX = 2			# 送信データ
	TX_SIZE = 3		# 送信データサイズ

class gui_manager:
	DISCONNECTED, DISCONNECTING, CONNECTED, CONNECTING = (1,2,3,4)
	
	def __init__(self) -> None:
		# Serial Info
		self._serial = serial_mng.serial_manager()
		# Window Info
		self._window: sg.Window = None
		self._header_font_family = 'BIZ UDゴシック'
		self._header_font = (self._header_font_family, 11)
		self._data_font_family = 'Consolas'
		self._gui_font = (self._data_font_family, 11)
		self._log_font = (self._data_font_family, 10)
		self._init_com()
		self._init_window()
		self._init_event()
		self._gui_conn_state = self.DISCONNECTED
		# sendオプション更新
		self._sendopt_update()

	def __del__(self) -> None:
		self.close()

	def _init_com(self):
		self._comport_list = []
		for com in self._serial.get_com_list():
			self._comport_list.append( com.device )
		if not self._comport_list:
		# if len(self._comport_list) == 0:
		# if self._comport_list == []:
			raise Exception("COM port not found.")
		self._bps_list = [2400, 9600]
		self._bytesize_list = [5, 6, 7, 8]
		self._parity_list = ["None", "EVEN", "ODD", "MARK", "SPACE"]
		self._stopbit_list = [1,1.5,2]

	def _init_window(self):
		sg.theme("Dark Blue 3")
		leyout_serial_connect = [
			sg.Text("   "),
			sg.Button("Connect", key="btn_connect", size=(15,1), enable_events=True),
		]
		layout_serial_status = [
			sg.Text("---", key="text_status", size=(50,1)),
		]
		# Define: Serial Setting View
		layout_serial_settings = [
			sg.Text("COM Port:"),
			sg.Combo(self._comport_list, key="cmb_port", default_value=self._comport_list[0], size=(7,1)),
			sg.Text(" "),
			sg.Text("Baudrate:"),
			sg.Combo(self._bps_list, key="cmb_baudrate", default_value=self._bps_list[0], size=(7, 1)),
			sg.Text(" "),
			sg.Text("ByteSize:"),
			sg.Combo(self._bytesize_list, key="cmb_byte_size", default_value=8, size=(7, 1)),
			sg.Text(" "),
			sg.Text("Parity:"),
			sg.Combo(self._parity_list, key="cmb_parity", default_value="EVEN", size=(7, 1)),
			sg.Text(" "),
			sg.Text("StopBit:"),
			sg.Combo(self._stopbit_list, key="cmb_stop_bit", default_value=1, size=(7, 1)),
		]
		# Define: AutoResponse View
		self._auto_response_init()
		layout_serial_auto_resp = [
			self._layout_autoresp_caption,
			self._layout_autoresp_head,
			*self._layout_autoresp_data
		]
		layout_serial_auto_resp_column = [
			[sg.Column(layout_serial_auto_resp, scrollable=True, vertical_scroll_only=False, size=(1450, 240))],
			[sg.Button("Update", key="btn_autoresp_update", size=(15, 1), enable_events=True)],
		]
		# Define: Send View
		self._send_init()
		layout_serial_send = [
			self._layout_send_caption,
			self._layout_send_head,
			*self._layout_send_data
		]
		layout_serial_send_option = [
			[
				sg.Text("", font=self._gui_font),
				sg.Input("", key="sendopt_tx_delay", size=(15, 1), font=self._log_font, tooltip="フレーム受信中の間に送信することを防ぐ"),
				sg.Text("マイクロ秒間受信が無ければ送信する", font=self._gui_font),
				sg.Button("Update", key="btn_sendopt_update", size=(15, 1), enable_events=True),
			],
		]
		layout_serial_send_column = [
			[sg.Column(layout_serial_send, scrollable=True, vertical_scroll_only=False, size=(1450, 240))],
			[sg.Frame("Send Option:", layout_serial_send_option)],
		]
		# Define: log View
		layout_serial_log_col = [
			[
				sg.Text("[HH:MM:SS.mmm.uuu][TxRx]", font=self._log_font),
				sg.Text("CommData", size=(52,1)),
				sg.Text("(Detail)")
			]
		]
		layout_serial_log_caption = [
			sg.Column(layout_serial_log_col, scrollable=False, size=(800, 30))
		]
		layout_serial_log_output = [
			sg.Output(size=(160, 10), echo_stdout_stderr=True, font=self._log_font)
		]
		layout_serial_log = [
			layout_serial_log_caption,
			layout_serial_log_output,
		]
		layout = [
			[*leyout_serial_connect, sg.Frame("Status:", [layout_serial_status])],
			[sg.Frame("Serial Settings:", [layout_serial_settings])],
			#[sg.Frame("Auto Response Settings:", layout_serial_auto_resp_column)],
			#[sg.Frame("Manual Send Settings:", layout_serial_send_column)],
			[sg.TabGroup([[
				sg.Tab('Auto Response Settings', layout_serial_auto_resp_column),
				sg.Tab('Manual Send Settings', layout_serial_send_column)
			]])],
			[sg.Frame("Log:", layout_serial_log)],
		]
		self._window = sg.Window("pySerialDebugger", layout, finalize=True)

	def _init_event(self) -> None:
		# clear events
		self._events = {
			# Exit
			None: self._hdl_exit,
			# Button: Connect
			"btn_connect": self._hdl_btn_connect,
			"btn_autoresp_update": self._hdl_btn_autoresp_update,
			# Button: Send
			"btn_send": self._hdl_btn_send,
			"btn_sendopt_update": self._hdl_btn_sendopt_update,
			# ButtonMenu:
			"resp": self._hdl_btnmenu,
			# Script Write Event
			"_swe_disconnected": self._hdl_swe_disconnected,
		}
		# event init
		self._hdl_btn_connect_init()

	def _hdl_exit(self, values):
		self.close()
		print("exit")

	def _hdl_btnmenu(self, values, row, col):
		val = values[("resp", row, col)]

	def _hdl_btn_connect_init(self):
		self._conn_btn_hdl = self._window["btn_connect"]
		self._conn_status_hdl = self._window["text_status"]

	def _hdl_btn_connect(self, values):
		#print("Button Pushed!")
		# 状態ごとに処理を実施
		if self._gui_conn_state == self.DISCONNECTED:
			# 通信開始処理を実施
			# 状況判定
			if self._future_serial is not None:
				# スレッドが稼働中
				print("切断済みのはずなのにスレッドが稼働中。バグでは？")
			# シリアル通信がオープンしていたら閉じる
			if self._serial.is_open():
				self._serial.close()
			# シリアル通信をオープン
			if self._serial_open():
				# オープンに成功したら
				# スレッドにて通信制御を開始
				self._future_serial = self._executer.submit(self._serial.connect, self._notify_to_serial, self._notify_from_serial, self._exit_flag_serial)
				# GUI更新
				self._conn_btn_hdl.Update(text="Disconnect")
				self._conn_status_hdl.Update(value=self._get_com_info())
				print("Port Open, and Comm Start: " + self._get_com_info())
				# 次状態へ
				self._gui_conn_state = self.CONNECTED
			else:
				# オープンに失敗したら
				# メッセージを出して終了
				print("Serial Open Failed!")

		elif self._gui_conn_state == self.CONNECTING:
			# 現状で接続中はない
			pass

		elif self._gui_conn_state == self.CONNECTED:
			# 通信切断処理を実施
			# 状況判定
			if self._future_serial is None:
				# スレッドが非稼働中
				print("接続済みのはずなのにスレッドが非稼働中。バグでは？")
			else:
				# スレッドに終了通知
				#self._notify_to_serial.put([serial_mng.ThreadNotify.EXIT_TASK, None, None])
				self._exit_flag_serial.put(True)
			# 切断中に移行
			self._gui_conn_state = self.DISCONNECTING
			# GUI操作
			self._conn_btn_hdl.Update(text="Disconnecting", disabled=True)
			self._conn_status_hdl.Update(value="Disconnecting...")
			# イベント周期で切断をポーリング
			# self._window.write_event_value("btn_connect", "")

		elif self._gui_conn_state == self.DISCONNECTING:
			# 切断完了判定を実施
			if not self._comm_hdle_notify.empty():
				# 切断通知あり
				# キューを空にしておく
				self._comm_hdle_notify.get_nowait()
				# 念のため切断
				self._serial_close()
				# スレッド解放
				self._future_serial = None
				# GUI操作
				self._conn_btn_hdl.Update(text="Connect", disabled=False)
				self._conn_status_hdl.Update(value="---")
				# 次状態へ
				self._gui_conn_state = self.DISCONNECTED
			else:
				# イベント周期で切断をポーリング
				# time.sleep(0.01)
				# self._window.write_event_value("btn_connect", "")
				pass

		else:
			print("ありえない状態。バグ")

	def _hdl_swe_disconnected(self, values):
		# 念のため切断
		self._serial_close()
		# スレッド解放
		self._future_serial = None
		# GUI操作
		self._conn_btn_hdl.Update(text="Connect", disabled=False)
		self._conn_status_hdl.Update(value="---")
		# 次状態へ
		self._gui_conn_state = self.DISCONNECTED

	def _hdl_btn_autoresp_update(self, values):
		self._auto_response_update()

	def _hdl_btn_send(self, values, row, col):
		self._req_send_bytes(row)

	def _hdl_btn_sendopt_update(self, values):
		self._sendopt_update()

	def exe(self):
		# スレッド管理
		self._future_comm_hdle = None
		self._future_serial = None
		# スレッド間通信用キュー
		self._exit_flag_serial = queue.Queue(10)
		self._notify_to_serial = queue.Queue(10)
		self._notify_from_serial = queue.Queue(10)
		self._exit_flag_comm_hdle = queue.Queue(10)
		self._comm_hdle_notify = queue.Queue(10)
		# (1) Windows イベントハンドラ
		# (2) シリアル通信
		# (3) シリアル通信->送受信->GUI
		# の3スレッドで処理を実施する
		self._executer = concurrent.futures.ThreadPoolExecutor(max_workers=3)
		self._future_comm_hdle = self._executer.submit(self.comm_hdle, self._exit_flag_comm_hdle, self._notify_from_serial, self._comm_hdle_notify)
		self.wnd_proc()
		self._executer.shutdown()

	def wnd_proc(self):
		while True:
			event, values = self._window.read()

			if event in self._events:
				self._events[event](values)
			if isinstance(event, tuple):
				t_ev, idx, col = event
				self._events[t_ev](values, idx, col)
			if event is None:
				# 各スレッドに終了通知
				#self._notify_to_serial.put([serial_mng.ThreadNotify.EXIT_TASK, None, None])
				self._exit_flag_serial.put(True)
				self._exit_flag_comm_hdle.put(True)
				# queueを空にしておく
				while not self._notify_from_serial.empty():
					self._notify_from_serial.get_nowait()
				break
		print("Exit: wnd_proc()")

	def comm_hdle(self, exit_flag: queue.Queue, serial_notify: queue.Queue, self_notify: queue.Queue):
		self.log_str = ""
		self.log_pos = 0
		try:
			while exit_flag.empty():
				if not serial_notify.empty():
					# queueからデータ取得
					notify, data, autoresp_name, timestamp = serial_notify.get_nowait()
					# 通知に応じて処理実施
					if notify == serial_mng.ThreadNotify.PUSH_RX_BYTE:
						# ログバッファに受信データを追加
						# ログ出力は実施しない
						self.log_str += data.hex().upper()
					elif notify == serial_mng.ThreadNotify.PUSH_RX_BYTE_AND_COMMIT:
						# ログバッファに受信データを追加
						self.log_str += data.hex().upper()
						# ログ出力
						self.comm_hdle_log_output("RX", self.log_str, autoresp_name, timestamp)
						# バッファクリア
						self.log_str = ""
					elif notify == serial_mng.ThreadNotify.COMMIT_AND_PUSH_RX_BYTE:
						# ログ出力
						self.comm_hdle_log_output("RX", self.log_str, autoresp_name, timestamp)
						# バッファクリア
						self.log_str = ""
						# ログバッファに受信データを追加
						self.log_str += data.hex().upper()
					elif notify == serial_mng.ThreadNotify.COMMIT_TX_BYTES:
						# 送信データをログ出力
						self.comm_hdle_log_output("TX", data.hex().upper(), autoresp_name, timestamp)
					elif notify == serial_mng.ThreadNotify.DISCONNECTED:
						# GUIスレッドに切断を通知
						# self_notify.put(True)
						# スレッドセーフらしい
						self._window.write_event_value("_swe_disconnected", "")
					else:
						pass
				#print("Run: serial_hdle()")
				time.sleep(0.0001)
			print("Exit: serial_hdle()")
		except:
			import traceback
			traceback.print_exc()

	def comm_hdle_log_output(self, rxtx:str, data:str, detail:str, timestamp:int):
		# タイムスタンプ整形
		ts_next, ts_ns = divmod(timestamp, 1000)	# nano sec
		ts_next, ts_us = divmod(ts_next, 1000)		# micro sec
		ts_next, ts_ms = divmod(ts_next, 1000)		# milli sec
		ts_next, ts_sec = divmod(ts_next, 60)		# sec
		ts_hour, ts_min = divmod(ts_next, 60)		# minute
		ts_str = "{0:02}:{1:02}:{2:02}.{3:03}.{4:03}".format(ts_hour, ts_min, ts_sec, ts_ms, ts_us)
		# ログ作成
		if detail == "":
			log_temp = "[{0}] [{1:2}]    {2:60}".format(ts_str, rxtx, data)
		else:
			log_temp = "[{0}] [{1:2}]    {2:60} ({3})".format(ts_str, rxtx, data, detail)
		print(log_temp)

	def close(self) -> None:
		if self._window:
			self._window.close()
		self._serial.close()

	def _serial_open(self) -> bool:
		result = self._serial.open(
			self._get_com_port(),
			self._get_com_baudrate(),
			self._get_com_bytesize(),
			self._get_com_parity(),
			self._get_com_stopbit()
		)
		return result

	def _serial_close(self) -> None:
		self._serial.close()

	def _get_com_port(self) -> str:
		return self._window["cmb_port"].Get()

	def _get_com_baudrate(self) -> int:
		return self._window["cmb_baudrate"].Get()

	def _get_com_bytesize(self) -> int:
		return self._window["cmb_byte_size"].Get()

	def _get_com_parity(self) -> str:
		return self._window["cmb_parity"].Get()

	def _get_com_stopbit(self) -> int:
		return self._window["cmb_stop_bit"].Get()

	def _get_com_info(self) -> str:
		result = ""
		result += "Port:[" + self._get_com_port() + "]"
		result += "  "
		result += "bps:[" + str(self._get_com_baudrate()) + "]"
		result += "  "
		result += "Size:[" + str(self._get_com_bytesize()) + "]"
		result += "  "
		result += "Parity:[" + self._get_com_parity() + "]"
		result += "  "
		result += "StopBit:[" + str(self._get_com_stopbit()) + "]"
		return result

	def _auto_response_init(self) -> None:
		"""
		_auto_response_settings の設定内容をGUI上に構築する。
		以降はGUI上で更新されたら解析情報に反映する。
		"""
		# 定義を読み込む
		self._auto_response_settings()
		# 定義解析
		self._auto_response_settings_construct()
		# GUIに落とし込む
		# 最大送信データ長を算出、ヘッダ構築に利用
		# TX_SIZEはconstructで更新済み
		# 固定ヘッダのName,RX分の2を最後に足す
		resp_len_max = 0
		for resp in self._autoresp_data:
			if resp[DataConf.TX_SIZE] > resp_len_max:
				resp_len_max = resp[DataConf.TX_SIZE]
		resp_len_max += 2
		# GUIパーツ定義
		self._font_name = (self._header_font_family, 10)
		self._font_rx = (self._data_font_family, 10)
		self._font_tx = (self._data_font_family, 9)
		self._size_name = (20, 1)
		self._size_rx = (20, 1)
		self._size_tx = (6, 1)
		self._pad_tx = ((0, 0), (0, 0))
		# Make Caption
		self._layout_autoresp_caption = []
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[0], size=self._size_name, font=self._font_name))
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[1], size=self._size_rx, font=self._font_name)) 
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[2], size=self._size_name, font=self._font_name)) 
		# Make Header
		# Name,Recvは固定とする
		# ヘッダ定義がデータ最大に足りなかったら穴埋めする
		head_max = len(self._autoresp_head)
		self._layout_autoresp_head = []
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[0], size=self._size_name, font=self._font_name))
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[1], size=self._size_rx, font=self._font_rx)) 
		head_suffix = ""
		if head_max < resp_len_max:
			head_suffix = self._autoresp_head[head_max-1]
			self._autoresp_head[head_max-1] = head_suffix + "[1]"
		self._layout_autoresp_head.extend([sg.Input(self._autoresp_head[i], size=self._size_tx, font=self._font_tx, disabled=True, pad=self._pad_tx, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(2, head_max)])
		if head_max < resp_len_max:
			self._layout_autoresp_head.extend( [sg.Input(head_suffix + "[" + str(i - head_max + 2) + "]", size=self._size_tx, font=self._font_tx, disabled=True, pad=self._pad_tx, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(head_max, resp_len_max)])
		# Make Values
		self._layout_autoresp_data = []
		for resp in self._autoresp_data:
			# GUI処理
			# Add empty list
			idx = len(self._layout_autoresp_data)
			parts = []
			# Add Name,Recv col
			parts.append(sg.Text(resp[DataConf.NAME], size=self._size_name, font=self._font_name))
			parts.append(sg.Text(resp[DataConf.RX].hex().upper(), size=self._size_rx, font=self._font_rx))
			# Add resp data col
			parts.extend(self._init_gui_tx("resp", idx, resp[DataConf.TX], resp[DataConf.TX_SIZE], self._autoresp_data_tx[idx]))
			# GUI更新
			self._layout_autoresp_data.append(parts)

	def _send_init(self) -> None:
		# 定義を読み込む
		self._send_settings()
		# 定義解析
		self._send_settings_construct()
		# 最大送信データ長を算出、ヘッダ構築に利用
		# TX_SIZEはconstructで更新済み
		# 固定ヘッダのName分の1を最後に足す
		send_col_num = 0
		for data in self._send_data:
			# send_data GUI 列数を算出
			if data[DataConf.TX_SIZE] > send_col_num:
				send_col_num = data[DataConf.TX_SIZE]
		send_col_num += 1
		# GUIパーツ定義
		font_btn_txt = (self._data_font_family, 11)
		font_btn = (self._data_font_family, 9)
		font_name = (self._header_font_family, 10)
		font_tx = (self._data_font_family, 9)
		size_btn_txt = (5, 1)
		size_btn = (5, 1)
		size_name = (20, 1)
		size_tx = (6, 1)
		# Make Caption
		self._layout_send_caption = []
		self._layout_send_caption.append(sg.Text("", size=size_btn_txt, font=font_btn_txt))
		self._layout_send_caption.append(sg.Text(self._send_caption[0], size=size_name, font=font_name))
		self._layout_send_caption.append(sg.Text(self._send_caption[1], size=size_name, font=font_name)) 
		# Make Header
		head_max = len(self._send_head)
		self._layout_send_head = []
		self._layout_send_head.append(sg.Text("", size=size_btn_txt, font=font_btn_txt))
		self._layout_send_head.append(sg.Text(self._send_head[0], size=size_name, font=font_name))
		# ヘッダ定義がデータ最大に足りなかったら穴埋めする
		head_suffix = ""
		if head_max < send_col_num:
			head_suffix = self._send_head[head_max-1]
			self._send_head[head_max-1] = head_suffix + "[1]"
		self._layout_send_head.extend([sg.Input(self._send_head[i], size=size_tx, font=font_tx, disabled=True, pad=self._pad_tx, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(1, head_max)])
		if head_max < send_col_num:
			self._layout_send_head.extend( [sg.Input(head_suffix + "[" + str(i - head_max + 2) + "]", size=size_tx, font=font_tx, disabled=True, pad=self._pad_tx, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(head_max, send_col_num)])
		# Make Values
		self._layout_send_data = []
		for idx, data in enumerate(self._send_data):
			# GUI処理
			# Add empty list
			idx = len(self._layout_send_data)
			parts = []
			# Add Button col
			parts.append(sg.Button("Send", size=size_btn, font=font_btn, key=("btn_send",idx, None)))
			# Add Name col
			parts.append(sg.Text(data[DataConf.NAME], size=size_name, font=font_name))
			# Add resp data col
			parts.extend(self._init_gui_tx("send", idx, data[DataConf.TX], data[DataConf.TX_SIZE], self._send_data_tx[idx]))
			# GUI更新
			self._layout_send_data.append(parts)

	def _init_gui_tx(self, key: str, idx: int, tx, size: int, tx_hex: bytes):
		if isinstance(tx, bytes):
			return self._init_gui_tx_bytes(key, idx, tx_hex, size)
		if isinstance(tx, List):
			return self._init_gui_tx_gui_list(key, idx, tx, size, tx_hex)

	def _init_gui_tx_bytes(self, key: str, idx: int, hex: bytes, size: int):
		parts = []
		# Add resp data col
		parts.extend([sg.Input(format(byte, "02X"), size=self._size_tx, font=self._font_tx, key=(key, idx, i), pad=self._pad_tx, enable_events=False) for i, byte in enumerate(hex)])
		# Add empty data col
		begin = len(hex)
		end = size
		parts.extend([sg.Input( "", size=self._size_tx, font=self._font_tx, key=(key, idx,i), pad=self._pad_tx, enable_events=False) for i in range(begin, end)])
		return parts

	def _init_gui_tx_gui_list(self, key: str, idx: int, txs: List[gui_input], size: int, tx_hex: bytes):
		parts = []
		# Add resp data col
		fix = gui_input.fix
		tx_len = len(txs)
		id = 0
		col = 0
		while col < size:
			if col < tx_len:
				parts.append(txs[id].get_gui((key, idx, id), self._size_tx, self._pad_tx, self._font_tx))
				col += txs[id].get_size()
			else:
				parts.append(fix(format(tx_hex[col], "02X")).get_gui((key, idx, id), self._size_tx, self._pad_tx, self._font_tx))
				col += 1
			id += 1
		return parts

	def _auto_response_settings_construct(self) -> None:
		# 実送信データHEXを別データとして保持する
		self._autoresp_data_tx = []
		for i, resp in enumerate(self._autoresp_data):
			### 送信データ長を算出
			# 送信データHEX長と送信データサイズを比較
			tx_len = self._calc_data_len(resp[DataConf.TX])
			resp_len = max(tx_len, resp[DataConf.TX_SIZE])
			# FCCを反映, FCC位置がデータ長よりも外側にあるとき
			if resp[4] >= resp_len:
				resp_len = resp[4] + 1
			# 定義データを更新
			resp[DataConf.TX_SIZE] = resp_len
			### 送信データHEXを構築
			tx_data = None
			if isinstance(resp[DataConf.TX], bytes):
				tx_data = resp[DataConf.TX]
			if isinstance(resp[DataConf.TX], List):
				tx_data = self._settings_construct_bytes(resp[DataConf.TX])
			self._autoresp_data_tx.append(tx_data)
			# FCC算出
			self._autoresp_data_tx[i] = self._update_fcc(self._autoresp_data_tx[i], resp[4], resp[5], resp[6])
			# FCC算出結果を送信データ定義に反映する。
			# FCC位置設定が送信データ定義内にあった場合に有効となる。範囲外の場合はGUI設定の方で反映する。
			if isinstance(resp[DataConf.TX], List):
				idx = 0
				for tx in resp[DataConf.TX]:
					tx.set_value(self._autoresp_data_tx[i], idx)
					idx += tx.get_size()
			# SerialManagaerに通知して解析ツリーを構築
			self._serial.autoresp_build(resp[DataConf.NAME], resp[DataConf.RX], self._autoresp_data_tx[i])

	def _send_settings_construct(self) -> None:
		# 実送信データHEXを別データとして保持する
		self._send_data_tx = []
		for i, data in enumerate(self._send_data):
			### 送信データ長を算出
			# 送信データHEX長と送信データサイズを比較
			tx_len = self._calc_data_len(data[DataConf.TX])
			data_len = max(tx_len, data[DataConf.TX_SIZE])
			# FCCを反映
			if data[4] >= data_len:
				data_len = data[4] + 1
			# 定義データを更新
			data[DataConf.TX_SIZE] = data_len
			### 送信データHEXを構築
			tx_data = None
			if isinstance(data[DataConf.TX], bytes):
				tx_data = data[DataConf.TX]
			if isinstance(data[DataConf.TX], List):
				tx_data = self._settings_construct_bytes(data[DataConf.TX])
			self._send_data_tx.append(tx_data)
			# FCC算出
			self._send_data_tx[i] = self._update_fcc(self._send_data_tx[i], data[4], data[5], data[6])
			# FCC算出結果を送信データ定義に反映する。
			# FCC位置設定が送信データ定義内にあった場合に有効となる。範囲外の場合はGUI設定の方で反映する。
			if isinstance(data[DataConf.TX], List):
				idx = 0
				for tx in data[DataConf.TX]:
					tx.set_value(self._send_data_tx[i], idx)
					idx += tx.get_size()

	def _calc_data_len(self, txs: List[gui_input]) -> int:
		if isinstance(txs, bytes):
			return len(txs)
		if isinstance(txs, List):
			txs_len = 0
			for tx in txs:
				txs_len += tx.get_size()
			return txs_len

	def _settings_construct_bytes(self, txs: List[gui_input]):
		data = b''
		# gui_inputリストからbytesを作成する
		for tx in txs:
			data += tx.get_bytes()
		return data

	def _update_fcc(self, tgt: bytes, fcc_pos:int, fcc_begin:int, fcc_end:int) -> bytes:
		# FCC位置が-1ならスキップ
		if fcc_pos != -1:
			# FCC計算
			fcc = 0
			fcc = self._calc_fcc(tgt, fcc_begin, fcc_end+1, fcc_pos)
			# FCC挿入
			resp_len = len(tgt)
			if resp_len-1 < fcc_pos:
				# 挿入位置が応答データサイズを超える場合、バッファを追加する
				# 挿入位置が応答データ長+1を超える場合はゼロ埋めする
				for i in range(resp_len, fcc_pos):
					tgt += (b'\0')
				tgt += (fcc.to_bytes(1, 'little'))
			else:
				# 挿入位置が応答データサイズ未満のときは既存バッファを書き換える
				temp = bytearray(tgt)
				temp[fcc_pos] = fcc
				tgt = bytes(temp)
		return tgt


	def _auto_response_update(self) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# self._autoresp_data を書き換え
		for i,resp in enumerate(self._autoresp_data):
			actual_len = len(self._autoresp_data_tx[i])
			# GUIから設定値を取得
			self._autoresp_data_tx[i] = self._get_gui_tx("resp", i, actual_len, resp[DataConf.TX])
			# FCC算出
			self._autoresp_data_tx[i] = self._update_fcc(self._autoresp_data_tx[i], resp[4], resp[5], resp[6])
			# GUI更新
			self._update_gui_tx("resp", i, actual_len, resp[DataConf.TX], self._autoresp_data_tx[i])
		# SerialManagaerに通知
		for i, resp in enumerate(self._autoresp_data):
			self._serial.autoresp_update(resp[DataConf.NAME], self._autoresp_data_tx[i])

	def _get_gui_tx(self, key: str, row: int, col_size: int, tx_data) -> bytes:
		"""
		GUI上の送信データ設定を取得する
		"""
		if isinstance(tx_data, bytes):
			return self._get_gui_tx_bytes(key, row, col_size, tx_data)
		if isinstance(tx_data, List):
			return self._get_gui_tx_list(key, row, col_size, tx_data)

	def _get_gui_tx_bytes(self, key: str, row: int, col_size: int, tx_data:bytes) -> bytes:
		"""
		GUI上の送信データ設定を取得する
		"""
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		resp_data = []
		for col in range(0, col_size):
			# 入力テキストをゼロ埋めで2桁にする
			data = self._window[(key, row, col)].Get().zfill(2)
			# 16進数文字列でなかったら 00 に強制置換
			if (hex_ptn.match(data) is None) or (len(data) > 2):
				data = "00"
			resp_data.append(data)
		return bytes.fromhex(''.join(resp_data))

	def _get_gui_tx_list(self, key: str, row: int, col_size: int, tx_data: List[gui_input]):
		"""
		GUI上の送信データ設定を取得する
		"""
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		resp_data = b''
		tx_len = len(tx_data)
		col = 0
		id = 0
		while col < col_size:
			data = None
			if id < tx_len:
				# gui_input定義があるとき
				data = tx_data[id].get_value(self._window[(key, row, id)].Get())
				col += tx_data[id].get_size()
			else:
				# gui_input定義がないとき
				# 入力テキストをゼロ埋めで2桁にする
				data = self._window[(key, row, id)].Get().zfill(2)
				# 16進数文字列でなかったら 00 に強制置換
				if (hex_ptn.match(data) is None) or (len(data) > 2):
					data = "00"
				data = bytes.fromhex(data)
				col += 1
			resp_data += data
			id += 1
		return resp_data

	def _update_gui_tx(self, key: str, row: int, col_size: int, tx_data, txs: bytes) -> bytes:
		"""
		GUI上の送信データ設定を更新する
		"""
		if isinstance(tx_data, bytes):
			return self._update_gui_tx_bytes(key, row, col_size, tx_data, txs)
		if isinstance(tx_data, List):
			return self._update_gui_tx_list(key, row, col_size, tx_data, txs)

	def _update_gui_tx_bytes(self, key: str, row: int, col_size: int, tx_data: bytes, txs: bytes) -> bytes:
		"""
		GUI上の送信データ設定を更新する
		"""
		for col in range(0,col_size):
			self._window[(key, row, col)].Update(value=format(txs[col], "02X"))

	def _update_gui_tx_list(self, key: str, row: int, col_size: int, tx_data: List[gui_input], txs: bytes):
		"""
		GUI上の送信データ設定を更新する
		"""
		tx_len = len(tx_data)
		col = 0
		id = 0
		while col < col_size:
			if id < tx_len:
				# gui_input定義があるとき
				self._window[(key, row, id)].Update(value=tx_data[id].get_gui_value())
				col += tx_data[id].get_size()
			else:
				# gui_input定義がないとき
				self._window[(key, row, id)].Update(value=format(txs[col], "02X"))
				col += 1
			id += 1

	def _req_send_bytes(self, idx:int) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# self._send を書き換え
		data = self._send_data[idx]
		actual_len = len(self._send_data_tx[idx])
		# GUIから設定値を取得
		self._send_data_tx[idx] = self._get_gui_tx("send", idx, actual_len, data[DataConf.TX])
		# データが有効なときだけ送信処理
		if len(self._send_data_tx[idx]) <= 0:
			return
		# FCC算出
		self._send_data_tx[idx] = self._update_fcc(self._send_data_tx[idx], data[4], data[5], data[6])
		# GUI更新
		self._update_gui_tx("send", idx, actual_len, data[DataConf.TX], self._send_data_tx[idx])
		# SerialManagaerに通知
		if self._notify_to_serial.full():
			print("Queue is full, send req denied.")
		else:
			self._notify_to_serial.put([serial_mng.ThreadNotify.TX_BYTES, self._send_data_tx[idx], self._send_data[idx][DataConf.NAME]])

	def _sendopt_update(self):
		time_ptn = re.compile(r'[0-9]+')
		time = self._window["sendopt_tx_delay"].Get()
		if time_ptn.match(time) is None:
			time = 0
			self._window["sendopt_tx_delay"].Update(value="0")
		self._sendopt_tx_delay = int(time)
		self._serial.sendopt_txdelay_update(self._sendopt_tx_delay)

	def _calc_fcc(self, data:bytes, begin:int, end:int, pos:int) -> int:
		"""
		FCC計算
		dataの(begin,end]要素の総和の2の補数を計算する
		* beginは含む、endは含まない
		(begin,end] がdata長を超えたら 0x00 を加算とする（何もしない）
		"""
		fcc: int = 0
		data_len = len(data)
		for i in range(begin, end):
			if (i != pos) and (i < data_len):
				fcc += data[i]
#		fcc = ((fcc % 256) ^ 0xFF) + 1
		fcc = ((fcc ^ 0xFF) + 1) % 256
		return fcc


	def _hex2bytes(self, hex: str) -> bytes:
		return bytes.fromhex(hex)


	def _auto_response_settings(self) -> None:
		"""
		Auto Response Settings
		自動応答の定義はここを編集する
		"""
		hex = self._hex2bytes
		inp = gui_input.input
		inp16 = gui_input.input_16
		sel = gui_input.select
		fix = gui_input.fix

		self._autoresp_caption = [
			"[自動応答データ設定]", "", "応答データ"
		]
		self._autoresp_head = [
			"Name", "Recv", "ST", "XX", "XX", "XX", "XX", "YY"
		]
		self._autoresp_data = [
				# 応答			# 自動応答対象					# 応答データ定義							# FCC定義(idx=0開始, 挿入位置=-1でFCC設定無効)
				# 名称			# 受信データパターン			# 送信HEX						# サイズ	# 挿入位置	# 計算開始位置	# 計算終了位置
#			[	"Test1",		hex('ABCDEF0102'),				hex('aaBBccDDeeFF'),			24,			6,			2,				4,					],
#			[	"Test2",		hex('ABCD0102'),				hex('aa00bb11cc22dd33ee44'),	24,			12,			6,				7,					],
			[	"Test3",		hex('ABCD03'),					hex('aa00bb11cc22dd33ee44'),	24,			-1,			0,				9,					],
			# 応答なし設定(応答データ＝空)で受信データパターンマッチ時に受信データ＋名称だけ出力
			[	"Test4",		hex('ABCDEF0102'),				b'',	0,	-1,	0,	0,	],
			[	"Test5",		hex('ABCD0102'),				[ inp('aa'), sel({'機能ON':1, '機能OFF':0}), fix('00'), inp16('8000'), fix('00'), fix('00'), fix('00'), fix('00') ],	18,			17,			1,				16,					],
		]

	def _send_settings(self) -> None:
		hex = self._hex2bytes
		inp = gui_input.input
		inp16 = gui_input.input_16
		sel = gui_input.select
		fix = gui_input.fix

		self._send_caption = [
			"[送信データ設定]", "送信データ",
		]
		self._send_head = [
			"Name", "ST", "XX", "XX", "XX", "XX", "YY"
		]
		self._send_data = [
				# 送信設定						# 手動送信データ定義					# FCC定義(idx=0開始)
				# 名称			#受信データ		# 送信HEX					#サイズ		# 挿入位置	# 計算開始位置	# 計算終了位置
			[	"Manual",		None,			hex(''),					24,			17,			4,				7,				],
			[	"TestSend1",	None,			hex('00112233'),			-1,			4,			0,				3,				],
			[	"TestSend2",	None,			hex('00'),					5,			-1,			0,				3,				],
			[	"TestSend3",	None,			hex(''),					0,			-1,			0,				3,				],
			[	"TestSend4",	None,			[ inp('aa'), sel({'ON':1, 'OFF':0}), fix('00'), fix('00'), fix('00'), fix('00'), fix('00'), inp16('8000') ],	18,			17,			1,				16,					],
		]

if __name__=="__main__":
	try:
		gui = gui_manager()
		gui.exe()
	except:
		import traceback
		traceback.print_exc()
	

