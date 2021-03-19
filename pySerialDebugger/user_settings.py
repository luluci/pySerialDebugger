
from .autoresp import autoresp_data
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

	caption = [
		"[送信データ設定]", "", "送信データ",
	]
	head = [
			"[ID]",				["ST", "XX", "XX", "XX", "XX", "YY"]
	]
	data = [
			# 送信設定			# 手動送信データ定義					# FCC定義(idx=0開始)
			# 名称				# 送信HEX					#サイズ		# 挿入位置	# 計算開始位置	# 計算終了位置
		[	"Manual",			hex(''),					24,			17,			4,				7,				],
		[	"TestSend1",		hex('00112233'),			-1,			4,			0,				3,				],
		[	"TestSend2",		hex('00'),					5,			None,		0,				3,				],
		[	"TestSend3",		hex(''),					0,			None,		0,				3,				],
		[	"TestSend4",		[ inp('aa'), sel({'ON':1, 'OFF':0}), fix('00'), fix('00'), inp16be('1234'), inp('56'), inp16('8000'), fix('9A') ],	18,			17,			1,				16,					],
	]
	#
	return (caption, head, data)


def autosend_settings() -> None:
	"""
	自動送信定義
	手動送信として定義したデータを使って送信する。
	送信対象は手動送信設定の名称で指定する。
	シリアル通信での出力を確認せずにシーケンスを進めるので、
	シリアル通信側で送信できずに詰まるとキューあふれを起こす点に注意。
	"""
	send = autosend_data.send		# 手動送信で設定した送信データ(名称で指定)を送信する
	wait = autosend_data.wait_ms	# 指定時間だけwaitする(※100ms前後くらい処理時間ありそう。)
	exit = autosend_data.exit		# 自動送信を終了する
	jump = autosend_data.jump		# autosendリスト内の指定idx(0開始)にジャンプする

	caption = [
		"[AutoSend]", "自動送信パターン",
	]
	head = [
			"[Act]",	"[ID]", 				"[SendInfo]",
	]
	data = [
		[	False,		"TestAutoSend1",		[send("TestSend1"), wait(1000), send("TestSend2"), wait(1000)]],
		[	False,		"TestAutoSend2",		[send("TestSend4"), exit()]],
		[	False,		"TestAutoSend3",		[send("TestSend1"), wait(100), send("TestSend2"), wait(100), send("TestSend3"), wait(100), send("TestSend2"), jump(3)]],
	]
	#
	return (caption, head, data)

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
			"[Act]",	"[ID]", 		["ST", "XX", "XX", "XX", "XX", "XX", ],					"[SendID]",
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
				#有効		# 受信値		# 自動応答対象							# 応答データ名
				#設定		# 名称			# 受信データパターン					# (自動送信設定)
			[	True,		"Test1",		[hex('00'), any(1), hex('02')],			"TestAutoSend2"],
			[	True,		"Test2",		[hex('00'), hex('01'), any(1)],			"TestAutoSend2"],
			[	True,		"Test3",		[hex('01'), any(1), hex('02')],			"TestAutoSend2"],
			[	True,		"Test4",		[any(1), any(1), hex('02')],			"TestAutoSend2"],
			[	True,		"Test5",		[any(1), any(1), hex('00')],			"TestAutoSend2"],
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
