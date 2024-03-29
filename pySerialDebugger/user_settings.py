
from .autoresp import autoresp_data, recvdata_adapter
from .send_node import send_data
from .autosend import autosend_data

def hex2bytes(hex: str) -> bytes:
	return bytes.fromhex(hex)



def send_settings() -> None:
	hex = hex2bytes
	inp = send_data.input
	inp16 = send_data.input_16
	inp16be = send_data.input_16be
	sel = send_data.select
	fix = send_data.fix
	fcc = send_data.fcc_2compl
	fcc_nml = send_data.fcc_sum
	fcc_1compl = send_data.fcc_1compl

	caption = [
		"[送信データ設定]", "", "送信データ",
	]
	head = [
			"[送信データID]",	["ST", "XX", "XX", "XX", "XX", "YY"]
	]
	data = [
			# 送信設定			# 手動送信データ定義					# FCC定義(idx=0開始)
			# 名称				# 送信HEX					#サイズ		# 挿入位置	# 計算開始位置	# 計算終了位置
		[	"Manual",			hex(''),					24,			17,			4,				7,				],
		[	"TestSend1",		hex('00112233'),			-1,			4,			0,				3,				],
		[	"TestSend2",		hex('00'),					5,			None,		0,				3,				],
		[	"TestSend3",		hex(''),					0,			None,		0,				3,				],
		[	"TestSend4",		[ inp('aa'), sel({'ON':1, 'OFF':0}), fix('00'), fix('00'), inp16be('1234'), inp('56'), inp16('8000'), fix('9A') ],	18,			17,			1,				16,					],
		[	"TestSend_A",		hex('01AA000000FF'),		-1,			6,			0,				4,				],
		[	"TestSend_B",		hex('01BB000000FF'),		-1,			6,			0,				4,				],
		[	"TestSend_C",		hex('01CC000000FF'),		-1,			6,			0,				4,				],
		[	"TestSend_D",		[ fix('01'), fix('DD'), inp16be('1234'), sel({'ON':1, 'OFF':0}) ],		-1,			6,			0,				4,				],
		[	"TestSend_X",		hex('0100FF'),				-1,			3,			1,				2,				],
		[	"TestSend_Y",		hex('0A00FF'),				-1,			3,			1,				2,				],
		[	"TestSend_E1",		[ fix('01'), fix('02'), inp('03'), fix('00') ],		-1,		3,		0,		3,		],
		[	"TestSend_E2",		[ fix('01'), fix('02'), inp('03'), fcc() ]	],
		[	"TestSend_E3",		[ fix('01'), fix('02'), inp('03'), fcc_nml() ]	],
		[	"TestSend_E4",		[ fix('01'), fix('02'), inp('03'), fcc_1compl() ]	],
	]
	#
	return (caption, head, data)


def autosend_settings() -> None:
	"""
	自動送信定義
	手動送信として定義したデータを使って送信する。
	送信対象は手動送信設定の名称で指定する。
	※処理負荷軽減のために有効にできるのは1つの設定のみ。
	"""
	send = autosend_data.send		# 手動送信で設定した送信データ(名称で指定)を送信する
	wait = autosend_data.wait_ms	# 指定時間だけwaitする(※100ms前後くらい処理時間ありそう。)
	exit = autosend_data.exit		# 自動送信を終了する
	jump = autosend_data.jump		# autosendリスト内の指定idx(0開始)にジャンプする

	caption = [
		"[AutoSend]", "自動送信パターン",
	]
	head = [
            "[Act]",	"[自動送信データID]", 	"[SendInfo/送信データID/wait時間]",
	]
	data = [
		[	False,		"TestAutoSend1",		[send("TestSend_A"), wait(50), send("TestSend_B"), wait(50)]],
		[	False,		"TestAutoSend2",		[send("TestSend_C"), wait(50), send("TestSend_D"), wait(50)]],
		[	False,		"TestAutoSend2-2",		[send("TestSend_C"), wait(50), send("TestSend_C"), wait(50)]],
		[	False,		"TestAutoSend2-3",		[send("TestSend_D"), wait(50), send("TestSend_D"), wait(50)]],
		[	False,		"TestAutoSend3",		[send("TestSend_X"), wait(25), send("TestSend_X"), wait(50)]],
		[	False,		"TestAutoSend4",		[send("TestSend_X"), wait(25), send("TestSend2"), wait(100), send("TestSend3"), wait(100), send("TestSend2"), jump(3)]],
		[	False,		"TestAutoSend5",		[send("TestSend_X"), wait(500)]],
		[	False,		"TestAutoSend6",		[send("TestSend_Y"), wait(500)]],
	]
	#
	return (caption, head, data)


