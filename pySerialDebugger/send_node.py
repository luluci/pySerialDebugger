import re
from typing import Any, List, Dict, Tuple
import PySimpleGUI as sg
import enum


class ChecksumType(enum.Enum):
	SUM = enum.auto()			# 総和
	TWOS_COMPL = enum.auto()	# 2の補数
	ONES_COMPL = enum.auto()	# 2の補数

class send_data:
	"""

	"""
	# inputノードタイプ
	INPUT, SELECT, FIX, BITFIELD = range(0,4)
	# BITFILED
	# bit_order: right
	#  0bXXXXYYZZ
	#    ||||||++-bf(0)
	#    ||||++---bf(1)
	#    ++++-----bf(2)
	# type : Tuple[send_node, int]
	# BITFIELD 要素idx定義
	BF_NODE, BF_SIZE = range(0,2)

	# GUI情報
	gui_size = None
	gui_pad = None
	gui_font = None

	@classmethod
	def set_gui_info(cls, size, pad, font):
		cls.gui_size = size
		cls.gui_pad = pad
		cls.gui_font = font
	
	def __init__(self, type: int, size: int, name: str, value: int, values: Any, endian:str) -> None:
		# inputノードタイプを設定
		if (type is None) or (size is None):
			raise Exception("send_node node require [type, size]")
		self.type = type
		# データサイズ(bit長)
		self.size = size
		# エンディアン
		if endian is None:
			endian = 'little'
		self.endian = endian
		# FCC情報
		self.fcc_type: ChecksumType = None
		# タイプごとに処理
		if type == send_data.INPUT:
			self._init_input(name, value)
		if type == send_data.SELECT:
			values: Dict[str, int]
			self._init_select(name, values)
		if type == send_data.FIX:
			self._init_input(name, value)
		if type == send_data.BITFIELD:
			values: List[Tuple[send_data, int]]
			self._init_bitfield(name, values)

	def _init_input(self, name: str, value: int):
		if (name is None) or (value is None):
			raise Exception("send_node: INPUT node require [name, value]")
		self.name = name
		self.value = value

	def _init_select(self, name: str, values: Dict[str, int]):
		if (name is None) or (values is None):
			raise Exception("send_node: SELECT node require [name, values]")
		self.name = name
		self.values = values
		# 初期値設定
		for val in values.values():
			self.value = val
			break

	def _init_bitfield(self, name: str, values):
		values: List[Tuple[send_data, int]]
		if (name is None) or (values is None):
			raise Exception("send_node: BITFIELD node require [name, values]")
		self.name = name
		self.values = values
		# bitfiled info
		self.bf_size_tbl = [0] * len(values)
		# 初期値設定
		value = 0
		val: Tuple[send_data, int]
		bf_pos = 0
		for i, val in enumerate(values):
			# 情報取得
			self.bf_size_tbl[i] = val[send_data.BF_SIZE]
			gui = val[send_data.BF_NODE]
			# 初期値作成
			value |= (gui.value << bf_pos)
			# bf_pos更新
			bf_pos += val[send_data.BF_SIZE]
		# サイズチェック
		if self.size < bf_pos:
			raise Exception("send_node: BITFIELD values takes too large bit_size.")

	@classmethod
	def input(cls, hex: str):
		return send_data(send_data.INPUT, 8, "kari", int(hex, 16), None, None)

	@classmethod
	def input_16(cls, hex: str):
		return send_data(send_data.INPUT, 16, "kari", int(hex, 16), None, "little")

	@classmethod
	def input_16be(cls, hex: str):
		return send_data(send_data.INPUT, 16, "kari", int(hex, 16), None, "big")

	@classmethod
	def select(cls, values: Dict[str, int]):
		return send_data(send_data.SELECT, 8, "kari", None, values, None)

	@classmethod
	def select_16(cls, values: Dict[str, int]):
		return send_data(send_data.SELECT, 16, "kari", None, values, None)

	@classmethod
	def fix(cls, hex: str):
		return send_data(send_data.FIX, 8, "kari", int(hex, 16), None, None)

	@classmethod
	def bf(cls, values: List[any], size:int = 8):
		values: List[Tuple[send_data, int]]
		return send_data(send_data.BITFIELD, size, "kari", None, values, None)

	@classmethod
	def bf_16(cls, values: List[any]):
		values: List[Tuple[send_data, int]]
		return send_data(send_data.BITFIELD, 16, "kari", None, values, None)

	@classmethod
	def fcc(cls, checksum: ChecksumType):
		node = send_data(send_data.FIX, 8, "kari", 0, None, None)
		node.fcc_type = checksum
		return node

	@classmethod
	def fcc_sum(cls):
		return send_data.fcc(ChecksumType.SUM)

	@classmethod
	def fcc_2compl(cls):
		return send_data.fcc(ChecksumType.TWOS_COMPL)

	@classmethod
	def fcc_1compl(cls):
		return send_data.fcc(ChecksumType.ONES_COMPL)



	def get_size(self) -> int:
		return int(self.size / 8)

	def get_value(self, gui_data: str) -> bytes:
		"""
		GUI設定値を値に直して返す
		"""
		# タイプごとに処理
		if self.type == send_data.INPUT:
			return self.get_value_input(gui_data)
		if self.type == send_data.SELECT:
			return self.get_value_select(gui_data)
		if self.type == send_data.FIX:
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
		if self.type == send_data.INPUT:
			return self._get_bytes_input()
		if self.type == send_data.SELECT:
			return self._get_bytes_select()
		if self.type == send_data.FIX:
			return self._get_bytes_input()
		if self.type == send_data.BITFIELD:
			return self._get_bytes_bitfield()
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

	def _get_bytes_bitfield(self) -> bytes:
		# size取得
		byte_size = self.get_size()
		return b'\88'

	def get_gui(self, key, row, col) -> Any:
		# タイプごとに処理
		if self.type == send_data.INPUT:
			return self._get_gui_input(key, row, col)
		if self.type == send_data.SELECT:
			return self._get_gui_select(key, row, col)
		if self.type == send_data.FIX:
			return self._get_gui_fix(key, row, col)
		if self.type == send_data.BITFIELD:
			return self._get_gui_bitfield(key, row, col)
		raise Exception("unknown node type detected!")

	def _get_gui_input(self, key, row, col):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		size_offset = 1 * (byte_size - 1)
		size = (send_data.gui_size[0] * byte_size + size_offset, send_data.gui_size[1])
		return sg.Input(format(self.value, gui_form), key=(key, row, col), size=size, pad=send_data.gui_pad, font=send_data.gui_font, enable_events=True)

	def _get_gui_select(self, key, row, col):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		list = []
		def_val = None
		size = (send_data.gui_size[0]*byte_size-2, send_data.gui_size[1])
		for data in self.values:
			if def_val is None:
				def_val = data
			list.append(data)
		return sg.Combo(list, default_value=def_val, key=(key, row, col), size=size, pad=send_data.gui_pad, font=send_data.gui_font, auto_size_text=True, enable_events=True)

	def _get_gui_fix(self, key, row, col):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		size = (send_data.gui_size[0] * byte_size, send_data.gui_size[1])
		return sg.Input(format(self.value, gui_form), key=(key, row, col), size=size, pad=send_data.gui_pad, font=send_data.gui_font, enable_events=True, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())

	def _get_gui_bitfield(self, key, row, col):
		# size取得
		byte_size = self.get_size()
		item_size = len(self.values)
		# GUI調整
		gui_list = []
		def_val = None
		size = (send_data.gui_size[0]*byte_size, send_data.gui_size[1])
		col_size = (44*byte_size, 20*item_size)
		for bf_idx, data in enumerate(self.values):
			gui: send_data = data[send_data.BF_NODE]
			gui_list.append([gui.get_gui(("gui_input_bf", key, row, (col,bf_idx)), size, send_data.gui_pad, send_data.gui_font)])
		return sg.Column(gui_list, key=(key, row, col), size=col_size, pad=send_data.gui_pad, vertical_alignment="top")

	def get_gui_value(self, fmt:str = None) -> str:
		# タイプごとに処理
		if self.type == send_data.INPUT:
			return self._get_gui_value_input(fmt)
		if self.type == send_data.SELECT:
			return self._get_gui_value_select()
		if self.type == send_data.FIX:
			return self._get_gui_value_input(fmt)
		raise Exception("unknown node type detected!")

	def _get_gui_value_input(self, fmt:str) -> str:
		# size取得
		byte_size = self.get_size()
		# GUI調整
		if fmt is None:
			fmt = "0" + format(byte_size * 2) + "X"
		return format(self.value, fmt)

	def _get_gui_value_select(self) -> str:
		def_val = None
		for key, value in self.values.items():
			if def_val is None:
				def_val = key
			if self.value == value:
				return key
		return def_val


