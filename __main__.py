from pySerialDebugger import gui_mng

if __name__ == "__main__":
	# オブジェクト生成
	try:
		gui = gui_mng.gui_manager()
	except:
		import traceback
		traceback.print_exc()
		exit(0)
	# 処理実施
	try:
		gui.exe()
	except:
		import traceback
		traceback.print_exc()
	finally:
		if gui:
			gui.close()
