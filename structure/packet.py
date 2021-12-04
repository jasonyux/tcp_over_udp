from .header import TCPHeader

class Packet(object):
	def __init__(self, header:TCPHeader, payload:str) -> None:
		self.__header = header
		self.__payload = payload

	@property
	def header(self):
		return self.__header

	@property
	def payload(self):
		return self.__payload

	@header.setter
	def header(self, value):
		self.__header = value
	
	@payload.setter
	def payload(self, value):
		self.__payload = value

	def __str__(self):
		content = f"""
		---
		[HEADER]: {self.__header}
		[Payload]: {self.__payload}
		---"""
		return content