class header:
	def __init__(self):
		self.operation_code = 0x00
		self.length = 1024
		self.target = ""
		self.sender = ""
		
class message:
	def __init__(self):
		self.header = header()
		self.data = bytearray()
		
class error_message:
	def __init__(self):
		self.err_code = 0x00
		self.data = ""
		self.target = ""
		self.sender = ""