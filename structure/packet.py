import logging

from .header import TCPHeader
from utils import util

class Packet(util.Comparable):
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

	def compute_checksum(self):
		self.__header.set_checksum(self.__compute_checksum())
		return

	def __compute_checksum(self):
		prev_checksum = self.__header.checksum
		self.__header.set_checksum(value=0)
		header_checksum = self.header.compute_checksum()
		# total = header_checksum + sum([ord(c) for c in self.payload])
		total = header_checksum + sum(self.__payload)
		# reset
		self.__header.set_checksum(prev_checksum)
		return total

	def is_corrupt(self):
		current_checksum = self.__compute_checksum()
		logging.debug(f'current {current_checksum} vs {self.__header.checksum}')
		return current_checksum != self.__header.checksum

	def __str__(self):
		content = f"""
		---
		[HEADER]: {self.__header}
		[Payload]: {self.__payload}
		---"""
		return content