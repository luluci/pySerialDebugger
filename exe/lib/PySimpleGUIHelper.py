import sys
import ctypes
import PySimpleGUI as sg

from ctypes import cast, c_int
from ctypes.wintypes import HWND, UINT, WPARAM, LPARAM, BOOL, LPWSTR, LONG, INT

"""
WindowsAPI
"""
# Type define
LRESULT = ctypes.c_void_p
HDROP = ctypes.c_void_p
LONG_PTR = ctypes.c_void_p
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, UINT, WPARAM, LPARAM)
WM_DROPFILES = 0x0233
WM_NOTIFY = 0x004E
GWL_WNDPROC = -4
GWL_STYLE = -16
LVS_EDITLABELS = 0x0200
# API define
Buffer = ctypes.create_unicode_buffer
DragAcceptFiles = ctypes.windll.shell32.DragAcceptFiles
DragAcceptFiles.argtypes = [HWND, BOOL]
DragQueryFile = ctypes.windll.shell32.DragQueryFileW
DragQueryFile.restype = UINT
DragQueryFile.argtypes = [HDROP, UINT, LPWSTR, UINT]
DragFinish = ctypes.windll.shell32.DragFinish
DragFinish.argtypes = [HDROP]
CallWindowProc = ctypes.windll.user32.CallWindowProcW
CallWindowProc.restype = LRESULT
CallWindowProc.argtypes = [ctypes.c_void_p, HWND, UINT, WPARAM, LPARAM]
try:
	GetWindowLong = ctypes.windll.user32.GetWindowLongPtrW
	GetWindowLong.restype = LONG_PTR
	GetWindowLong.argtypes = [HWND, c_int]
except AttributeError:
	GetWindowLong = ctypes.windll.user32.GetWindowLongW
	GetWindowLong.restype = LONG
	GetWindowLong.argtypes = [HWND, c_int]
try:
	SetWindowLong = ctypes.windll.user32.SetWindowLongPtrW
	SetWindowLong.restype = LONG_PTR
	SetWindowLong.argtypes = [HWND, c_int, LONG_PTR]
except AttributeError:
	SetWindowLong = ctypes.windll.user32.SetWindowLongW
	SetWindowLong.restype = LONG
	SetWindowLong.argtypes = [HWND, c_int, LONG]
GetDlgCtrlID = ctypes.windll.user32.GetDlgCtrlID
GetDlgCtrlID.restype = INT
GetDlgCtrlID.argtypes = [HWND]


class adapt_dad:
	__hwnd_dict = {}

	def __init__(self, sg_wnd: sg.Window, cb) -> None:
		# PySimpleGUIのD&Dを有効にするWindowへの参照を格納
		self.wnd = sg_wnd
		# デフォルトプロシージャを初期化
		self.winproc_org = None
		# ドラッグアンドドロップを処理できるウィンドウプロシージャを作成
		self.__wnd_proc = WNDPROC(adapt_dad.wnd_proc)
		# コールバック登録
		self.cb = cb
		#
		self.adapt()

	def adapt(self) -> None:
		#=== ドラッグアンドドロップイベントを取得させるようにする。===
		#ハンドラの取得
		hwnd = self.wnd.Widget.winfo_id()
		#ウィンドウがドラッグアンドドロップを認識できるようにする。
		DragAcceptFiles(hwnd, True)
		#ウィンドウプロシージャを取得
		self.winproc_org = GetWindowLong(hwnd, GWL_WNDPROC)
		#ウィンドウプロシージャを追加
		SetWindowLong(hwnd, GWL_WNDPROC, self.__wnd_proc)
		#hWndとクラスインスタンスをひもづけ
		adapt_dad.__hwnd_dict[hwnd] = self

	def default_proc(self, hwnd, msg, wp, lp) -> LRESULT:
		"""
		デフォルトプロシージャをコールする
		"""
		return CallWindowProc(self.winproc_org, hwnd, msg, wp, lp)

	def callback(self, dropname: str) -> str:
		return self.cb(dropname)

	@staticmethod
	def wnd_proc(hwnd, msg, wp, lp) -> LRESULT:
		"""
		WinProcのプロトタイプ
		ファイルのドラッグアンドドロップイベント(WM_DROPFILES)を検出して、
		ドロップされたファイルを保存する。
		ここでウィンドウ(tk)を使用するとハングアップするのでデータ保存だけ行う。
		"""
		# アダプタインスタンスを取得
		py_inst = adapt_dad.__hwnd_dict[hwnd]
		# イベント処理
		if msg == WM_DROPFILES:
			DragQueryFile(wp, -1, None, 0)
			buf = Buffer(260)
			DragQueryFile(wp, 0, buf, ctypes.sizeof(buf))
			#dropname = buf.value.decode(sys.getfilesystemencoding())
			dropname = buf.value
			DragFinish(wp)
			py_inst.callback(dropname)
		# デフォルトプロシージャコール
		return py_inst.default_proc(hwnd, msg, wp, lp)


