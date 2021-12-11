import logging

from utils.serialize import serialize
from .header import TCPHeader
from utils import util

class Packet(util.Comparable):
	"""TCP Packet

	This abstraction gives you a human-readable packet on the "surface",
	but during transmission, it will be "serialized" by struct.pack to become
	bytes.
	"""

	def __init__(self, header:TCPHeader, payload:str) -> None:
		"""Construct a packet from header and payload

		Args:
			header (TCPHeader): a constructed TCP header
			payload (str or bytes): payload
		"""
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
		"""Computes the 1s complement treating self.__header=0

		Returns:
			[int]: 1s complement of checksummed packet
		"""
		prev_checksum = self.__header.checksum
		self.__header.set_checksum(value=0)
		# computes checksum without header
		all_bytes = serialize(self)
		checksum = 0
		for i in range(0, len(all_bytes), 2):
			if i + 1 == len(all_bytes):
				checksum += all_bytes[i]
				break
			checksum += (all_bytes[i] << 8 + all_bytes[i+1])
		checksum &= 0xffff
		# reset
		self.__header.set_checksum(prev_checksum)
		return ~checksum # 1s complement

	def is_corrupt(self):
		current_checksum = self.__compute_checksum()
		logging.debug(f'checksum result {current_checksum & self.__header.checksum}')
		return current_checksum & self.__header.checksum == 0

	def __str__(self):
		content = f"""
		---
		[HEADER]: {self.__header}
		[Payload]: {self.__payload}
		---"""
		return content