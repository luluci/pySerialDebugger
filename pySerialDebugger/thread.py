import enum
import queue
from typing import Callable
from . import autoresp
from pySerialDebugger.autosend import autosend_result
from pySerialDebugger.send_node import send_data_node

class ThreadNotify(enum.Enum):
	"""
	スレッド間通信メッセージ
	"""
	# GUIへの通知
	RECV_ANALYZE = enum.auto()				# 受信解析結果通知
	COMMIT_RX = enum.auto()					# 受信バッファ出力
	PUSH_RX = enum.auto()					# 受信データをバッファに追加
	COMMIT_TX = enum.auto()					# 自動応答データを出力
	DISCONNECTED = enum.auto()				# シリアル切断
	AUTORESP_UPDATE_FIN = enum.auto()		# 自動応答データ更新完了
	# Serialへの通知
	TX_BYTES = enum.auto()					# シリアル送信(手動)
	AUTORESP_UPDATE = enum.auto()			# 自動応答データ更新
	EXIT_TASK = enum.auto()					# シリアルタスク終了



class serial_msg:
	"""
	シリアル通信スレッドが作成するメッセージ
	"""

	def __init__(self) -> None:
		self.notify: ThreadNotify = None
		self.id: str = None
		self.data: bytes = None
		self.timestamp: int = None
		self.result: autoresp.analyze_result = None
		self.as_result: autosend_result = None

	def autoresp_updated(self):
		self.notify = ThreadNotify.AUTORESP_UPDATE_FIN

	def autoresp_disconnected(self):
		self.notify = ThreadNotify.DISCONNECTED

	def send(self, result: autosend_result):
		"""
		手動送信実施完了通知
		"""
		self.notify = ThreadNotify.COMMIT_TX
		self.as_result = result

	def recv_analyze(self, result: autoresp.analyze_result):
		self.notify = ThreadNotify.RECV_ANALYZE
		self.result = result


class gui_msg:
	"""
	メインスレッドが作成するメッセージ
	"""

	def __init__(self) -> None:
		self.notify: ThreadNotify = None
		self.cb: Callable[[None], None] = None
		self.id: str = None
		self.data: bytes = None
		node: send_data_node = None

	def autoresp_update(self, cb):
		self.notify = ThreadNotify.AUTORESP_UPDATE
		self.cb = cb

	def send(self, node: send_data_node):
		self.notify = ThreadNotify.TX_BYTES
		self.node = node


class hdlr_msg:
	"""
	管理スレッドが作成するメッセージ
	"""

	def __init__(self) -> None:
		self.notify: ThreadNotify = None



class msg_manager:
	def __init__(self) -> None:
		# メッセージ通知用キュー
		### from シリアル通信スレッド
		# 処理通知
		self.q_serial2hdlr_msg = queue.Queue(10)
		### from 管理スレッド
		# 処理通知
		# None
		### from メインスレッド(GUI)
		# 終了通知
		self.q_gui2serial_exit = queue.Queue(10)
		self.q_gui2hdlr_exit = queue.Queue(10)
		# 処理通知
		self.q_gui2serial_msg = queue.Queue(10)
		self.q_gui2hdlr_msg = queue.Queue(10)
		# なし

	"""
	Exit通知
	"""
	def notify_exit_serial(self):
		self.q_gui2serial_exit.put(True)

	def notify_exit_hdlr(self):
		self.q_gui2hdlr_exit.put(True)

	def has_exit_serial(self):
		return not self.q_gui2serial_exit.empty()

	def has_exit_hdlr(self):
		return not self.q_gui2hdlr_exit.empty()

	def clear_exit_serial(self):
		# queueを空にしておく
		while not self.q_gui2serial_exit.empty():
			self.q_gui2serial_exit.get_nowait()

	def clear_exit_hdlr(self):
		# queueを空にしておく
		while not self.q_gui2hdlr_exit.empty():
			self.q_gui2hdlr_exit.get_nowait()

	"""
	シリアル通信スレッドへ通知
	"""

	def clear_notify_serial(self):
		# queueを空にしておく
		while not self.q_gui2serial_msg.empty():
			self.q_gui2serial_msg.get_nowait()

	def is_full_notify_serial(self):
		return self.q_gui2serial_msg.full()

	def has_notify_serial(self):
		return not self.q_gui2serial_msg.empty()

	def get_notify_serial(self) -> gui_msg:
		return self.q_gui2serial_msg.get_nowait()

	def notify_serial_autoresp_update(self, cb:Callable[[None], None]):
		"""
		シリアル通信スレッドへ自動応答データ設定の更新を通知する
		シリアル通信スレッド側で更新をかけることで排他を実施する
		"""
		# メッセージ作成
		new_msg = gui_msg()
		new_msg.autoresp_update(cb)
		# メッセージ送信
		self.q_gui2serial_msg.put(new_msg, block=True, timeout=None)

	def notify_serial_send(self, node: send_data_node):
		# メッセージ作成
		new_msg = gui_msg()
		new_msg.send(node)
		# メッセージ送信
		self.q_gui2serial_msg.put(new_msg, block=True, timeout=None)

	"""
	管理制御スレッドへ通知
	"""

	def clear_notify_serial2hdrl(self):
		# queueを空にしておく
		while not self.q_serial2hdlr_msg.empty():
			self.q_serial2hdlr_msg.get_nowait()

	def has_notify_serial2hdrl(self):
		return not self.q_serial2hdlr_msg.empty()

	def get_notify_serial2hdrl(self) -> serial_msg:
		return self.q_serial2hdlr_msg.get_nowait()


	def notify_hdlr_autoresp_updated(self):
		# メッセージ作成
		new_msg = serial_msg()
		new_msg.autoresp_updated()
		# メッセージ送信
		self.q_serial2hdlr_msg.put(new_msg, block=True, timeout=None)

	def notify_hdlr_autoresp_disconnected(self):
		# メッセージ作成
		new_msg = serial_msg()
		new_msg.autoresp_disconnected()
		# メッセージ送信
		self.q_serial2hdlr_msg.put(new_msg, block=True, timeout=None)

	def notify_hdlr_send(self, result:autosend_result):
		# メッセージ作成
		new_msg = serial_msg()
		new_msg.send(result)
		# メッセージ送信
		self.q_serial2hdlr_msg.put(new_msg, block=True, timeout=None)

	def notify_hdlr_recv_analyze(self, result: autoresp.analyze_result):
		# メッセージ作成
		new_msg = serial_msg()
		new_msg.recv_analyze(result)
		# メッセージ送信
		self.q_serial2hdlr_msg.put(new_msg, block=True, timeout=None)


messenger = msg_manager()
