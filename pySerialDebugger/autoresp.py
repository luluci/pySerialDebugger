import enum
from typing import List, Dict
import PySimpleGUI as sg

class autoresp_data:
	"""
	自動応答対象受信データパターン定義用ノード
	"""
	gui_size = None
	gui_pad = None
	gui_font = None

	# node_type
	class TYPE(enum.Enum):
		BYTE = enum.auto()
		ANY = enum.auto()
	
	def __init__(self, type:TYPE, size:int, value:bytes) -> None:
		# node_type
		self.type = type
		# データサイズ(bit長)
		self.size = size
		# bytes
		self.value = value

	@classmethod
	def byte(cls, hex: str):
		# size check
		size = len(hex)
		if size % 2 == 1:
			raise Exception("param is not hex format.")
		# インスタンス作成
		return autoresp_data(autoresp_data.TYPE.BYTE, size/2*8, bytes.fromhex(hex))

	@classmethod
	def any(cls, bit_size:int):
		# インスタンス作成
		return autoresp_data(autoresp_data.TYPE.ANY, bit_size, None)

	@classmethod
	def set_gui_info(cls, size, pad, font):
		cls.gui_size = size
		cls.gui_pad = pad
		cls.gui_font = font

	def get_gui(self, key:str, row:int, col:int):
		if self.type == autoresp_data.TYPE.BYTE:
			return self._get_gui_byte(key,row,col)
		elif self.type == autoresp_data.TYPE.ANY:
			return self._get_gui_any(key, row, col)
		else:
			raise Exception("unknown type detected: " + str(self.type))

	def _get_gui_byte_closure(self, key: str, row: int, col: int, byte_size:int):
		#
		gui_form = "0" + format(byte_size * 2) + "X"
		size = (self.gui_size[0] * byte_size, autoresp_data.gui_size[1])
		pad = autoresp_data.gui_pad
		font = autoresp_data.gui_font
		#
		def get(idx:int, data:int):
			gui_key = (key,row, col+idx)
			return sg.Input(format(data, gui_form), key=gui_key, size=size, pad=pad, font=font, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())
		#
		return get

	def _get_gui_any_closure(self, key: str, row: int, col: int, byte_size:int):
		#
		size = (self.gui_size[0] * byte_size, autoresp_data.gui_size[1])
		pad = autoresp_data.gui_pad
		font = autoresp_data.gui_font
		#
		def get(idx:int, data:str):
			gui_key = (key,row, col+idx)
			return sg.Input(data, key=gui_key, size=size, pad=pad, font=font, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())
		#
		return get

	def _get_gui_byte(self, key: str, row: int, col: int):
		# クロージャ作成
		get = self._get_gui_byte_closure(key, row, col, 1)
		# GUIリストを作成して返す
		return [get(i,data) for i, data in enumerate(self.value)]

	def _get_gui_any(self, key: str, row: int, col: int):
		# クロージャ作成
		get = self._get_gui_any_closure(key, row, col, 1)
		# GUIリストを作成して返す
		return [get(0, "*")]


class autoresp_node:
	"""
	受信データ解析テーブルノード
	"""

	def __init__(self) -> None:
		# root要素用情報
		self.root: bool = False
		# ノード情報
		self.hex: int = None
		self.next: Dict[int,autoresp_node] = {}
		self.next_else: autoresp_node = None
		# 末端要素用情報
		self.tail: bool = False
		self.tail_list: Dict[str, autoresp_tail_node] = {}
		self.tail_active: autoresp_tail_node = None

class autoresp_tail_node:
	def __init__(self) -> None:
		self.enable: bool = False
		self.id: str = None
		self.send_id: str = None
		self.senddata_ref = None


class autoresp_list:
	"""
	GUI構築定義データ
	"""
	ENABLE = 0			# 有効無効設定
	ID = 1				# 自動応答設定定義名
	DATA = 2			# 自動応答対象受信データパターン
	SENDDATA_ID = 3		# 自動送信データ定義名


