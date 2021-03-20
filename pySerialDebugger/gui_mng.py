import time
import concurrent.futures
from typing import Any, Callable, Union, List, Type, Dict, Tuple
import PySimpleGUI as sg
from PySimpleGUI.PySimpleGUI import Input
from multiprocessing import Array, Value
import queue
import re
import enum
from . import serial_mng
from .send_node import send_data, send_data_node, send_mng, send_data_list
from .autosend import autosend_data, autosend_mng, autosend_node, autosend_list
from .autoresp import autoresp_data, autoresp_list, autoresp_mng
from . import user_settings
from . import thread



class DataConf:
	"""
	GUI構築定義データ
	"""
	ENABLE = 0		# 有効無効設定
	NAME = 1		# 定義名
	RX = 2			# 受信データ
	TX = 3			# 送信データ
	TX_SIZE = 4		# 送信データサイズ
	FCC_POS = 5		# FCC挿入位置
	FCC_BEGIN = 6	# FCC計算開始位置
	FCC_END = 7		# FCC計算終了位置
	GUI_ID = 8		# bytes上の位置とGUI上の位置との対応付けテーブル
	BYTES_ID = 9	# GUI上の位置とbytes上の位置との対応付けテーブル

class ThreadNotify(enum.Enum):
	"""
	スレッド間通信メッセージ
	"""
	# [GUI->管理]通知
	AUTOSEND_ENABLE = enum.auto()			# 自動送信有効化
	AUTOSEND_DISABLE = enum.auto()			# 自動送信無効化


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
		# GUI共通部品定義
		self._gui_param_init()
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
			[sg.Column(layout_serial_send, scrollable=True, vertical_scroll_only=False, size=(1450, 280), vertical_alignment="top")],
			[sg.Frame("Send Option:", layout_serial_send_option)],
		]
		# Define: AutoSend View
		self._autosend_init()
		layout_serial_autosend = [
			self._layout_autosend_caption,
			self._layout_autosend_head,
			*self._layout_autosend_data
		]
		layout_serial_autosend_column = [
			[sg.Column(layout_serial_autosend, scrollable=True, vertical_scroll_only=False, size=(1450, 280), vertical_alignment="top")],
		]
		# Define: AutoResponse View
		self._auto_response_init()
		layout_serial_auto_resp = [
			self._layout_autoresp_caption,
			self._layout_autoresp_head,
			*self._layout_autoresp_data
		]
		layout_serial_auto_resp_column = [
			[sg.Column(layout_serial_auto_resp, scrollable=True, vertical_scroll_only=False, size=(1450, 280), vertical_alignment="top")],
			[sg.Button("Update", key="btn_autoresp_update", size=(15, 1), enable_events=True)],
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
				sg.Tab('Manual Send Settings', layout_serial_send_column),
				sg.Tab('Auto Send Settings', layout_serial_autosend_column),
			]])],
			[sg.Frame("Log:", layout_serial_log)],
		]
		self._window = sg.Window("pySerialDebugger", layout, finalize=True)

	def _init_event(self) -> None:
		"""
		GUIイベントとイベントハンドラをひもづける
		"""
		# clear events
		self._events = {
			# Exit
			# None: self._hdl_exit,
			# Button: Connect
			"btn_connect": self._hdl_btn_connect,
			### 自動応答
			# 有効設定更新
			"autoresp_enable": self._hdl_autoresp_enable,
			# データ更新
			"btn_autoresp_update": self._hdl_btn_autoresp_update,
			# GUI更新
			"resp": self._hdl_hex_ui_resp,
			### 送信
			# 送信ボタン
			"btn_send": self._hdl_btn_send,
			# オプション更新
			"btn_sendopt_update": self._hdl_btn_sendopt_update,
			# GUI更新
			"send": self._hdl_hex_ui_send,
			# Button: AutoSend
			"btn_autosend": self._hdl_btn_autosend,
			# ButtonMenu:
			# Script Write Event
			"_swe_disconnected": self._hdl_swe_disconnected,
			"_swe_autosend_disable": self._hdl_autosend_disable,
			"_swe_autosend_gui_update": self._hdl_autosend_gui_update,
		}
		# event init
		self._gui_hdl_init()

	def _hdl_exit(self, values):
		self.close()
		print("exit")

	def _hdl_hex_ui_resp(self, values, row, col):
		"""
		自動応答設定：送信HEXデータ入力GUIからの操作イベントハンドラ
		"""
		part: sg.Element = self._window[("resp", row, col)]
		self._update_sendhex_gui(part, self._autoresp_data, self._autoresp_data_tx, "resp", row, col)

	def _hdl_hex_ui_send(self, values, row, col):
		"""
		手動送信設定：送信HEXデータ入力GUIからの操作イベントハンドラ
		"""
		part: sg.Element = self._window[("send", row, col)]
		self._update_sendhex_gui(part, self._send_data, self._send_data_tx, "send", row, col)

	def _gui_hdl_init(self):
		self._conn_btn_hdl = self._window["btn_connect"]
		self._conn_status_hdl = self._window["text_status"]
		self._gui_hdl_autoresp_update_btn = self._window["btn_autoresp_update"]

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
				self._future_serial = self._executer.submit(self._serial.connect, self._notify_to_serial, self._notify_from_serial)
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
				thread.messenger.notify_exit_serial()
			# 切断中に移行
			self._gui_conn_state = self.DISCONNECTING
			# GUI操作
			self._conn_btn_hdl.Update(text="Disconnecting", disabled=True)
			self._conn_status_hdl.Update(value="Disconnecting...")
			# シリアル通信スレッドは終了したらThreadNotifyで通知する
			# 自動送信を全終了
			# self._autosend_mng.end(0)
			#for row, autosend in enumerate(self._autosend_data):
			#	if self._autosend_data[row].running():
			#		# 自動送信有効のとき
			#		# 自動送信を無効にする
			#		self._comm_hdle_notify.put([ThreadNotify.AUTOSEND_DISABLE, row])
			#		# GUI更新
			#		self._window[("btn_autosend", row, None)].Update(text="Start")
			#	else:
			#		# 自動送信無効のとき
			#		pass

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


	def _hdl_autoresp_enable(self, values, row:int, col:int):
		"""
		イベントハンドラ：有効設定更新
		"""
		# 有効設定取得
		value = values[("autoresp_enable", row, col)]
		# 設定更新
		self._autoresp_mng.update_enable(value, row)


	def _hdl_btn_autoresp_update(self, values):
		"""
		イベントハンドラ：自動応答設定更新

		"""
		# シリアル通信稼働中はメッセージを投げるのでGUIを無効化
		if self._serial.is_open():
			# データ更新までボタン無効化
			self._gui_hdl_autoresp_update_btn.Update(text="Updating...", disabled=True)

		# 設定情報のチェックを実施
		dup_check = self._autoresp_mng.update_tree_check()
		if dup_check:
			# 重複があれば先優先で、残りは無効化
			print("*warning* enable setting is duplicate, automatically fixed.")
			for idx in dup_check:
				self._window[("autoresp_enable", idx, None)].update(value=False)

		# 自動応答データ設定を更新
		if self._serial.is_open():
			# シリアル通信スレッドに自動応答データ更新のリクエストを投げる
			#self._notify_to_serial.put([serial_mng.ThreadNotify.AUTORESP_UPDATE, self._autoresp_update, None])
			thread.messenger.notify_serial_autoresp_update(self._autoresp_update)
		else:
			# 非通信時は直接更新
			self._autoresp_update()

	def _hdl_btn_send(self, values, row, col):
		self._req_send_bytes(row)

	def _hdl_btn_sendopt_update(self, values):
		self._sendopt_update()

	def _hdl_btn_autosend(self, values, row, col):
		if self._serial.is_open():
			if self._autosend_mng.running():
				# 自動送信有効のとき
				# 自動送信を無効にする
				# とりあえず直接操作。バグになるようならスレッド間メッセージで通知する
				self._autosend_mng.stop(row)
				#self._comm_hdle_notify.put([ThreadNotify.AUTOSEND_DISABLE, row])
				# GUI更新
				self._window[("btn_autosend", row, col)].Update(text="Start")
			else:
				# 自動送信無効のとき
				# 自動送信を有効にする
				self._autosend_mng.start(row)
				#self._comm_hdle_notify.put([ThreadNotify.AUTOSEND_ENABLE, row])
				# GUI更新
				self._window[("btn_autosend", row, col)].Update(text="Sending..")

	def _hdl_autosend_disable(self, values):
		# GUI更新
		self._window[("btn_autosend", values["_swe_autosend_disable"], None)].Update(text="Start")

	def _hdl_autosend_gui_update(self, values):
		# 引数取得
		row, col_disable, col_enable = values["_swe_autosend_gui_update"]
		# GUI更新
		if col_disable is not None:
			self._window[("autosend", row, col_disable)].Update(text_color=self._deactive_box)
		if col_enable is not None:
			self._window[("autosend", row, col_enable)].Update(text_color=self._active_box)

	def exe(self):
		# スレッド管理
		self._future_comm_hdle = None
		self._future_serial = None
		# スレッド間通信用キュー
		self._comm_hdle_notify = queue.Queue(10)

		self._notify_to_serial = queue.Queue(10)
		self._notify_from_serial = queue.Queue(10)
		# (1) Windows イベントハンドラ
		# (2) シリアル通信
		# (3) 全体管理(シリアル通信->送受信->GUI)
		# の3スレッドで処理を実施する
		self._executer = concurrent.futures.ThreadPoolExecutor(max_workers=3)
		self._future_comm_hdle = self._executer.submit(self.comm_hdle, self._notify_from_serial, self._comm_hdle_notify)
		self.wnd_proc()
		self._executer.shutdown()
		self.close()
		print("Exit: all")

	def wnd_proc(self):
		while True:
			event, values = self._window.read()

			if event in self._events:
				self._events[event](values)
			if isinstance(event, tuple):
				t_ev, idx, col = event
				self._events[t_ev](values, idx, col)
			if event in (None, 'Quit'):
				# 自動送信処理:シリアル通信側で停止(何もしない)
				# 各スレッドに終了通知
				thread.messenger.notify_exit_serial()
				thread.messenger.notify_exit_hdlr()
				# queueを空にしておく
				while not self._notify_from_serial.empty():
					self._notify_from_serial.get_nowait()
				break
		print("Exit: wnd_proc()")

	def comm_hdle(self, serial_notify: queue.Queue, self_notify: queue.Queue):
		self.log_str = ""
		self.log_pos = 0
		timestamp_curr: int = 0
		timestamp_rx: int = 0
		rx_commit_interval: int = 1 * 1000 * 1000 * 1000	# 1sec無受信でコミット
		try:
			# exit通知があるまでループ
			while not thread.messenger.has_exit_hdlr():
				# 今回現在時間取得
				timestamp_curr = time.perf_counter_ns()
				# シリアル通信からの指令を待機
				if thread.messenger.has_notify_serial2hdrl():
					msg = thread.messenger.get_notify_serial2hdrl()
					if msg.notify == thread.ThreadNotify.AUTORESP_UPDATE_FIN:
						# データ更新でボタン有効化
						self._gui_hdl_autoresp_update_btn.Update(text="Update", disabled=False)
				if not serial_notify.empty():
					# queueからデータ取得
					notify, data, autoresp_name, timestamp = serial_notify.get_nowait()
					# 通知に応じて処理実施
					if notify == serial_mng.ThreadNotify.COMMIT_RX:
						if self.log_str != "":
							# ログ出力
							self.comm_hdle_log_output("RX", self.log_str, autoresp_name, timestamp)
							# バッファクリア
							self.log_str = ""
					elif notify == serial_mng.ThreadNotify.PUSH_RX:
						# 受信時タイムスタンプ取得
						timestamp_rx = timestamp_curr
						# ログバッファに受信データを追加
						# ログ出力は実施しない
						self.log_str += data.hex().upper()
					elif notify == serial_mng.ThreadNotify.COMMIT_TX:
						# 送信データをログ出力
						self.comm_hdle_log_output("TX", data.hex().upper(), autoresp_name, timestamp)
					elif notify == serial_mng.ThreadNotify.DISCONNECTED:
						# GUIスレッドに切断を通知
						# self_notify.put(True)
						# スレッドセーフらしい
						self._window.write_event_value("_swe_disconnected", "")
					#elif notify == serial_mng.ThreadNotify.AUTORESP_UPDATE_FIN:
					#	# データ更新でボタン有効化
					#	self._gui_hdl_autoresp_update_btn.Update(text="Update", disabled=False)
					else:
						pass
				# GUIからの指令を待機
				if not self_notify.empty():
					# queueからデータ取得
					notify, pos = self_notify.get_nowait()
					# 通知毎処理
					if notify == ThreadNotify.AUTOSEND_ENABLE:
						# 自動送信有効化
						#self._autosend_data[pos].start(pos)
						pass
					elif notify == ThreadNotify.AUTOSEND_DISABLE:
						# 自動送信無効化
						#self._autosend_data[pos].end(pos)
						pass
				# 一定時間受信が無ければ送信バッファをコミット
				if (timestamp_curr - timestamp_rx) > rx_commit_interval:
					if self.log_str != "":
						# ログ出力
						self.comm_hdle_log_output("RX", self.log_str, "", timestamp_rx)
						# バッファクリア
						self.log_str = ""
				# GUIに処理を回す
				time.sleep(0.000001)
				#print("Run: serial_hdle()")
			# 処理終了
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

	def _gui_param_init(self) -> None:
		# GUIパーツ定義
		# フォント定義
		self._font_caption = (self._header_font_family, 10)
		self._font_header = (self._data_font_family, 10)
		self._font_btn_txt = (self._data_font_family, 11)
		self._font_btn = (self._data_font_family, 9)
		self._font_enable = (self._data_font_family, 9)
		self._font_name = (self._header_font_family, 10)
		self._font_rx = (self._data_font_family, 10)
		self._font_tx = (self._data_font_family, 9)
		# サイズ定義
		self._size_caption = (23, 1)
		self._size_btn_txt = (5, 1)
		self._size_btn = (5, 1)
		self._size_enable = (5, 1)
		self._size_name = (20, 1)
		self._size_rx = (20, 1)
		self._size_tx = (6, 1)
		self._size_as_caption = (13, 1)
		self._size_as_btn = (10,1)
		self._size_as = (17,1)
		# padding
		self._pad_tx = ((0, 0), (0, 0))
		# text_color
		#self._active_box = sg.theme_input_background_color()
		self._active_box = '#F0F000'
		self._deactive_box = sg.theme_element_text_color()

	def _gui_build_input(self):
		"""
		Input GUI 構築クロージャ
		"""
		size = self._size_tx
		font = self._font_tx
		disabled = True
		pad = self._pad_tx
		disabled_readonly_background_color = sg.theme_background_color()
		disabled_readonly_text_color = sg.theme_element_text_color()
		def build(data:str):
			return sg.Input(data, size=size, font=font, disabled=disabled, pad=pad, disabled_readonly_background_color=disabled_readonly_background_color, disabled_readonly_text_color=disabled_readonly_text_color)
		return build

	def _auto_response_init(self) -> None:
		"""
		_auto_response_settings の設定内容をGUI上に構築する。
		以降はGUI上で更新されたら解析情報に反映する。
		"""
		# 定義を読み込む
		gui_settings = user_settings.auto_response_settings()
		self._autoresp_caption = gui_settings[0]
		self._autoresp_head = gui_settings[1]
		self._autoresp_data = gui_settings[2]
		# 受信解析マネージャ作成
		# コンストラクタで解析ツリーを構築、
		# 自動応答enableが重複したときは自動でdisableに変更する。
		# このあとにGUI構築すること
		self._autoresp_mng = autoresp_mng(self._autoresp_data, self._autosend_mng)
		autoresp_data.set_gui_info(self._size_tx, self._pad_tx, self._font_tx)
		# 受信解析マネージャをシリアルマネージャに渡す
		self._serial.autoresp(self._autoresp_mng)
		# GUI構築
		input = self._gui_build_input()
		# Layout: Caption
		self._layout_autoresp_caption = []
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[0], size=self._size_caption, font=self._font_name))
		#self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[1], size=self._size_caption, font=self._font_name))
		#self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[2], size=self._size_caption, font=self._font_name))
		# Layout: Header
		self._layout_autoresp_head = []
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[autoresp_list.ENABLE], size=self._size_enable, font=self._font_enable))
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[autoresp_list.ID], size=self._size_name, font=self._font_header))
		self._layout_autoresp_head.extend( [ input(data) for data in self._autoresp_head[autoresp_list.DATA] ] )
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[autoresp_list.SENDDATA_ID], size=self._size_rx, font=self._font_header))
		# Layout: Data
		self._layout_autoresp_data = []
		for resp in self._autoresp_data:
			# GUI処理
			# Add empty list
			row = len(self._layout_autoresp_data)
			parts = []
			# Add AutoResponse_Enable
			parts.append(sg.Checkbox("", default=resp[autoresp_list.ENABLE], key=("autoresp_enable",row, None), size=(2, 1), font=self._font_enable, enable_events=True))
			# Add Name
			parts.append(sg.Text(resp[autoresp_list.ID], size=self._size_name, font=self._font_name))
			# Add RecvData
			parts.extend(self._init_gui_rx("resp", row, resp))
			# Add SendDataID
			parts.append(sg.Text(resp[autoresp_list.SENDDATA_ID], size=self._size_name, font=self._font_name))
			# GUI更新
			self._layout_autoresp_data.append(parts)

	def _init_gui_rx(self, key: str, row: int, rx_data: List[any]):
		data_list = rx_data[autoresp_list.DATA]
		gui_parts = []
		col = 0
		# autoresp_dataをすべてチェック
		for data in data_list:
			data: autoresp_data
			temp = data.get_gui(key, row, col)
			col += len(temp)
			gui_parts.extend(temp)
		# 結果を返す
		return gui_parts

	def _send_init(self) -> None:
		# 定義を読み込む
		gui_settings = user_settings.send_settings()
		self._send_caption = gui_settings[0]
		self._send_head = gui_settings[1]
		self._send_data = gui_settings[2]
		# 定義解析
		#self._send_settings_construct()
		self._send_mng = send_mng(self._send_data)
		send_data.set_gui_info(self._size_tx, self._pad_tx, self._font_tx)

		# Make Caption
		self._layout_send_caption = []
		self._layout_send_caption.append(sg.Text("", size=self._size_btn_txt, font=self._font_btn_txt))
		self._layout_send_caption.append(sg.Text(self._send_caption[0], size=self._size_name, font=self._font_name))
		self._layout_send_caption.append(sg.Text(self._send_caption[2], size=self._size_name, font=self._font_name)) 
		# Make Header
		self._layout_send_head = []
		self._layout_send_head.append(sg.Text("", size=self._size_btn_txt, font=self._font_btn_txt))
		self._layout_send_head.append(sg.Text(self._send_head[send_data_list.ID], size=self._size_name, font=self._font_name))
		# ヘッダ定義がデータ最大に足りなかったら穴埋めする
		# Header GUI作成クロージャ
		def header_gui_closure():
			# 定義
			def get(text:str):
				return sg.Input(text, size=self._size_tx, font=self._font_tx, disabled=True, pad=self._pad_tx, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())
			# return
			return get
		#
		gui_get = header_gui_closure()
		head_data = self._send_head[send_data_list.DATA]
		head_max = len(head_data)
		head_suffix = ""
		# header定義数がデータ定義数に達していないとき、末尾を配列っぽくしておく
		if head_max < self._send_mng._max_size:
			head_suffix = head_data[head_max-1]
			head_data[head_max-1] = head_suffix + "[1]"
		self._layout_send_head.extend([gui_get(head) for head in head_data])
		# 不足分を出力
		if head_max < self._send_mng._max_size:
			data_diff = self._send_mng._max_size - head_max
			self._layout_send_head.extend( [gui_get(head_suffix + "[" + str(i + 2) + "]") for i in range(0, data_diff)])
		# Make Values
		self._layout_send_data = []
		data: send_data_node
		for row, data in enumerate(self._send_mng._send_data_list):
			# GUI処理
			# Add empty list
			#idx = len(self._layout_send_data)
			parts = []
			# Add Button col
			parts.append(sg.Button("Send", size=self._size_btn, font=self._font_btn, key=("btn_send",row, None)))
			# Add Name col
			parts.append(sg.Text(data.id, size=self._size_name, font=self._font_name))
			# Add resp data col
			parts.extend(data.get_gui("send", row))
			# GUI更新
			self._layout_send_data.append(parts)

	def _autosend_init(self) -> None:
		# 定義を読み込む
		gui_settings = user_settings.autosend_settings()
		self._autosend_caption = gui_settings[0]
		self._autosend_head = gui_settings[1]
		self._autosend_data = gui_settings[2]
		# 定義解析
		# 自動送信マネージャに手動送信用コールバックを登録
		#autosend_mng.set_send_cb(self._autosend_send)
		autosend_mng.set_exit_cb(self._autosend_exit)
		autosend_mng.set_gui_update_cb(self._autosend_gui_update)
		#
		self._autosend_mng = autosend_mng(self._autosend_data, self._send_mng)
		autosend_node.set_gui_info(self._size_tx, self._pad_tx, self._font_tx)
		# 自動送信マネージャをシリアルマネージャに渡す
		self._serial.autosend(self._autosend_mng)

		# Layout: Caption
		self._layout_autosend_caption = []
		self._layout_autosend_caption.append(sg.Text(self._autosend_caption[0], size=self._size_as_caption, font=self._font_name))
		self._layout_autosend_caption.append(sg.Text(self._autosend_caption[1], size=(100,1), font=self._font_name)) 
		# Layout: Header
		self._layout_autosend_head = []
		self._layout_autosend_head.append(sg.Text(self._autosend_head[autosend_list.ENABLE], size=self._size_enable, font=self._font_enable))
		self._layout_autosend_head.append(sg.Text(self._autosend_head[autosend_list.ID], size=self._size_name, font=self._font_header))
		self._layout_autosend_head.append(sg.Text(self._autosend_head[autosend_list.DATA], size=self._size_rx, font=self._font_header))
		# Layout: Values
		self._layout_autosend_data = []
		for row, data in enumerate(self._autosend_mng._data_list):
			data: autosend_node
			# GUI処理
			# Add empty list
			row = len(self._layout_autosend_data)
			parts = []
			# Add Button col
			parts.append(sg.Button("Start", size=self._size_as_btn, font=self._font_btn, key=("btn_autosend",row, None)))
			# Add Name col
			parts.append(sg.Text(data.id, size=self._size_name, font=self._font_name))
			# Add Settings col
			parts.extend(data.get_gui("autosend", row))
			# GUI更新
			self._layout_autosend_data.append(parts)


	def _autosend_send(self, idx: int) -> None:
		#idx = self._send_data_ref[name]
		# 送信データをGUIから取得して送信する場合
		self._req_send_bytes(idx)

	def _autosend_exit(self, idx: int) -> None:
		self._window.write_event_value("_swe_autosend_disable", idx)

	def _autosend_gui_update(self, row: int, col_disable: int, col_enable: int) -> None:
		self._window.write_event_value("_swe_autosend_gui_update", (row, col_disable, col_enable))


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


	def _update_sendhex_gui(self, gui: sg.Element, def_data_list, bytes_list: List[bytes], key: str, row: int, gui_id: int) -> None:
		"""
		送信HEXデータGUIの入力値チェック
		"""
		# GUIから値を取得
		data, size = self._get_gui_tx_data(gui, key, row, gui_id, def_data_list[row][DataConf.TX])
		# 送信HEXを更新
		temp_hex = bytearray(bytes_list[row])
		data_idx = 0
		bytes_id = def_data_list[row][DataConf.BYTES_ID][gui_id]
		for idx in range(bytes_id, bytes_id+size):
			temp_hex[idx] = data[data_idx]
			data_idx += 1
		bytes_list[row] = bytes(temp_hex)
		# FCC算出
		fcc_pos = def_data_list[row][DataConf.FCC_POS]
		bytes_list[row] = self._update_fcc(bytes_list[row], fcc_pos, def_data_list[row][DataConf.FCC_BEGIN], def_data_list[row][DataConf.FCC_END])
		# GUI更新
		# data
		self._update_gui_tx_data(gui, key, row, gui_id, None, def_data_list[row][DataConf.TX], bytes_list[row], None)
		# FCC
		fcc_pos = def_data_list[row][DataConf.FCC_POS]
		fcc_id = def_data_list[row][DataConf.GUI_ID][fcc_pos]
		fcc_gui: sg.Element = self._window[(key, row, fcc_id)]
		self._update_gui_tx_data(fcc_gui, key, row, fcc_id, fcc_pos, def_data_list[row][DataConf.TX], bytes_list[row], "02X")

	def _get_gui_tx_data(self, gui: sg.Element, key: str, row: int, col_size: int, tx_data) -> Tuple[bytes, int]:
		"""
		GUI上の送信データ設定を取得する
		"""
		if isinstance(tx_data, bytes):
			return self._get_gui_data_bytes(gui, key, row, col_size, tx_data)
		if isinstance(tx_data, List):
			return self._get_gui_data_list(gui, key, row, col_size, tx_data)

	def _get_gui_data_bytes(self, gui: sg.Element, key: str, row: int, col: int, tx_data: bytes) -> Tuple[bytes, int]:
		"""
		GUI上の送信データ設定を取得する
		"""
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		# 入力テキストをゼロ埋めで2桁にする
		data = gui.Get().zfill(2)
		# 16進数文字列でなかったら 00 に強制置換
		if (hex_ptn.match(data) is None) or (len(data) > 2):
			data = "00"
		return (bytes.fromhex(data), 1)

	def _get_gui_data_list(self, gui: sg.Element, key: str, row: int, col: int, tx_data: List[send_data]) -> Tuple[bytes, int]:
		"""
		GUI上の送信データ設定を取得する
		"""
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		tx_len = len(tx_data)
		data = None
		size = 0
		if col < tx_len:
			# send_node定義があるとき
			# send_nodeにGUI設定値を渡して値に変換する
			data = tx_data[col].get_value(gui.Get())
			size = tx_data[col].get_size()
		else:
			# send_node定義がないとき
			# 入力テキストをゼロ埋めで2桁にする
			data = gui.Get().zfill(2)
			# 16進数文字列でなかったら 00 に強制置換
			if (hex_ptn.match(data) is None) or (len(data) > 2):
				data = "00"
			data = bytes.fromhex(data)
			size = 1
		return (data, size)

	def _update_gui_tx_data(self, gui, key: str, row: int, gui_id: int, bytes_idx: int, tx_data, txs: bytes, fmt: str) -> bytes:
		"""
		GUI上の送信データ設定を更新する
		"""
		if isinstance(tx_data, bytes):
			return self._update_gui_tx_data_bytes(gui, key, row, gui_id, bytes_idx, tx_data, txs, fmt)
		if isinstance(tx_data, List):
			return self._update_gui_tx_data_list(gui, key, row, gui_id, bytes_idx, tx_data, txs, fmt)

	def _update_gui_tx_data_bytes(self, gui: sg.Element, key: str, row: int, gui_id: int, bytes_idx: int, tx_data: bytes, txs: bytes, fmt: str) -> bytes:
		"""
		GUI上の送信データ設定を更新する
		"""
		if fmt is None:
			fmt = "X"
		gui.Update(value=format(txs[gui_id], fmt))

	def _update_gui_tx_data_list(self, gui: sg.Element, key: str, row: int, gui_id: int, bytes_idx: int, tx_data: List[send_data], txs: bytes, fmt: str):
		"""
		GUI上の送信データ設定を更新する
		"""
		if fmt is None:
			fmt = "X"
		tx_len = len(tx_data)
		if gui_id < tx_len:
			# send_node定義があるとき
			gui.Update(value=tx_data[gui_id].get_gui_value(fmt))
		else:
			# send_node定義がないとき
			gui.Update(value=format(txs[bytes_idx], fmt))





	def _autoresp_update(self) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# 
		self._autoresp_mng.update_tree()

	def _req_send_bytes(self, idx:int) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
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
		fcc = ((fcc ^ 0xFF) + 1) % 256
		return fcc




if __name__=="__main__":
	try:
		gui = gui_manager()
		gui.exe()
	except:
		import traceback
		traceback.print_exc()
	

