
from .autoresp import autoresp_data




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
			[	False,		"Test1",		[hex('00'), any(1), hex('02')],		""],
			[	False,		"Test2",		[hex('00'), hex('01'), any(1)],		""],
			[	False,		"Test3",		[hex('01'), any(1), hex('02')],		""],
			[	False,		"Test4",		[any(1), any(1), hex('02')],		""],
			[	False,		"Test5",		[any(1), any(1), hex('00')],		""],
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
