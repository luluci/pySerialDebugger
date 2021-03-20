
import PySimpleGUI as sg
from typing import Any, Callable, List, Dict

from .send_node import send_mng, send_data_node

class autosend_data:
	"""
	自動送信定義ノード
	"""
	# ノードタイプ
	SEND, WAIT, JUMP, EXIT = range(0, 4)
	# wait分解能
	MS, US, NS = range(0, 3)

	def __init__(self, type: int, id: str, wait: int, wait_unit: int, jump: int) -> None:
		self._node_type: int = type
		self._send_id: str = id
		self._send_ref: send_data_node = None
		self._wait_time: int = wait
		self._wait_unit: int = wait_unit
		self._jump_to: int = jump

	@classmethod
	def exit(cls):
		return autosend_data(autosend_data.EXIT, None, 0, None, None)

	@classmethod
	def send(cls, name: str):
		return autosend_data(autosend_data.SEND, name, 0, None, None)

	@classmethod
	def wait_ms(cls, wait: int):
		return autosend_data(autosend_data.WAIT, None, wait * 1000 * 1000, autosend_data.MS, None)

	@classmethod
	def wait_us(cls, wait: int):
		return autosend_data(autosend_data.WAIT, None, wait * 1000, autosend_data.US, None)

	@classmethod
	def jump(cls, jump: int):
		return autosend_data(autosend_data.JUMP, None, 0, None, jump)

	def get_gui(self, key, size, pad, font) -> Any:
		# タイプごとに処理
		text = ""
		if self._node_type == autosend_data.SEND:
			text = "send[" + self._send_id + "]"
		elif self._node_type == autosend_data.WAIT:
			time = 0
			unit = ""
			if self._wait_unit == autosend_data.MS:
				time = self._wait_time / (1000 * 1000)
				unit = "ms"
			elif self._wait_unit == autosend_data.US:
				time = self._wait_time / (1000)
				unit = "us"
			text = "wait[" + "{0}".format(time) + unit + "]"
		elif self._node_type == autosend_data.JUMP:
			text = "jump_to[" + "{0}".format(self._jump_to) + "]"
		elif self._node_type == autosend_data.EXIT:
			text = "exit"
		else:
			raise Exception("unknown node type detected!")
		# GUI作成
		return sg.Input(text, disabled=True, key=key, size=size, pad=pad, font=font, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())

	def set_send(self, s_mng:send_mng):
		# 送信データを設定する
		# 送信データIDチェック
		if self._send_id is not None:
			# check
			if self._send_id not in s_mng._send_data_dict.keys():
				# 送信対象定義名称が存在しない場合NG
				raise Exception("in AutoSend Settings, '" + self._send_id + "' send setting not exist.")
			# 送信データへの参照設定
			self._send_ref = s_mng._send_data_dict[self._send_id]

class autosend_list:
	"""
	GUI構築定義データ
	"""
	ENABLE = 0			# 有効無効設定
	ID = 1				# 自動送信データ定義名
	DATA = 2			# 自動送信データパターン


class autosend_node:
	# GUI情報
	gui_size = None
	gui_pad = None
	gui_font = None

	@classmethod
	def set_gui_info(cls, size, pad, font):
		cls.gui_size = size
		cls.gui_pad = pad
		cls.gui_font = font

	def __init__(self, autosend, mng: send_mng) -> None:
		# 送信データ定義参照
		self._send_mng = mng
		# ユーザ定義データ取得
		# デフォルトで無効にするか？　とりあえずなりゆき
		self.enable = autosend[autosend_list.ENABLE]
		self.id = autosend[autosend_list.ID]
		self.data_list: List[autosend_data] = autosend[autosend_list.DATA]
		self.data_size: int = len(self.data_list)
		# データ解析
		for data in self.data_list:
			data: autosend_data
			# データチェック
			if data._node_type == autosend_data.SEND:
				# 送信ノードのとき
				data.set_send(mng)
			elif data._node_type == autosend_data.JUMP:
				# ジャンプノードのとき
				if data._jump_to >= len(self.data_list):
					# Jump先が存在しない場合はNG
					raise Exception("in AutoSend Settings, jump to '" + "{0}".format(data._jump_to) + "'th node is not exist.")

	def get_gui(self, key: str, row: int):
		parts = []
		for col, data in enumerate(self.data_list):
			data: autosend_node
			if col != 0:
				parts.append(sg.Text(">>", size=(3, 1), font=autosend_node.gui_font))
			else:
				parts.append(sg.Text("", size=(1, 1)))
			parts.append(data.get_gui((key, row, col), autosend_node.gui_size, autosend_node.gui_pad, autosend_node.gui_font))
		return parts


class autosend_result:
	def __init__(self) -> None:
		# データ
		self.send_ref: send_data_node = None
		# フラグ
		self._send_data: bool = False
		self._wait_time: bool = False

	def set_send(self, node:send_data_node):
		self.send_ref = node
		self._send_data = True

	def set_wait(self):
		self._wait_time = True

	def is_send(self) -> bool:
		return self._send_data