class analyze_result:
	"""
	受信解析結果定義
	"""

	def __init__(self, data:int) -> None:
		# 今回受信データ
		self.data = data
		#
		self.id = ""
		# tail参照
		self.tail_node = None
		# 解析フラグ
		self._autoresp_send = False
		self._rx_buf_commit_prev = False
		self._rx_buf_commit = False
		self._rx_buf_push = False

	"""
	状態設定メソッド
	解析状態を設定する。内部で操作要求へ変換する。
	"""

	def set_analyze_NG2OK(self):
		self._rx_buf_commit_prev = True

	def set_analyze_OK2NG(self):
		pass

	def set_analyze_OK2OK(self):
		pass

	def set_analyze_NG2NG(self):
		pass

	def set_analyze_succeeded(self, tail_node: autoresp_tail_node):
		if tail_node is not None:
			self.id = tail_node.id
			self.tail_node = tail_node
		# フラグ設定
		self._autoresp_send = True
		self._rx_buf_push = True
		self._rx_buf_commit = True

	def set_analyze_failed(self):
		#
		self._rx_buf_push = True

	def set_analyzing(self):
		self._rx_buf_push = True

	def set_analyze_next_start(self):
		self._rx_buf_commit_prev = True
		self._rx_buf_push = True

	"""
	操作要求取得メソッド
	"""

	def trans_req(self) -> bool:
		return self._autoresp_send

	def prev_buff_commit(self) -> bool:
		return self._rx_buf_commit_prev

	def new_data_push(self) -> bool:
		return self._rx_buf_push

	def buff_commit(self) -> bool:
		return self._rx_buf_commit



