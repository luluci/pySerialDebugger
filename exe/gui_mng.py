import time
import concurrent.futures
from typing import Union, List
import PySimpleGUI as sg
import lib.PySimpleGUIHelper as sgh
import serial_mng
from multiprocessing import Value
import queue

class gui_manager:
	
	def __init__(self) -> None:
		# Serial Info
		self._serial = serial_mng.serial_manager()
		# Window Info
		self._window: sg.Window = None
		self._init_com()
		self._init_window()
		self._init_event()

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
			[sg.Column(layout_serial_auto_resp, scrollable=True, vertical_scroll_only=True, size=(750, 100))],
			[sg.Button("Update", key="btn_autoresp_update", size=(15, 1), enable_events=True)],
		]
		# Define: log View
		layout_serial_log = [
			sg.Table([ ["","",""] ], ["Dir", "HEX", "Analyze"], key="table_log", num_rows=20, col_widths=[3,20,60], auto_size_columns=False),
		]
		layout = [
			[*leyout_serial_connect, sg.Frame("Status:", [layout_serial_status])],
			[sg.Frame("Serial Settings:", [layout_serial_settings])],
			[sg.Text("Auto Response:")],
			[sg.Frame("Auto Response Settings:", layout_serial_auto_resp_column)],
			[sg.Text("Log:")],
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
		print("Button Pushed!")
		if self._serial.is_open():
			self._serial_close()
			self._conn_btn_hdl.Update(text="Connect")
			self._conn_status_hdl.Update(value="---")
		else:
			if self._serial_connect():
				self._conn_btn_hdl.Update(text="Disconnect")
				self._conn_status_hdl.Update(value=self._get_com_info())
			else:
				self._conn_status_hdl.Update(value="Serial Open Failed.")

	def _hdl_btn_autoresp_update(self, values):
		self._auto_response_update()

	def exe(self):
		# (1) Windows イベントハンドラ
		# (2) シリアル通信
		# (3) シリアル通信->送受信->GUI
		# の3スレッドで処理を実施する
		with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executer:
			exit_flag = queue.Queue(10)
			recv_data = queue.Queue(10)
			resp_data = queue.Queue(10)
			#executer.submit(self.wnd_proc, exit_flag)
			executer.submit(self._serial.connect, exit_flag, recv_data, resp_data)
			executer.submit(self.serial_hdle, exit_flag, recv_data, resp_data)
			self.wnd_proc(exit_flag)

	def wnd_proc(self, exit_flag: queue.Queue):
		while True:
			event, values = self._window.read()

			if event in self._events:
				self._events[event](values)
			if event is None:
				exit_flag.put(True)
				exit_flag.put(True)
				break
		print("Exit: wnd_proc()")

	def serial_hdle(self, exit_flag: queue.Queue, recv_data: queue.Queue, resp_data: queue.Queue):
		self.log_str = ""
		self.log_pos = 0
		log_wnd = self._window["table_log"]
		self._log = []
		try:
			while exit_flag.empty():
				if not recv_data.empty():
					data = recv_data.get(block=True, timeout=1)
					if isinstance(data, bytes):
						self.log_str += data.hex()
					else:
						self._log.append(["rcv", self.log_str, ""])
						self._window["table_log"].update(values=self._log)
						self.log_str = ""
				if not resp_data.empty():
					data = resp_data.get(block=True, timeout=1)
					if isinstance(data, bytes):
						self._log.append(["resp", data.hex(), ""])
						self._window["table_log"].update(values=self._log)
				#print("Run: serial_hdle()")
				time.sleep(0.05)
			print("Exit: serial_hdle()")
		except:
			import traceback
			traceback.print_exc()


	def close(self) -> None:
		if self._window:
			self._window.close()
		self._serial.close()

	def _serial_connect(self) -> bool:
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
		# GUIに落とし込む
		# AutoResp定義解析
		resp_len_max = 0
		for resp in self._autoresp_data:
			if len(resp[2]) > resp_len_max:
				resp_len_max = len(resp[2]) + 2
		# Make Header
		# Name,Recvは固定とする
		# ヘッダ定義がデータ最大に足りなかったら穴埋めする
		head_max = len(self._autoresp_head)
		self._layout_autoresp_head = [sg.Text(self._autoresp_head[i], size=(10,1)) for i in range(0, 2)]
		self._layout_autoresp_head.extend([sg.Input(self._autoresp_head[i], size=(6,1), disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(2, head_max)])
		if head_max < resp_len_max:
			head_suffix = self._autoresp_head[head_max-1]
			self._autoresp_head[head_max-1] = head_suffix + "[1]"
			#layout_serial_auto_resp = [sg.Input(size=(10, 1), pad=(1, 1), justification='right', key=(1, j)) for j in range(10)]
			self._layout_autoresp_head.extend( [sg.Input(head_suffix + "[" + str(i - head_max + 2) + "]", size=(6,1), disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color()) for i in range(head_max, resp_len_max)])
		# Make Values
		self._layout_autoresp_data = []
		for resp in self._autoresp_data:
			# Add empty list
			self._layout_autoresp_data.append([])
			idx = len(self._layout_autoresp_data) - 1
			# Add Name,Recv col
			self._layout_autoresp_data[idx].extend([sg.Text(resp[i], size=(10,1)) for i in range(0, 2)])
			# Add resp data col
			self._layout_autoresp_data[idx].extend([sg.Input( format(byte,"02X"), size=(6,1), key=(idx,i), enable_events=True) for i,byte in enumerate(resp[2])])

	def _auto_response_update(self) -> None:
		"""
		GUI上で更新された自動応答設定を反映する
		"""
		# self._autoresp_data を書き換え
		for i,autoresp in enumerate(self._autoresp_data):
			resp_data = [self._window[(i, j)].Get() for j in range(0, len(autoresp[2]))]
			autoresp[2] = bytes.fromhex(''.join(resp_data))
		# SerialManagaerに通知

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
			["Test1", hex('ABCDEF0102'), hex('aaBBccDDeeFF')],
			["Test2", hex('ABCD0102'), hex('aa00bb11cc22dd33ee44')]
		]

if __name__=="__main__":
	try:
		gui = gui_manager()
		gui.exe()
	except:
		import traceback
		traceback.print_exc()
	

