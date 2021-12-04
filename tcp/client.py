import logging
import time

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
	# state flags
	CLOSED = 0
	ESTABLISHED = 1
	FIN_WAIT_1 = 2
	FIN_WAIT_2 = 3
	TIME_WAIT = 4

	CLOSE_WAIT_TIME = 30

	def __init__(self, udpl_ip, udpl_port, ack_lstn_port):
		super().__init__(udpl_ip, udpl_port, ack_lstn_port)
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0
		self.__timer = timer.TCPTimer(2, self.retransmit)
		self.__window = []
		self.__send_base = 0 # smallest unacked seq num
		self.__state = TCP_CLIENT.ESTABLISHED

	def __next_seq(self, payload):
		num_bytes = len(payload) or 1
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
			_flags=Flags(cwr=10, ece=0, ack=0, syn=0,fin=0),
			rcvwd=9)
		packet = Packet(header, payload)

		# 2. send packet
		self.send_packet(packet)

		# 3. update seq_num, etc
		self.__post_send(packet)
		return

	def retransmit(self):
		logging.debug('retransmitting')
		# 0. if connection is closed, stop whatever you haven't finished
		if self.__state == TCP_CLIENT.CLOSED:
			return
		# 1. retransmit
		# self.__window = sorted(self.__window, key= lambda pkt: pkt.header.seq_num)
		packet = self.__window[0]
		self.send_packet(packet)
		# 2. restart timer
		prev_interval = self.__timer.interval
		self.__timer.restart(prev_interval)
		return

	def __next_ack(self, packet:Packet):
		num_bytes = len(packet.payload) or 1
		return packet.header.seq_num + num_bytes
	
	def __post_recv(self, packet:Packet):
		# 0. If I received a FIN, then ACK will be the same as last one
		if packet.header.is_fin():
			self.__ack_num = self.__next_ack(packet) # position of next byte
			self.__window = []
		
		# 1. update window, received ACK
		if packet.header.ack_num > self.__send_base:
			self.__send_base = packet.header.ack_num
			logging.debug(f"post_recv, send_base={self.__send_base}")
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

	def __wait_server_ack(self, fin_packet:Packet):
		fin_seq = fin_packet.header.seq_num
		self.__state = TCP_CLIENT.FIN_WAIT_1
		while self.__state == TCP_CLIENT.FIN_WAIT_1:
			packet = self.receive()
			# check if is the ACK for fin
			logging.debug(f'fin ack wait: {packet.header}')
			if packet.header.ack_num == fin_seq + 1 and packet.header.is_ack():
				self.__state = TCP_CLIENT.FIN_WAIT_2
				self.__window = []
				return packet
			
			# wait
			time.sleep(0.2)
		return

	def __send_ack(self):
		# 1. construct packet
		_, src_port = self.get_info()
		header = TCPHeader(
			src_port=src_port,
			dst_port=self.dst_addr[1], 
			seq_num=self.__seq_num, 
			ack_num=self.__ack_num, 
			_flags=Flags(cwr=10, ece=0, ack=1, syn=0,fin=0),
			rcvwd=9)
		packet = Packet(header, '')

		# 2. send packet
		self.send_packet(packet)

		# 3. No need to do anything
		self.__post_send(packet)
		return packet

	def __wait_server_fin(self):
		# wait for fin from server
		while self.__state == TCP_CLIENT.FIN_WAIT_2:
			packet = self.receive()
			# check if it is fin
			logging.debug(f'fin wait: {packet.header}')
			if packet.header.is_fin():
				# send ack
				final_ack = self.__send_ack()
				self.__state = TCP_CLIENT.TIME_WAIT
				break
			
			# wait
			time.sleep(0.2)
		return final_ack

	def __time_wait(self, final_ack:Packet):
		fin_seq = final_ack.header.seq_num
		start_time = time.time()
		while time.time() - start_time < TCP_CLIENT.CLOSE_WAIT_TIME:
			# if received ack for final ack, done
			packet = self.receive()
			logging.debug(f'at __time_wait {packet.header}')
			if packet.header.ack_num == fin_seq + 1 and packet.header.is_ack():
				self.__state = TCP_CLIENT.FIN_WAIT_2
				break
			time.sleep(0.2)
		self.__state = TCP_CLIENT.CLOSED
		return

	def __post_fin(self, packet:Packet):
		# 1. wait for ACK for FIN sent
		self.__wait_server_ack(packet)
		# 2. wait for FIN from server
		final_ack = self.__wait_server_fin()
		# 3. time wait
		self.__time_wait(final_ack)
		return

	def __post_terminate(self, packet:Packet):
		# 1. check if timer is running, since we sent something
		if not self.__timer.is_alive():
			self.__timer.start()
		# 2. update seq_num
		self.__seq_num = self.__next_seq(packet.payload)

		# 3. update window
		self.__window.append(packet)
		# 4. wait until received fin from server
		self.__post_fin(packet)
		return

	def terminate(self):
		# 1. construct FIN packet
		_, src_port = self.get_info()
		header = TCPHeader(
			src_port=src_port, 
			dst_port=self.dst_addr[1], 
			seq_num=self.__seq_num, 
			ack_num=self.__ack_num, 
			_flags=Flags(cwr=0, ece=0, ack=0, syn=0, fin=1),
			rcvwd=9)
		packet = Packet(header, '')

		# 2. send packet
		self.send_packet(packet)

		# 3. update seq_num, etc
		self.__post_terminate(packet)
		return super().terminate()
