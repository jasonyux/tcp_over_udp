import logging
import struct

from .header import TCPHeader, Flags
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
		checksum = self.__compute_checksum()
		checksum = ~checksum & 0xffff # 1s complement and mask
		self.__header.set_checksum(checksum)
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
		# reset
		self.__header.set_checksum(prev_checksum)
		return checksum 

	def is_corrupt(self):
		current_checksum = self.__compute_checksum()
		logging.debug(f'checksum result {current_checksum & self.__header.checksum}')
		return current_checksum & self.__header.checksum != 0

	def __str__(self):
		content = f"""
		---
		[HEADER]: {self.__header}
		[Payload]: {self.__payload}
		---"""
		return content


def serialize(packet:Packet):
	"""Converts the Human-readable Packet to bytes

	Args:
		packet (Packet): Packet abstraction

	Returns:
		bytes: actual bytes of the packet 
		(i.e. 20 bytes header + up to 512 byte payload)
	"""
	line_1 = struct.pack('HH', packet.header.src_port, packet.header.dst_port)
	line_2 = struct.pack('I', packet.header.seq_num)
	line_3 = struct.pack('I', packet.header.ack_num)
	# convert flag
	flag = packet.header.flags
	flag_map = int(f"{flag.ack}{flag.cwr}{flag.ece}{flag.fin}{flag.syn}", 2)
	line_4 = struct.pack('BBH', packet.header.header_len, flag_map, packet.header.rcvwd)
	line_5 = struct.pack('HH', packet.header.checksum, 0)
	# final
	final = line_1 + line_2 + line_3 + line_4 + line_5
	if len(packet.payload) != 0:
		final += packet.payload
	return final

def deserialize(packet):
	"""Converts bytes to a HUman-readable Packet

	Args:
		packet (bytes): network transmitted bytes

	Returns:
		Packet: human-readable Packet
	"""
	total_size = len(packet)
	src_port, dst_port, \
		seq_num, ack_num, \
			header_len, flags, rcvwd, \
				checksum, urg, \
					data = struct.unpack(f'HHIIBBHHH{total_size-20}s', packet)
	flags = format(flags, '#07b')
	header = TCPHeader(
		src_port=src_port,
		dst_port=dst_port,
		seq_num=seq_num, 
		ack_num=ack_num, 
		_flags=Flags(
			cwr=int(flags[3]), 
			ece=int(flags[4]), 
			ack=int(flags[2]), 
			syn=int(flags[6]),
			fin=int(flags[5])),
		rcvwd=rcvwd)
	header.set_checksum(checksum)
	packet = Packet(header, data)
	return packet