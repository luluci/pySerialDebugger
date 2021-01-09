import time
import concurrent.futures
from typing import Union, List
import PySimpleGUI as sg
from PySimpleGUI.PySimpleGUI import Input
from . import serial_mng
from multiprocessing import Value
import queue
import re

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
			[sg.Column(layout_serial_auto_resp, scrollable=True, vertical_scroll_only=False, size=(1300, 200))],
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
			[sg.Column(layout_serial_send, scrollable=True, vertical_scroll_only=False, size=(1300, 200))],
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
			# Script Write Event
			"_swe_disconnected": self._hdl_swe_disconnected,
		}
		# event init
		self._hdl_btn_connect_init()

	def _hdl_exit(self, values):
		self.close()
		print("exit")

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

	def _hdl_btn_send(self, values, idx):
		self._req_send_bytes(idx)

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
				t_ev, idx = event
				self._events[t_ev](values, idx)
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
		# FCC処理
		self._auto_response_update_fcc()
		# SerialManagaerに通知
		self._serial.autoresp_build(self._autoresp_data)
		# GUIに落とし込む
		# AutoResp定義解析
		resp_len_max = 0
		for resp in self._autoresp_data:
			if len(resp[2]) > resp_len_max:
				resp_len_max = len(resp[2]) + 2
			if resp[3] > resp_len_max:
				resp_len_max = resp[3] + 2
		# GUIパーツ定義
		font_name = (self._header_font_family, 10)
		font_rx = (self._data_font_family, 10)
		font_tx = (self._data_font_family, 9)
		size_name = (20, 1)
		size_rx = (20, 1)
		size_tx = (5, 1)
		# Make Caption
		self._layout_autoresp_caption = []
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[0], size=size_name, font=font_name))
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[1], size=size_rx, font=font_name)) 
		self._layout_autoresp_caption.append(sg.Text(self._autoresp_caption[2], size=size_name, font=font_name)) 
		# Make Header
		# Name,Recvは固定とする
		# ヘッダ定義がデータ最大に足りなかったら穴埋めする
		head_max = len(self._autoresp_head)
		self._layout_autoresp_head = []
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[0], size=size_name, font=font_name))
		self._layout_autoresp_head.append(sg.Text(self._autoresp_head[1], size=size_rx, font=font_rx)) 
		head_suffix = ""
		if head_max < resp_len_max:
			head_suffix = self._autoresp_head[head_max-1]
			self._autoresp_head[head_max-1] = head_suffix + "[1]"
		self._layout_autoresp_head.extend([sg.Input(self._autoresp_head[i], size=size_tx, font=font_tx, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(2, head_max)])
		if head_max < resp_len_max:
			self._layout_autoresp_head.extend( [sg.Input(head_suffix + "[" + str(i - head_max + 2) + "]", size=size_tx, font=font_tx, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(head_max, resp_len_max)])
		# Make Values
		self._layout_autoresp_data = []
		for resp in self._autoresp_data:
			# GUI処理
			# Add empty list
			self._layout_autoresp_data.append([])
			idx = len(self._layout_autoresp_data) - 1
			# Add Name,Recv col
			self._layout_autoresp_data[idx].append(sg.Text(resp[0], size=size_name, font=font_name))
			self._layout_autoresp_data[idx].append(sg.Text(resp[1].hex().upper(), size=size_rx, font=font_rx))
			# Add resp data col
			self._layout_autoresp_data[idx].extend([sg.Input( format(byte,"02X"), size=size_tx, font=font_tx, key=(idx,i), enable_events=False) for i,byte in enumerate(resp[2])])
			# Add empty data col
			begin = len(resp[2])
			end = resp[3]
			self._layout_autoresp_data[idx].extend([sg.Input( "", size=size_tx, font=font_tx, key=(idx,i), enable_events=False) for i in range(begin, end)])

	def _send_init(self) -> None:
		# 定義を読み込む
		self._send_settings()
		# FCC処理
		self._send_update_fcc_all()
		# Send定義解析
		# データサイズ更新
		send_col_num = 0
		for data in self._send_data:
			send_data_len = len(data[1])
			send_data_size = data[2] 
			# data毎のデータ数更新
			data_len = send_data_len
			if send_data_len < send_data_size:
				data_len = send_data_size
			data[2] = data_len
			# send_data GUI 列数を算出
			if data_len > send_col_num:
				send_col_num = data_len
		# Name分を加算
		send_col_num += 1
		# GUIパーツ定義
		font_btn_txt = (self._data_font_family, 11)
		font_btn = (self._data_font_family, 9)
		font_name = (self._header_font_family, 10)
		font_tx = (self._data_font_family, 9)
		size_btn_txt = (5, 1)
		size_btn = (5, 1)
		size_name = (20, 1)
		size_tx = (5, 1)
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
		self._layout_send_head.extend([sg.Input(self._send_head[i], size=size_tx, font=font_tx, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(1, head_max)])
		if head_max < send_col_num:
			self._layout_send_head.extend( [sg.Input(head_suffix + "[" + str(i - head_max + 2) + "]", size=size_tx, font=font_tx, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(head_max, send_col_num)])
		# Make Values
		self._layout_send_data = []
		for idx, resp in enumerate(self._send_data):
			# GUI処理
			# Add empty list
			self._layout_send_data.append([])
			# Add Button col
			self._layout_send_data[idx].append(sg.Button("Send", size=size_btn, font=font_btn, key=("btn_send",idx)))
			# Add Name col
			self._layout_send_data[idx].append(sg.Text(resp[0], size=size_name, font=font_name))
			# Add resp data col
			self._layout_send_data[idx].extend([sg.Input( format(byte,"02X"), size=size_tx, font=font_tx, key=("send",idx,i), enable_events=False) for i,byte in enumerate(resp[1])])
			# Add empty data col
			begin = len(resp[1])
			end = resp[2]
			self._layout_send_data[idx].extend([sg.Input( "", size=size_tx, font=font_tx, key=("send",idx,i), enable_events=False) for i in range(begin, end)])


	def _auto_response_update(self) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# self._autoresp_data を書き換え
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		for i,autoresp in enumerate(self._autoresp_data):
			# GUIから設定値を取得
			resp_data = []
			for j in range(0, len(autoresp[2])):
				# 入力テキストをゼロ埋めで2桁にする
				data = self._window[(i, j)].Get().zfill(2)
				# 16進数文字列でなかったら 00 に強制置換
				if hex_ptn.match(data) is None:
					data = "00"
				resp_data.append(data)
			autoresp[2] = bytes.fromhex(''.join(resp_data))
		# FCC処理
		self._auto_response_update_fcc()
		# GUI更新
		self._auto_response_update_gui()
		# SerialManagaerに通知
		self._serial.autoresp_update(self._autoresp_data)

	def _auto_response_update_fcc(self):
		# FCC処理
		for resp in self._autoresp_data:
			# FCC位置が-1ならスキップ
			fcc_pos = resp[4]
			if fcc_pos != -1:
				# FCC計算
				fcc = 0
				fcc_begin = resp[5]
				fcc_end = resp[6]
				fcc = self._calc_fcc(resp[2], fcc_begin, fcc_end+1, fcc_pos)
				# FCC挿入
				resp_len = len(resp[2])
				if resp_len-1 < fcc_pos:
					# 挿入位置が応答データサイズを超える場合、バッファを追加する
					# 挿入位置が応答データ長+1を超える場合はゼロ埋めする
					for i in range(resp_len, fcc_pos):
						resp[2] += (b'\0')
					resp[2] += (fcc.to_bytes(1, 'little'))
				else:
					# 挿入位置が応答データサイズ未満のときは既存バッファを書き換える
					temp = bytearray(resp[2])
					temp[fcc_pos] = fcc
					resp[2] = bytes(temp)

	def _auto_response_update_gui(self):
		for i, resp in enumerate(self._autoresp_data):
			for j, byte in enumerate(resp[2]):
				self._window[(i, j)].Update(value=format(byte, "02X"))

	def _req_send_bytes(self, idx:int) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# self._send を書き換え
		hex_ptn = re.compile(r'[0-9a-fA-F]{2}')
		# GUIから設定値を取得
		send_data = []
		for i in range(0, self._send_data[idx][2]):
			# 入力テキストをゼロ埋めで2桁にする
			data = self._window[("send", idx, i)].Get().zfill(2)
			# 16進数文字列でなかったら 00 に強制置換
			if hex_ptn.match(data) is None:
				data = "00"
			send_data.append(data)
		# データが有効なときだけ送信処理
		if len(send_data) > 0:
			self._send_data[idx][1] = bytes.fromhex(''.join(send_data))
			# FCC処理
			self._send_update_fcc(idx)
			# GUI更新
			self._send_update_gui(idx)
			# SerialManagaerに通知
			if self._notify_to_serial.full():
				print("Queue is full, send req denied.")
			else:
				self._notify_to_serial.put([serial_mng.ThreadNotify.TX_BYTES, self._send_data[idx][1], self._send_data[idx][0]])

	def _send_update_fcc_all(self):
		# FCC処理
		for i, resp in enumerate(self._send_data):
			self._send_update_fcc(i)

	def _send_update_fcc(self, idx:int):
		# FCC処理
		resp = self._send_data[idx]
		# FCC位置が-1ならスキップ
		fcc_pos = resp[3]
		if fcc_pos != -1:
			# FCC計算
			fcc = 0
			fcc_begin = resp[4]
			fcc_end = resp[5]
			fcc = self._calc_fcc(resp[1], fcc_begin, fcc_end+1, fcc_pos)
			# FCC挿入
			resp_len = len(resp[1])
			if resp_len-1 < fcc_pos:
				# 挿入位置が応答データサイズを超える場合、バッファを追加する
				# 挿入位置が応答データ長+1を超える場合はゼロ埋めする
				for i in range(resp_len, fcc_pos):
					resp[1] += (b'\0')
				resp[1] += (fcc.to_bytes(1, 'little'))
			else:
				# 挿入位置が応答データサイズ未満のときは既存バッファを書き換える
				temp = bytearray(resp[1])
				temp[fcc_pos] = fcc
				resp[1] = bytes(temp)

	def _send_update_gui(self, idx:int):
		for i,byte in enumerate(self._send_data[idx][1]):
			self._window[("send", idx, i)].Update(value=format(byte, "02X"))

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

		self._autoresp_caption = [
			"[自動応答データ設定]", "", "応答データ"
		]
		self._autoresp_head = [
			"Name", "Recv", "ST", "XX", "XX", "XX", "XX", "YY"
		]
		self._autoresp_data = [
				# 応答			# 自動応答対象					# 応答データ定義							# FCC定義(idx=0開始, 挿入位置=-1でFCC設定無効)
				# 名称			# 受信データパターン			# 送信HEX						# サイズ	# 挿入位置	# 計算開始位置	# 計算終了位置
			[	"Test1",		hex('ABCDEF0102'),				hex('aaBBccDDeeFF'),			18,			6,			2,				4,					],
			[	"Test2",		hex('ABCD0102'),				hex('aa00bb11cc22dd33ee44'),	18,			12,			6,				7,					],
			[	"Test3",		hex('ABCD0102'),				hex('aa00bb11cc22dd33ee44'),	18,			-1,			0,				9,					],
		]

	def _send_settings(self) -> None:
		hex = self._hex2bytes

		self._send_caption = [
			"[送信データ設定]", "送信データ",
		]
		self._send_head = [
			"Name", "ST", "XX", "XX", "XX", "XX", "YY"
		]
		self._send_data = [
				# 送信設定			# 手動送信データ定義					# FCC定義(idx=0開始)
				# 名称				# 送信HEX					#サイズ		# 挿入位置	# 計算開始位置	# 計算終了位置
			[	"Manual",			hex(''),					18,			17,			4,				7,				],
			[	"TestSend1",		hex('00112233'),			-1,			4,			0,				3,				],
			[	"TestSend2",		hex('00'),					5,			-1,			0,				3,				],
			[	"TestSend3",		hex(''),					0,			-1,			0,				3,				],
		]

if __name__=="__main__":
	try:
		gui = gui_manager()
		gui.exe()
	except:
		import traceback
		traceback.print_exc()
	