class autosend_mng:
	_exit_cb: Callable[[int], None] = None
	_gui_update_cb: Callable[[int, int, int], None] = None

	def __init__(self, autosend, mng: send_mng) -> None:
		# コールバック
		self._send_cb: Callable[[bytes], None] = None
		# 送信データ定義への参照を設定
		self._send_mng = mng
		# 管理情報初期化
		self._active_node: autosend_node = None
		self._pos: int = 0
		self._timestamp: int = 0
		# nodeリスト
		self._data_list: List[autosend_node] = []
		self._data_dict: Dict[str, autosend_node] = {}

		# 自動送信データ定義ノードを解析
		enabled = False
		for i, data in enumerate(autosend):
			# 自動送信データ作成
			new_node = autosend_node(data, mng)
			# enableチェック
			if enabled:
				# すでにenableルールが出現していたら
				# 先優先で残りはすべてdisableに倒す
				new_node.enable = False
			else:
				# enableルール未出現なら、enable判定
				if new_node.enable:
					self._active_node = new_node
					enabled = True

			# データ登録
			self._data_list.append(new_node)
			if new_node.id not in self._data_dict.keys():
				self._data_dict[new_node.id] = new_node
			else:
				print("id[" + new_node.id + "] is duplicate. idx[" + str(i) + "] is ignored.")

	def set_send_cb(self, cb: Callable[[bytes], None]) -> None:
		self._send_cb = cb

	@classmethod
	def set_exit_cb(cls, cb: Callable[[int], None]) -> None:
		cls._exit_cb = cb

	@classmethod
	def set_gui_update_cb(cls, cb: Callable[[int, int, int], None]) -> None:
		cls._gui_update_cb = cb


	def start(self, idx: int) -> None:
		self.activate(self._data_list[idx])
		# GUI更新
		# autosend_mng._gui_update_cb(idx, None, self._pos)

	def end(self, idx: int) -> None:
		# GUI更新
		#autosend_mng._gui_update_cb(idx, self._pos, None)
		# パラメータ初期化
		# self._active_node = None
		# とりあえず有効設定はそのまま残しておく
		self.inactivate(self._data_list[idx])

	def stop(self):
		"""
		全停止する
		"""
		if self._active_node is not None:
			self._active_node.enable = False
			self._active_node = None

	def activate(self, node:autosend_node):
		"""
		指定のnodeで自動送信を有効化する
		"""
		# すでにアクティブなルールがあれば無効化する
		if self._active_node is not None:
			self._active_node.enable = False
		# 引数で指定されたノードを有効化
		node.enable = True
		# 参照設定
		self._active_node = node
		# パラメータ初期化
		self._pos = 0
		#self._timestamp = 0

	def inactivate(self, node: autosend_node):
		"""
		指定されたnodeの自動送信を無効化する。
		"""
		if self._active_node == node:
			self._active_node = None
		node.enable = False

	def running(self) -> bool:
		if self._active_node is not None:
			return True
		else:
			return False

	def run(self, idx: int, timestamp: int) -> autosend_result:
		# 処理結果情報初期化
		self._result = autosend_result()
		# 自動送信処理
		# スレッド間排他のために最初にノードを取り出しておく
		tgt_node = self._active_node
		if tgt_node is not None:
			tgt_data = tgt_node.data_list[self._pos]
			self._run_impl(tgt_node, tgt_data, timestamp)
		# 結果を返す
		return self._result

	def _run_impl(self, node: autosend_node, data: autosend_data, timestamp: int) -> None:
		node_type = data._node_type
		if node_type == autosend_data.SEND:
			self._run_impl_send(node, data, timestamp)
		elif node_type == autosend_data.WAIT:
			self._run_impl_wait(node, data, timestamp)
		elif node_type == autosend_data.JUMP:
			self._run_impl_jump(node, data, timestamp)
		elif node_type == autosend_data.EXIT:
			self._run_impl_exit(node)

	def _run_impl_send(self, node: autosend_node, data: autosend_data, timestamp: int) -> None:
		# タイムスタンプ更新
		self._timestamp = timestamp
		# 送信実行
		self._send_cb(data._send_ref.data_bytes)
		# 次のシーケンスへ遷移
		self._next(node)
		# 結果作成
		self._result.set_send(data._send_ref)

	def _run_impl_wait(self, node: autosend_node, data: autosend_data, timestamp: int) -> None:
		if self._timestamp == 0:
			# タイムスタンプ更新
			self._timestamp = timestamp
		else:
			# wait時間経過判定
			diff = timestamp - self._timestamp
			if diff >= data._wait_time:
				# タイムスタンプ初期化
				self._timestamp = timestamp
				self._next(node)
		# 結果作成
		self._result.set_wait()

	def _run_impl_jump(self, node: autosend_node, data: autosend_data, timestamp: int) -> None:
		# タイムスタンプ更新
		self._timestamp = timestamp
		# 指定のシーケンスへジャンプ
		self._set_pos(node, data._jump_to)

	def _run_impl_exit(self, node: autosend_node) -> None:
		#autosend_mng._exit_cb(idx)
		self.inactivate(node)

	def _next(self, node: autosend_node) -> None:
		idx_disable = self._pos
		self._pos += 1
		if self._pos >= node.data_size:
			self._pos = 0
		idx_enable = self._pos
		# GUI更新
		# autosend_mng._gui_update_cb(idx, idx_disable, idx_enable)

	def _set_pos(self, node: autosend_node, pos: int) -> None:
		idx_disable = self._pos
		self._pos = pos
		if self._pos >= node.data_size:
			self._pos = 0
		idx_enable = self._pos
		# GUI更新
		# autosend_mng._gui_update_cb(idx, idx_disable, idx_enable)
