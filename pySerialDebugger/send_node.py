import re
from typing import Any, List, Dict, Tuple
import PySimpleGUI as sg

class send_node:
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
		# タイプごとに処理
		if type == send_node.INPUT:
			self._init_input(name, value)
		if type == send_node.SELECT:
			values: Dict[str, int]
			self._init_select(name, values)
		if type == send_node.FIX:
			self._init_input(name, value)
		if type == send_node.BITFIELD:
			values: List[Tuple[send_node, int]]
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
		values: List[Tuple[send_node, int]]
		if (name is None) or (values is None):
			raise Exception("send_node: BITFIELD node require [name, values]")
		self.name = name
		self.values = values
		# bitfiled info
		self.bf_size_tbl = [0] * len(values)
		# 初期値設定
		value = 0
		val: Tuple[send_node, int]
		bf_pos = 0
		for i, val in enumerate(values):
			# 情報取得
			self.bf_size_tbl[i] = val[send_node.BF_SIZE]
			gui = val[send_node.BF_NODE]
			# 初期値作成
			value |= (gui.value << bf_pos)
			# bf_pos更新
			bf_pos += val[send_node.BF_SIZE]
		# サイズチェック
		if self.size < bf_pos:
			raise Exception("send_node: BITFIELD values takes too large bit_size.")

	@classmethod
	def input(cls, hex: str):
		return send_node(send_node.INPUT, 8, "kari", int(hex, 16), None, None)

	@classmethod
	def input_16(cls, hex: str):
		return send_node(send_node.INPUT, 16, "kari", int(hex, 16), None, "little")

	@classmethod
	def input_16be(cls, hex: str):
		return send_node(send_node.INPUT, 16, "kari", int(hex, 16), None, "big")

	@classmethod
	def select(cls, values: Dict[str, int]):
		return send_node(send_node.SELECT, 8, "kari", None, values, None)

	@classmethod
	def select_16(cls, values: Dict[str, int]):
		return send_node(send_node.SELECT, 16, "kari", None, values, None)

	@classmethod
	def fix(cls, hex: str):
		return send_node(send_node.FIX, 8, "kari", int(hex, 16), None, None)

	@classmethod
	def bf(cls, values: List[any], size:int = 8):
		values: List[Tuple[send_node, int]]
		return send_node(send_node.BITFIELD, size, "kari", None, values, None)

	@classmethod
	def bf_16(cls, values: List[any]):
		values: List[Tuple[send_node, int]]
		return send_node(send_node.BITFIELD, 16, "kari", None, values, None)

	def get_size(self) -> int:
		return int(self.size / 8)

	def get_value(self, gui_data: str) -> bytes:
		"""
		GUI設定値を値に直して返す
		"""
		# タイプごとに処理
		if self.type == send_node.INPUT:
			return self.get_value_input(gui_data)
		if self.type == send_node.SELECT:
			return self.get_value_select(gui_data)
		if self.type == send_node.FIX:
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
		if self.type == send_node.INPUT:
			return self._get_bytes_input()
		if self.type == send_node.SELECT:
			return self._get_bytes_select()
		if self.type == send_node.FIX:
			return self._get_bytes_input()
		if self.type == send_node.BITFIELD:
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

	def get_gui(self, key, size, pad, font) -> Any:
		# タイプごとに処理
		if self.type == send_node.INPUT:
			return self._get_gui_input(key, size, pad, font)
		if self.type == send_node.SELECT:
			return self._get_gui_select(key, size, pad, font)
		if self.type == send_node.FIX:
			return self._get_gui_fix(key, size, pad, font)
		if self.type == send_node.BITFIELD:
			return self._get_gui_bitfield(key, size, pad, font)
		raise Exception("unknown node type detected!")

	def _get_gui_input(self, key, size, pad, font):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		size_offset = 1 * (byte_size - 1)
		size = (size[0] * byte_size + size_offset, size[1])
		return sg.Input(format(self.value, gui_form), key=key, size=size, pad=pad, font=font, enable_events=True)

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
		return sg.Combo(list, default_value=def_val, key=key, size=size, pad=pad, font=font, auto_size_text=True, enable_events=True)

	def _get_gui_fix(self, key, size, pad, font):
		# size取得
		byte_size = self.get_size()
		# GUI調整
		gui_form = "0" + format(byte_size * 2) + "X"
		size = (size[0] * byte_size, size[1])
		return sg.Input(format(self.value, gui_form), key=key, size=size, pad=pad, font=font, enable_events=True, disabled=True, disabled_readonly_background_color=sg.theme_background_color(), disabled_readonly_text_color=sg.theme_element_text_color())

	def _get_gui_bitfield(self, key, size, pad, font):
		# size取得
		byte_size = self.get_size()
		item_size = len(self.values)
		# GUI調整
		gui_list = []
		def_val = None
		size = (size[0]*byte_size, size[1])
		col_size = (44*byte_size, 20*item_size)
		for bf_idx, data in enumerate(self.values):
			gui: send_node = data[send_node.BF_NODE]
			gui_list.append([gui.get_gui(("gui_input_bf", key, bf_idx), size, pad, font)])
		return sg.Column(gui_list, key=key, size=col_size, pad=pad, vertical_alignment="top")

	def get_gui_value(self, fmt:str = None) -> str:
		# タイプごとに処理
		if self.type == send_node.INPUT:
			return self._get_gui_value_input(fmt)
		if self.type == send_node.SELECT:
			return self._get_gui_value_select()
		if self.type == send_node.FIX:
			return self._get_gui_value_input()
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