class test_data_buff:
	def __init__(self) -> None:
		self.B_data = 0
		self.autosend = [
			"TestAutoSend2",
			"TestAutoSend2-2",
			"TestAutoSend2-3",
		]
		self.autosend_pos = 0
		self.autosend_size = len(self.autosend)

	def next_autosend(self):
		next = self.autosend[self.autosend_pos]
		self.autosend_pos += 1
		if self.autosend_pos >= self.autosend_size:
			self.autosend_pos = 0
		return next

test_data = test_data_buff()

def analyze_recvdata_test1(hdl: recvdata_adapter, data: bytes):
	global test_data
	# 受信データからデータ抽出
	mode = data[2] ^ 0x0F
	# 送信データに反映:TestSend_Aの4バイト目を変更
	hdl.senddata_update("TestSend_A", 2, mode)
	test_data.B_data += 1
	hdl.senddata_update("TestSend_B", 2, test_data.B_data)

def analyze_recvdata_test2(hdl: recvdata_adapter, data: bytes):
	#
	hdl.autosend_change(test_data.next_autosend())


def anlyze_recvdata_test1_log(hdl: recvdata_adapter, data: bytes):
	log = ""
	if data[2] == 0x01:
		log += "初回"
	elif data[2] == 0x02:
		log += "2回目"
	elif data[2] == 0x04:
		log += "3回目"
	elif data[2] == 0x05:
		log += "4回目"
	elif data[2] == 0x06:
		log += "5回目"
	return log


def auto_response_settings():
	"""
	Auto Response Settings
	自動応答の定義はここを編集する
	"""
	hex = autoresp_data.byte
	any = autoresp_data.any		# 現状1バイト固定

	caption = [
		"[自動応答データ設定]"
	]
	head = [
			"[Act]",	"[受信解析ID]", 	["ST", "XX", "XX", "XX", "XX", "XX", ],			"[自動送信データID]",
	]

	if True:
		"""
			data1: 0*2
			data2: 01*
			data3: 1*2
			data4: **2
			data5: **0
		"""
		data = [
				#有効		# 受信値		# 自動応答対象									# 応答データ名			# 受信解析
				#設定		# 名称			# 受信データパターン							# (自動送信設定)		# データ解析				# ログ作成
			[	True,		"Test1",		[hex('00'), hex('AA'), any(1), any(1)],			"TestAutoSend1",		analyze_recvdata_test1,		anlyze_recvdata_test1_log,],
			[	True,		"Test2",		[hex('00'), hex('BB'), any(1), any(1)],			"TestAutoSend2",		analyze_recvdata_test2,		None,],
			[	True,		"Test3",		[hex('00'), any('FF'), hex('02')],				"TestAutoSend3",		None,						None,],
			[	True,		"Test4",		[any(1), any(1), hex('02')],					"TestAutoSend4",		None,						None,],
			[	True,		"Test5",		[any(1), any(1), hex('00')],					"TestAutoSend4",		None,						None,],
		]
	if False:
		data = [
				#有効		# 受信値		# 自動応答対象												# 応答データ名
				#設定		# 名称			# 受信データパターン										# (自動送信設定)
			[	True,		"Test1",		[hex('ABCD'), any(8), hex('02'), any(8), hex('02')],		"応答データ1"],
			[	True,		"Test2",		[hex('0020'), any(8), any(8), any(8), any(8)],				"応答データ2"],
			[	True,		"Test3",		[hex('0030'), any(8), any(8), any(8), any(8)],				"応答データ3"],
		]
	
	#
	return (caption, head, data)