class send_data_list:
	"""
	GUI構築定義データ
	"""
	ID = 0				# 送信設定定義名
	DATA = 1			# 送信データ定義
	DATA_SIZE = 2		# 送信データ長
	FCC_POS = 3			# FCC位置
	FCC_CALC_BEGIN = 4	# FCC計算開始位置
	FCC_CALC_END = 5	# FCC計算終了位置

class send_data_node:
	"""
	各送信データ定義を管理する
	"""

	def __init__(self, data: List[any]) -> None:
		data_len = len(data)
		# GUI情報
		self._wnd: sg.Window = None
		self._gui_key: str = None
		self._gui_row: int = None
		# ID設定
		self.id = data[send_data_list.ID]
		# user_settingsで指定されたオリジナルのsend_dataリストの参照を取得
		self.data_list_org = data[send_data_list.DATA]
		# FCC情報設定
		# 個別にFCC情報が設定されていたら取得
		self.fcc_pos = None
		self.fcc_calc_begin = None
		self.fcc_calc_end = None
		if send_data_list.FCC_CALC_END < data_len:
			self.fcc_pos = data[send_data_list.FCC_POS]
			self.fcc_calc_begin = data[send_data_list.FCC_CALC_BEGIN]
			self.fcc_calc_end = data[send_data_list.FCC_CALC_END]+1
		# send_dataリストからFCC設定情報を検索
		# data_list_orgがListのときのみ存在する
		if isinstance(self.data_list_org, List):
			# send_dataをすべてチェック
			for i, node in enumerate(self.data_list_org):
				node: send_data
				# FCCノードはFCC情報が初期化されている
				if node.fcc_type is not None:
					# FCC位置はFCCノードの位置を優先する
					self.fcc_pos = i
					# FCC計算範囲は指定されていなかった場合、FCCノードの直前まですべてとする
					if self.fcc_calc_begin is None or self.fcc_calc_end is None:
						self.fcc_calc_begin = 0
						self.fcc_calc_end = i
		# 送信データ定義設定
		self.size = -1
		if send_data_list.DATA_SIZE < data_len:
			self.size = data[send_data_list.DATA_SIZE]
		# send_dataリスト
		self.data_list: List[send_data] = None
		if isinstance(self.data_list_org, List):
			# send_dataリストのとき参照設定
			self.data_list = self.data_list_org
		else:
			# bytes指定のときはNone
			self.data_list = None

		# 送信データバイト列
		self.data_array: bytearray = None
		self.data_bytes: bytes = None
		# 要素対応付けリスト
		self.map_data2gui: List[int] = None
		self.map_gui2data: List[int] = None

		# 定義データを解析
		self._calc_send_data_size()
		self._make_send_data()
		# FCC算出
		self.update_fcc()
		# 作成したbytearrayをbytesに反映
		self.update_bytes()

	def init_wnd(self, wnd: sg.Window):
		"""
		window作成後に、windowインスタンスへの参照を設定する
		"""
		self._wnd = wnd

	def _calc_send_data_size(self) -> int:
		# 送信データ定義の長さ、送信データサイズ定義、FCC位置を比較
		# 最大長を採用する
		data_len = self._calc_data_len()
		data_len = max(data_len, self.size)
		if self.fcc_pos is not None:
			data_len = max(data_len, self.fcc_pos+1)
		# データ設定
		self.size = data_len

	def _calc_data_len(self) -> int:
		if isinstance(self.data_list_org, bytes):
			return len(self.data_list_org)
		if isinstance(self.data_list_org, List):
			txs_len = 0
			for tx in self.data_list_org:
				txs_len += tx.get_size()
			return txs_len

	def _make_send_data(self):
		### 送信データHEXを構築
		tx_data: bytearray = None

		# bytesで設定されていたらsend_dataリストを生成
		if self.data_list is None:
			# send_dataを自動生成
			self.data_list = []
			for byte in self.data_list_org:
				new_data = send_data(send_data.INPUT, 8, "kari", byte, None, None)
				self.data_list.append(new_data)

		# この時点で必ずself.data_listは初期化されている
		# data_listは初期化されているから送信データbytearrayを作成する
		tx_data = self._make_send_data_from_list()

		# データサイズに対してbytesが短ければ0埋め
		tx_data_size = len(tx_data)
		idx_data2gui = len(self.map_data2gui)
		idx_gui2data = len(self.map_gui2data)
		if tx_data_size < self.size:
			for i in range(tx_data_size, self.size):
				# 0埋め追加
				new_data = send_data(send_data.INPUT, 8, "kari", 0, None, None)
				self.data_list.append(new_data)
				tx_data += bytearray(b'\0')
				# 対応付けリスト更新
				self.map_data2gui.append(idx_gui2data)
				self.map_gui2data.append(idx_data2gui)
				idx_data2gui += 1
				idx_gui2data += 1
		# データ設定
		self.data_array = tx_data
		# data_bytesはfcc_update()で作成

	def _make_send_data_from_list(self) -> bytearray:
		# 対応付けリストを初期化
		self.map_data2gui = []
		self.map_gui2data = []

		data = bytearray()
		data_idx = 0
		data_size = 0
		for gui_idx, send_data in enumerate(self.data_list):
			# send_dataから設定値取得
			data += bytearray(send_data.get_bytes())
			# 対応付けリスト更新
			# GUI to data
			self.map_gui2data.append(data_idx)
			# data to GUI
			data_size = send_data.get_size()
			for i in range(0,data_size):
				self.map_data2gui.append(gui_idx)
				data_idx += 1
		return data

	def update_fcc(self):
		"""
		FCCを計算して反映する
		"""
		# FCC位置がNoneのときは対象外
		fcc = None
		if self.fcc_pos is not None:
			# FCCを計算して反映
			fcc = self.calc_fcc()
			self.data_array[self.fcc_pos] = fcc
			# FCC算出結果をdata_listに反映する。
			if self.data_list is not None:
				# FCC位置にあるsend_dataのインデックスを取得
				idx = self.map_data2gui[self.fcc_pos]
				# send_dataを更新
				self.data_list[idx].set_value(fcc.to_bytes(1, 'little'), 0)
		# 返す
		return fcc

	def calc_fcc(self):
		"""
		FCC計算
		dataの(begin,end]要素の総和の2の補数を計算する
		* beginは含む、endは含まない、FCC挿入位置は含まない
		(begin,end] がdata長を超えたら 0x00 を加算とする（何もしない）
		"""
		fcc: int = 0
		for i in range(self.fcc_calc_begin, self.fcc_calc_end):
			if (i != self.fcc_pos) and (i < self.size):
				fcc += self.data_array[i]
		fcc = ((fcc ^ 0xFF) + 1) % 256
		return fcc

	def update_bytes(self):
		"""
		bytesデータを更新する
		"""
		# bytesを更新する
		self.data_bytes = bytes(self.data_array)

	def get_gui(self, key:str, row:int):
		# GUI情報を記憶しておく
		self._gui_key = key
		self._gui_row = row
		# gui部品リストを初期化
		parts = []
		# Add resp data col
		fix = send_data.fix
		#
		for col, data in enumerate(self.data_list):
			# col と self.map_gui2data[] は同じデータになる
			parts.append( data.get_gui(key, row, col) )
		#
		return parts

	def set_gui_value(self, wnd:sg.Window, key:str, row:int, col: int, gui_data: str) -> bytes:
		"""
		GUIから取得できるstrを受け取る。
		GUI部品に渡してstrを解析し、bytesとして取得する。
		"""
		# key,rowをチェックしてもいい
		# if key != self._gui_key or row != self._gui_row:
		# 	raise Exception("unexpected key/row set.")
		# 該当GUI部品を取得
		data: send_data = self.data_list[col]
		# GUI部品にGUI入力値を渡して、解析結果を受け取る
		value = data.get_value(gui_data)
		# bytearrayを更新
		data_idx = self.map_gui2data[col]
		for i, byte in enumerate(value):
			self.data_array[data_idx+i] = byte
		# FCC算出
		fcc = self.update_fcc()
		# 作成したbytearrayをbytesに反映
		self.update_bytes()
		# 変更した可能性のあるデータはGUIに書き戻す
		# 今回変更データ
		gui_tgt = wnd[(key, row, col)]
		gui_tgt.Update(value=data.get_gui_value('X'))
		# FCC
		if fcc is not None:
			fcc_idx = self.map_data2gui[self.fcc_pos]
			fcc_data = self.data_list[fcc_idx]
			gui_fcc = wnd[(key, row, fcc_idx)]
			gui_fcc.Update(value=fcc_data.get_gui_value())

	def update_gui(self, pos:int, value:int):
		"""
		GUIと送信データを更新する
		"""
		# データ整形
		# 処理を流用するため、無駄になるけど変換する
		pos = self.map_data2gui[pos]
		value = f'{value:X}'
		# 更新処理を実施
		self.set_gui_value(self._wnd, self._gui_key, self._gui_row, pos, value)


