import pickle
import struct
import logging
from structure.packet import Packet
from structure.header import TCPHeader, Flags


def serialize(packet:Packet):
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