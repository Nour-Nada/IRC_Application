import math
import base64

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

    def to_dict(self): #my method for encoding the main message into a json
        d  = {
            'message': {
                'header': {
                    'operation_code': self.header.operation_code,
                    'length': 4 * math.ceil(len(self.data) / 3),
                    'target': self.header.target,
                    'sender': "server"
                },
                'data': base64.b64encode(self.data).decode("utf-8") #first coverts to base64 ensureing all the charcters are utf-8 comptaible then it decodes using utf-8
            }
        }
        return d
		
class operation_message:
    def __init__(self):
        self.operation_code = 0x00
        self.data = ""
        self.target = ""
        self.sender = ""
            
    def to_dict(self): #turns the operation message into the expected json format
        return {'operation_message': self.__dict__}
		
class error_message:
    def __init__(self):
        self.err_code = 0x00
        self.data = ""
        self.target = ""
        self.sender = ""

    def to_dict(self): #turns the error message into the expected json format
        return {'error_message': self.__dict__}