class autoresp_mng:
	"""
	受信データ解析テーブルを構築
	"""

	def __init__(self, autoresp) -> None:
		# アクセス用にリストと辞書の両方で参照を持つ
		self.mng_dict: Dict[str,autoresp_node] = {}
		self.mng_list: List[str,autoresp_node] = []
		# 解析ツリー
		self.tree = autoresp_node()
		self.tree.root = True
		self.tail_ref = {}				# tailノードへの参照
		# 解析情報
		self._curr_node: autoresp_node = None
		self._prev_recv_analyze_result: bool = True

		"""
		受信データ定義が次のようになっているとき
			data1: 0*2
			data2: 01*
			data3: 1*2
			data4: **2
			data5: **0
			(1文字1バイト、*=any)
		次の通りに解析ツリーを構築する
			[root]	->	0	->	1	->	*
							->	*	->	2
					->	1	->	*	->	2
					->	*	->	*	->	0
									->	2
		常にanyより固定値を優先する。
		anyと固定値をマージしたツリーを構築したいとき、
		辿ったパスを記憶しておき、tail到達時にどのルールにマッチするか判定が必要になる。
		動的に構築するのは難しいため、anyと固定値のマージはしない。状態遷移組め。
		"""
		for i, resp in enumerate(autoresp):
			# 解析ツリーを構築
			tgt_node: List[autoresp_node] = []
			next_node: List[autoresp_node] = []
			tgt_node.append(self.tree)
			# 定義データをすべてチェック
			for data in resp[autoresp_list.DATA]:
				data: autoresp_data
				if data.type == autoresp_data.TYPE.ANY:
					# ANYではあらゆるデータを受け付ける
					next_node = []
					# 現状態ノードをすべてチェック
					for node in tgt_node:
						# elseノードチェック
						if node.next_else is None:
							# elseノード作成
							node.next_else = autoresp_node()
							# elseノードはnextノードも内包する
							#self._maketree_clone_next2else(node, autoresp)
						# elseノードを次状態として登録
						next_node.append(node.next_else)
						# 既存のnextノードもすべて、次状態以降の設定を追加する
						#for next in node.next.values():
						#	next_node.append(next)
					# 次の遷移設定
					tgt_node = next_node

				elif data.type == autoresp_data.TYPE.BYTE:
					# bytesを順に辿るツリーを構築
					for hex in data.value:
						# 現状態ノードをすべてチェック
						next_node = []
						for node in tgt_node:
							# 次状態ノードチェック
							if hex not in node.next.keys():
								# 存在しなければ新しいノード作成
								node.next[hex] = autoresp_node()
								# ノード情報登録
								next_node_ref = node.next[hex]
								next_node_ref.hex = hex
							else:
								next_node_ref = node.next[hex]
							next_node.append(next_node_ref)
							# elseノードチェック
							#if node.next_else is not None:
							#	next_node.append(node.next_else)
						# 次の遷移設定
						tgt_node = next_node
			# tailノード作成
			tail_node = self._maketree_make_tail(resp)
			# 末尾ノードチェック
			for tail in tgt_node:
				tail.tail = True
				# tail情報登録
				if tail_node.id not in tail.tail_list.keys():
					tail.tail_list[tail_node.id] = tail_node
				# enableチェック
				if tail.tail_active is None:
					if tail_node.enable:
						# 有効なtail_nodeが初出現のとき、有効tailとして参照登録
						tail.tail_active = tail_node
				else:
					if tail_node.enable:
						# 有効なtail_nodeが重複したとき
						# 先優先で、今回ノードは無効化する
						tail_node.enable = False
						resp[autoresp_list.ENABLE] = False



	def _maketree_make_tail(self, resp) -> autoresp_tail_node:
		id = resp[autoresp_list.ID]
		if id not in self.tail_ref.keys():
			# インスタンス作成
			node = autoresp_tail_node()
			# 情報設定
			node.enable = resp[autoresp_list.ENABLE]
			node.id = id
			node.send_id = resp[autoresp_list.SENDDATA_ID]
			# 参照登録
			self.tail_ref[node.id] = node
		else:
			# 参照取得
			node = self.tail_ref[id]
			print("tail_node作成済み???")
		# 終了
		return node

	def _maketree_set_tail(self, node:autoresp_node, enable:bool, id:str, send_id:str):
		pass

	def _maketree_clone_else2next(self, node: autoresp_node, autoresp):
		"""
		ツリー構築補助関数
		elseノードをnextノードにコピーする
		"""

	def _maketree_clone_next2else(self, node: autoresp_node, autoresp):
		"""
		ツリー構築補助関数
		nextノードをelseノードにコピーする。
		nextノードが複数存在する場合、すべて統合してelseノードとなる。

			[curr]	->	[next]	->	A	->	[next]	->	B
													->	C
											[else]	
								->	D	->	[next]	->	B
													->	E
											[else]	
								->	Z	->	[tail]
						↓コピー
					->	[else]	=======>	[next]	->	B
													->	C
													->	E
		"""
		# elseノードチェック
		if node.next_else is None:
			# 関数に渡す前にインスタンスは作成しておくこと
			raise Exception("make node instance, before copy method.")
		# nextノードチェック
		if not node.next:
			# nextノードが存在しなければ何もせず終了
			return
		# 
		for next in node.next.values():
			self._maketree_merge_node(next, node.next_else)

	def _maketree_merge_node(self, src_node: autoresp_node, dist_node: autoresp_node):
		"""
		1階層コピーする
		末端に到達するまで再帰的に繰り返す
		"""
		if src_node.tail:
			# tail設定
			dist_node.tail = True
			# enableチェック
			has_enable = False
			if dist_node.tail_active is not None:
				has_enable = True
			# tailノードリストマージ
			for key in src_node.tail_list.keys():
				# 参照作成
				dist_node.tail_list[key] = src_node.tail_list[key]
				# tailノード有効チェック
				if dist_node.tail_list[key].enable:
					if has_enable:
						dist_node.tail_list[key].enable = False
					else:
						dist_node.tail_active = dist_node.tail_list[key]
						has_enable = True

		else:
			# nextノードを順番にコピー
			for key in src_node.next.keys():
				# keyチェック
				if key not in dist_node.next.keys():
					dist_node.next[key] = autoresp_node()
				# コピー実行
				self._maketree_merge_node(src_node.next[key], dist_node.next[key])
			# srcノードがelseノードを持っているとき
			# elseノードコピー
			if src_node.next_else is not None:
				# elseインスタンスチェック
				if dist_node.next_else is None:
					dist_node.next_else = autoresp_node()
				# コピー実行
				self._maketree_merge_node(src_node.next_else, dist_node.next_else)



	def recv_analyze_init(self):
		"""
		受信解析を初期化する
		"""
		self._curr_node = self.tree

	def recv_analyze(self, data: int) -> analyze_result:
		# 今回解析結果
		result = analyze_result(data)

		# 状態遷移チェック
		trans_result = self._recv_analyze_trans(data)
		if trans_result:
			# 解析OK
			self._recv_analyze_success(data, result)
		else:
			# 解析NG
			self._recv_analyze_failure(data, result)
		#
		return result

	def _recv_analyze_trans(self, data: int) -> bool:
		result: bool
		# 状態遷移チェック
		if data in self._curr_node.next.keys():
			# 解析ツリーにマッチ
			self._curr_node = self._curr_node.next[data]
			# 解析OK
			result = True
		elif self._curr_node.next_else is not None:
			# anyにマッチ
			self._curr_node = self._curr_node.next_else
			# 解析OK
			result = True
		else:
			# 解析NG
			result = False
		#
		return result

	def _recv_analyze_success(self, data: int, result: analyze_result):
		# 前回結果
		if self._prev_recv_analyze_result:
			# OK -> OK
			result.set_analyze_OK2OK()
		else:
			# NG -> OK
			result.set_analyze_NG2OK()
		# tailチェック
		# 遷移後ノードでチェック
		if self._curr_node.tail:
			# 受信解析正常終了
			result.set_analyze_succeeded(self._curr_node.tail_active)
		else:
			# 解析継続中
			result.set_analyzing()
		"""
		# 解析途中で解析テーブルの末尾に到達
		# 受信解析途中終了
		if not self._curr_node.next and self._curr_node.next_else is None:
			analyze_result.set_analyze_failed()
		"""

		# 前回結果更新
		self._prev_recv_analyze_result = True

	def _recv_analyze_failure(self, data: int, result: analyze_result):
		# 前回結果
		if self._prev_recv_analyze_result:
			# OK -> NG
			result.set_analyze_OK2NG()
		else:
			# NG -> NG
			result.set_analyze_NG2NG()
		# 前回結果更新
		self._prev_recv_analyze_result = False
		# 解析失敗したので最初から解析しなおし
		self.recv_analyze_init()
		# 先頭からマッチするかチェック
		trans_check = self._recv_analyze_trans(data)
		if trans_check:
			# 解析OKなら
			self._recv_analyze_success(data, result)
			# ここまでの解析は失敗、次の解析開始
			result.set_analyze_next_start()
		else:
			# 解析失敗継続
			result.set_analyze_failed()





