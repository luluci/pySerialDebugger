
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
	data = [
			#有効		# 受信値		# 自動応答対象												# 応答データ名
			#設定		# 名称			# 受信データパターン										# (自動送信設定)
		[	True,		"Test1",		[hex('ABCD'), any(8), hex('02'), any(8), hex('02')],		"応答データ1"],
		[	True,		"Test2",		[hex('0020'), any(8), any(8), any(8), any(8)],				"応答データ2"],
		[	True,		"Test3",		[hex('0030'), any(8), any(8), any(8), any(8)],				"応答データ3"],
	]
	
	#
	return (caption, head, data)
