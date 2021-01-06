import time
import concurrent.futures
from typing import Union, List
import PySimpleGUI as sg
from . import serial_mng
from multiprocessing import Value
import queue

class gui_manager:
	DISCONNECTED, DISCONNECTING, CONNECTED, CONNECTING = (1,2,3,4)
	
	def __init__(self) -> None:
		# Serial Info
		self._serial = serial_mng.serial_manager()
		# Window Info
		self._window: sg.Window = None
		self._gui_font = ('Consolas', 11)
		self._init_com()
		self._init_window()
		self._init_event()
		self._gui_conn_state = self.DISCONNECTED

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
		self._font_family = 'Consolas'
		leyout_serial_connect = [
			sg.Text("SerialDebug Tool..."),
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
			self._layout_autoresp_head,
			*self._layout_autoresp_data
		]
		layout_serial_auto_resp_column = [
			[sg.Column(layout_serial_auto_resp, scrollable=True, vertical_scroll_only=False, size=(1100, 150))],
			[sg.Button("Update", key="btn_autoresp_update", size=(15, 1), enable_events=True)],
		]
		# Define: log View
		layout_serial_log_col = [
			[sg.Text("[TxRx]"), sg.Text("CommData", size=(40,1)), sg.Text("(Detail)")]
		]
		layout_serial_log_caption = [
			sg.Column(layout_serial_log_col, scrollable=False, size=(750, 20))
		]
		layout_serial_log = [
			sg.Output(size=(130, 10), echo_stdout_stderr=True, font=self._gui_font)
		]
		layout = [
			[*leyout_serial_connect, sg.Frame("Status:", [layout_serial_status])],
			[sg.Frame("Serial Settings:", [layout_serial_settings])],
			[sg.Text("Auto Response:")],
			[sg.Frame("Auto Response Settings:", layout_serial_auto_resp_column)],
			[sg.Text("Log:")],
			[*layout_serial_log_caption],
			[*layout_serial_log],
		]
		self._window = sg.Window("test window.", layout, finalize=True)

	def _init_event(self) -> None:
		# clear events
		self._events = {
			# Exit
			None: self._hdl_exit,
			# Button: Connect
			"btn_connect": self._hdl_btn_connect,
			"btn_autoresp_update": self._hdl_btn_autoresp_update,
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
				self._future_serial = self._executer.submit(self._serial.connect, self._exit_flag_serial_mng, self._serial_notify)
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
				self._exit_flag_serial_mng.put(True)
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

	def exe(self):
		# スレッド管理
		self._future_comm_hdle = None
		self._future_serial = None
		# スレッド間通信用キュー
		self._exit_flag_serial_mng = queue.Queue(10)
		self._exit_flag_comm_hdle = queue.Queue(10)
		self._serial_notify = queue.Queue(10)
		self._comm_hdle_notify = queue.Queue(10)
		# (1) Windows イベントハンドラ
		# (2) シリアル通信
		# (3) シリアル通信->送受信->GUI
		# の3スレッドで処理を実施する
		self._executer = concurrent.futures.ThreadPoolExecutor(max_workers=3)
		self._future_comm_hdle = self._executer.submit(self.comm_hdle, self._exit_flag_comm_hdle, self._serial_notify, self._comm_hdle_notify)
		#self._future_serial = self._executer.submit(self._serial.connect, self._exit_flag_serial_mng, self._serial_notify)
		self.wnd_proc()
		self._executer.shutdown()

	def wnd_proc(self):
		while True:
			event, values = self._window.read()

			if event in self._events:
				self._events[event](values)
			if event is None:
				# 各スレッドに終了通知
				self._exit_flag_serial_mng.put(True)
				self._exit_flag_comm_hdle.put(True)
				# queueを空にしておく
				while not self._serial_notify.empty():
					self._serial_notify.get_nowait()
				break
		print("Exit: wnd_proc()")

	def comm_hdle(self, exit_flag: queue.Queue, serial_notify: queue.Queue, self_notify: queue.Queue):
		self.log_str = ""
		self.log_pos = 0
		try:
			while exit_flag.empty():
				if not serial_notify.empty():
					# queueからデータ取得
					notify, data, autoresp_name = serial_notify.get_nowait()
					# 通知に応じて処理実施
					if notify == serial_mng.ThreadNotify.PUSH_RX_BYTE:
						# ログバッファに受信データを追加
						# ログ出力は実施しない
						self.log_str += data.hex()
					elif notify == serial_mng.ThreadNotify.PUSH_RX_BYTE_AND_COMMIT:
						# ログバッファに受信データを追加
						self.log_str += data.hex()
						# ログ出力
						self.comm_hdle_log_output("RX", self.log_str, autoresp_name)
						# バッファクリア
						self.log_str = ""
					elif notify == serial_mng.ThreadNotify.COMMIT_AND_PUSH_RX_BYTE:
						# ログ出力
						self.comm_hdle_log_output("RX", self.log_str, autoresp_name)
						# バッファクリア
						self.log_str = ""
						# ログバッファに受信データを追加
						self.log_str += data.hex()
					elif notify == serial_mng.ThreadNotify.COMMIT_TX_BYTES:
						# 送信データをログ出力
						self.comm_hdle_log_output("TX", data.hex(), autoresp_name)
					elif notify == serial_mng.ThreadNotify.DISCONNECTED:
						# GUIスレッドに切断を通知
						# self_notify.put(True)
						# スレッドセーフらしい
						self._window.write_event_value("_swe_disconnected", "")
					else:
						pass
				#print("Run: serial_hdle()")
				time.sleep(0.05)
			print("Exit: serial_hdle()")
		except:
			import traceback
			traceback.print_exc()

	def comm_hdle_log_output(self, rxtx:str, data:str, detail:str):
		if detail == "":
			log_temp = "[{0:2}]   {1:40}".format(rxtx, data)
		else:
			log_temp = "[{0:2}]   {1:40} ({2})".format(rxtx, data, detail)
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
				resp_len_max = resp[3]
		# GUIパーツ定義
		font = (self._font_family, 8)
		di_size = (5, 1)
		# Make Header
		# Name,Recvは固定とする
		# ヘッダ定義がデータ最大に足りなかったら穴埋めする
		head_max = len(self._autoresp_head)
		self._layout_autoresp_head = [sg.Text(self._autoresp_head[i], size=(10,1)) for i in range(0, 2)]
		self._layout_autoresp_head.extend([sg.Input(self._autoresp_head[i], size=di_size, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(2, head_max)])
		if head_max < resp_len_max:
			head_suffix = self._autoresp_head[head_max-1]
			self._autoresp_head[head_max-1] = head_suffix + "[1]"
			#layout_serial_auto_resp = [sg.Input(size=(10, 1), pad=(1, 1), justification='right', key=(1, j)) for j in range(10)]
			self._layout_autoresp_head.extend( [sg.Input(head_suffix + "[" + str(i - head_max + 2) + "]", size=di_size, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(head_max, resp_len_max)])
		# Make Values
		self._layout_autoresp_data = []
		for resp in self._autoresp_data:
			# GUI処理
			# Add empty list
			self._layout_autoresp_data.append([])
			idx = len(self._layout_autoresp_data) - 1
			# Add Name,Recv col
			self._layout_autoresp_data[idx].extend([sg.Text(resp[i], size=(10,1)) for i in range(0, 2)])
			# Add resp data col
			self._layout_autoresp_data[idx].extend([sg.Input( format(byte,"02X"), size=di_size, key=(idx,i), enable_events=True) for i,byte in enumerate(resp[2])])
			# Add empty data col
			begin = len(resp[2])
			end = resp[3]
			self._layout_autoresp_data[idx].extend([sg.Input( "", size=di_size, key=(idx,i), enable_events=True) for i in range(begin, end)])

	def _auto_response_update(self) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# self._autoresp_data を書き換え
		for i,autoresp in enumerate(self._autoresp_data):
			resp_data = [self._window[(i, j)].Get() for j in range(0, len(autoresp[2]))]
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
			fcc = 0
			if resp[4] != -1:
				for i, byte in enumerate(resp[2]):
					if i != resp[4]-1:
						fcc += byte
			fcc = ((fcc % 256) ^ 0xFF) + 1
			if len(resp[2]) < resp[4]:
				for i in range(len(resp[2])+1, resp[4]):
					resp[2] += (b'\0')
				resp[2] += (fcc.to_bytes(1, 'little'))
			else:
				temp = bytearray(resp[2])
				temp[resp[4]-1] = fcc
				resp[2] = bytes(temp)

	def _auto_response_update_gui(self):
		for i, resp in enumerate(self._autoresp_data):
			for j, byte in enumerate(resp[2]):
				self._window[(i, j)].Update(value=format(byte, "02X"))


	def _hex2bytes(self, hex: str) -> bytes:
		return bytes.fromhex(hex)


	def _auto_response_settings(self) -> None:
		"""
		Auto Response Settings
		自動応答の定義はここを編集する
		"""
		hex = self._hex2bytes

		self._autoresp_head = [
			"Name", "Recv", "ST", "XX", "XX", "XX", "XX", "YY"
		]
		self._autoresp_data = [
				# 応答名称		# 自動応答対象受信データ		# 応答データ					# 応答データサイズ		# FCC位置
			[	"Test1",		hex('ABCDEF0102'),				hex('aaBBccDDeeFF'),			18,						7			],
			[	"Test2",		hex('ABCD0102'),				hex('aa00bb11cc22dd33ee44'),	18,						11			],
		]

if __name__=="__main__":
	try:
		gui = gui_manager()
		gui.exe()
	except:
		import traceback
		traceback.print_exc()
	

