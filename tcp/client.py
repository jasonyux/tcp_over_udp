import logging

from socket import *
from structure.packet import Packet
from structure.header import TCPHeader, Flags
from utils import serialize, timer

class UDP_CLIENT():
	def __init__(self, udpl_ip, udpl_port, ack_lstn_port):
		self.__dst_address = (udpl_ip, udpl_port)
		self.__buffersize = 2048
		self.__socket = socket(family=AF_INET, type=SOCK_DGRAM)
		self.__socket.bind(('127.0.0.1', ack_lstn_port))

	@property
	def dst_addr(self):
		return self.__dst_address

	def send_packet(self, packet:Packet):
		socket = self.__socket
		packet = serialize.serialize(packet)
		ret = socket.sendto(packet, self.__dst_address)
		return ret

	def receive_packet(self):
		raw_packet, _ = self.__socket.recvfrom(self.__buffersize)
		return serialize.deserialize(raw_packet)

	def get_info(self):
		info = self.__socket.getsockname()
		return info

	def terminate(self):
		self.__socket.close()
		return self


class TCP_CLIENT(UDP_CLIENT):
	def __init__(self, udpl_ip, udpl_port, ack_lstn_port):
		super().__init__(udpl_ip, udpl_port, ack_lstn_port)
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0
		self.__timer = timer.TCPTimer(2, self.retransmit)
		self.__window = []
		self.__send_base = 0 # smallest unacked seq num

	def __next_seq(self, payload):
		num_bytes = len(payload)
		return self.__seq_num + num_bytes

	def __post_send(self, packet:Packet):
		# 1. check if timer is running
		if not self.__timer.is_alive():
			self.__timer.start()
		# 2. update seq_num
		self.__seq_num = self.__next_seq(packet.payload)

		# 3. update window
		self.__window.append(packet)
		return

	def send(self, payload:str):
		# 1. construct packet
		_, src_port = self.get_info()
		header = TCPHeader(
			src_port=src_port, 
			dst_port=self.dst_addr[1], 
			seq_num=self.__seq_num, 
			ack_num=self.__ack_num, 
			_flags=Flags(-4,-5,-6,-7,-8), 
			rcvwd=-9)
		packet = Packet(header, payload)

		# 2. send packet
		self.send_packet(packet)

		# 3. update seq_num, etc
		self.__post_send(packet)
		return

	def retransmit(self):
		logging.debug('retransmitting')
		# 1. retransmit
		# self.__window = sorted(self.__window, key= lambda pkt: pkt.header.seq_num)
		packet = self.__window[0]
		self.send_packet(packet)
		# 2. restart timer
		prev_interval = self.__timer.interval
		self.__timer.restart(prev_interval)
		return

	def __next_ack(self, packet:Packet):
		num_bytes = len(packet.payload)
		return packet.header.seq_num + num_bytes
	
	def __post_recv(self, packet:Packet):
		# 1. update window, received ACK
		if packet.header.ack_num > self.__send_base:
			self.__send_base = packet.header.ack_num
			# update packets in window
			new_window = []
			for unacked in self.__window:
				# cumulative ack
				if unacked.header.seq_num >= self.__send_base:
					new_window.append(unacked)
			self.__window = new_window
			# if still some unacked packets
			if len(self.__window) > 0:
				self.__timer.restart()
			# all done
			else:
				self.__timer.cancel()
		
			self.__ack_num = self.__next_ack(packet) # position of next byte
		else:
			# TODO:duplicate ack, fast retransmit possible
			pass
		return

	def receive(self):
		# 1. receive ACK packet
		packet = self.receive_packet()

		# 2. update ack_num
		self.__post_recv(packet)
		return packet