class adapt_lv_editable:
	__hwnd_dict = {}

	def __init__(self, sg_wnd: sg.Window, cb) -> None:
		# adapt対象とするPySimpleGUIのWindowへの参照を格納
		self.wnd = sg_wnd
		# デフォルトプロシージャを初期化
		self.winproc_org = None
		# ドラッグアンドドロップを処理できるウィンドウプロシージャを作成
		self.__wnd_proc = WNDPROC(adapt_lv_editable.wnd_proc)
		# コールバック登録
		self.cb = cb
		#
		self.adapt()

	def adapt(self) -> None:
		#=== ドラッグアンドドロップイベントを取得させるようにする。===
		#ハンドラの取得
		hwnd = self.wnd.Widget.winfo_id()
		self.hwnd = hwnd
		self.hctrl = None
		# GWL_STYLE に LVS_EDITLABELS を追加
		style = GetWindowLong(hwnd, GWL_STYLE)
		style |= LVS_EDITLABELS
		SetWindowLong(hwnd, GWL_STYLE, style)
		#ウィンドウプロシージャを取得
		self.winproc_org = GetWindowLong(hwnd, GWL_WNDPROC)
		#ウィンドウプロシージャを追加
		SetWindowLong(hwnd, GWL_WNDPROC, self.__wnd_proc)
		#hWndとクラスインスタンスをひもづけ
		adapt_lv_editable.__hwnd_dict[hwnd] = self

	def default_proc(self, hwnd, msg, wp, lp) -> LRESULT:
		"""
		デフォルトプロシージャをコールする
		"""
		return CallWindowProc(self.winproc_org, hwnd, msg, wp, lp)

	def callback(self, dropname: str) -> str:
		return self.cb(dropname)

	@staticmethod
	def wnd_proc(hwnd, msg, wp, lp) -> LRESULT:
		"""
		WinProcのプロトタイプ
		ファイルのドラッグアンドドロップイベント(WM_DROPFILES)を検出して、
		ドロップされたファイルを保存する。
		ここでウィンドウ(tk)を使用するとハングアップするのでデータ保存だけ行う。
		"""
		# アダプタインスタンスを取得
		py_inst: adapt_lv_editable
		py_inst = adapt_lv_editable.__hwnd_dict[hwnd]
		# イベント処理
		if msg == WM_NOTIFY:
			py_inst.hctrl = GetDlgCtrlID(hwnd)
			if wp == py_inst.hctrl:
				print("List Edit!")
		# デフォルトプロシージャコール
		return py_inst.default_proc(hwnd, msg, wp, lp)



"""
Test
"""
if __name__ == "__main__":
	try:
		print("ModuleTest:")
		sg.theme("Dark Blue 3")
		layout = [
			[sg.Text("Test GUI.")],
			[sg.InputText(key="input_text", default_text="hoge")]
		]
		window = sg.Window("test window.", layout, finalize=True)
		cb_func = lambda dn: print("D&D accepted! Get: " + dn)
		adapt1 = adapt_dad(window["input_text"], cb_func)
		while True:
			event, values = window.read()
			if event is None:
				print("exit")
				break
		window.close()
	except Exception as e:
		print(e)