class send_mng:

	def __init__(self, send) -> None:
		# dict: idと対応付けて記憶
		self._send_data_dict: Dict[str, send_data_node] = {}
		# list: ユーザ定義データの定義順と対応付けて記憶
		self._send_data_list: List[send_data_node] = []
		# 定義データ最大サイズ
		self._max_size: int = 0
		#
		for i, data in enumerate(send):
			# send_data管理ノード作成
			new_node = send_data_node(data)
			# サイズ確認
			if new_node.size > self._max_size:
				self._max_size = new_node.size
			#
			if new_node.id not in self._send_data_dict.keys():
				self._send_data_list.append(new_node)
				self._send_data_dict[new_node.id] = new_node
			else:
				self._send_data_list.append(new_node)
				print("id[" + new_node.id + "] is duplicate. idx[" + str(i) + "] is ignored.")

	def init_wnd(self, wnd: sg.Window):
		"""
		window作成後に、windowインスタンスへの参照を設定する
		"""
		for node in self._send_data_list:
			node.init_wnd(wnd)



if __name__ == "__main__":

	def _hex2bytes(hex: str) -> bytes:
		return bytes.fromhex(hex)

	hex = _hex2bytes
	inp = send_data.input
	inp16 = send_data.input_16
	inp16be = send_data.input_16be
	sel = send_data.select
	fix = send_data.fix

	_send_data = [
			# 送信設定			# 手動送信データ定義					# FCC定義(idx=0開始)
			# 名称				# 送信HEX					#サイズ		# 挿入位置	# 計算開始位置	# 計算終了位置
		[	"Manual",			hex(''),					24,			17,			4,				7,				],
		[	"TestSend1",		hex('00112233'),			-1,			4,			0,				3,				],
		[	"TestSend2",		hex('00'),					5,			None,		0,				3,				],
		[	"TestSend3",		hex(''),					0,			None,		0,				3,				],
		[	"TestSend4",		[ inp('aa'), sel({'ON':1, 'OFF':0}), fix('00'), fix('00'), inp16be('1234'), inp('56'), inp16('8000'), fix('9A') ],	18,			17,			1,				16,					],
	]
	mng = send_mng(_send_data)
	print("finish.")