if __name__ == "__main__":
	hex = autoresp_data.byte
	any = autoresp_data.any
	data = None
	if False:
		"""
			data1: 0*2
			data2: 01*
			data3: 1*2
			data4: **2
			data5: **0
		"""
		data = [
				#有効		# 受信値		# 自動応答対象							# 応答データ名
				#設定		# 名称			# 受信データパターン					# (自動送信設定)
			[	True,		"Test1",		[hex('00'), any(1), hex('02')],		""],
			[	True,		"Test2",		[hex('00'), hex('01'), any(1)],		""],
			[	True,		"Test3",		[hex('01'), any(1), hex('02')],		""],
			[	True,		"Test4",		[any(1), any(1), hex('02')],		""],
			[	True,		"Test5",		[any(1), any(1), hex('00')],		""],
		]
	if True:
		"""
				data1: 01**0*
				data2: 02**0*
				data2: 03**0*
				data3: 04**0*
				data4: 05**0*
		"""
		data = [
				#有効		# 受信値		# 自動応答対象															# 応答データ名
				#設定		# 名称			# 受信データパターン													# (自動送信設定)
			[	True,		"Test1",		[hex('00'), hex('01'), any(1), any(1), hex('00'), any(1)],				""],
			[	True,		"Test2",		[hex('00'), hex('02'), any(1), any(1), hex('00'), any(1)],				""],
			[	True,		"Test3",		[hex('00'), hex('03'), any(1), any(1), hex('00'), any(1)],				""],
			[	True,		"Test4",		[hex('00'), hex('04'), any(1), any(1), hex('00'), any(1)],				""],
			[	True,		"Test5",		[hex('00'), hex('05'), any(1), any(1), hex('00'), any(1)],				""],
		]
	mng = autoresp_mng(data)
	print("finish.")
