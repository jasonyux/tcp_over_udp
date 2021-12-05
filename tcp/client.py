import logging
import threading
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
	BEGIN_CLOSE = 5

	CLOSE_WAIT_TIME = 30

	def __init__(self, udpl_ip, udpl_port, ack_lstn_port):
		super().__init__(udpl_ip, udpl_port, ack_lstn_port)
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0
		self.__timer = timer.TCPTimer(2, self.retransmit)
		self.__window = []
		self.__window_size = 10
		self.__send_base = 0 # smallest unacked seq num
		self.__state = TCP_CLIENT.ESTABLISHED

		# used for threading
		self.rcv_lock = threading.Lock()
		self.__thread_fin_packets = []
		self.__thread_fin_packets_id = set()

	@property
	def state(self):
		return self.__state

	def __next_seq(self, payload):
		num_bytes = len(payload) or 1
		return self.__seq_num + num_bytes

	def __post_send(self, packet:Packet):
		logging.debug("at __post_send")
		# 1. update seq_num
		self.__seq_num = self.__next_seq(packet.payload)
		# 2. update window
		self.__window.append(packet)
		# 3. check if timer is running
		if not self.__timer.is_alive():
			self.__timer.restart()
		# checknig twice in case there is __timer timedout in one of them
		if not self.__timer.is_alive():
			logging.debug("restart timer")
			self.__timer.restart()			
		return

	def send(self, payload:str):
		# 0. consult window
		if len(self.__window) == self.__window_size:
			return -1
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
		packet.compute_checksum()

		# 2. send packet
		self.send_packet(packet)

		# 3. update seq_num, etc
		self.__post_send(packet)
		return 0

	def retransmit(self):
		logging.debug('retransmitting')
		# 0. if connection is closed, stop whatever you haven't finished
		if self.__state == TCP_CLIENT.CLOSED or len(self.__window) == 0:
			return
		# 1. retransmit
		# self.__window = sorted(self.__window, key= lambda pkt: pkt.header.seq_num)
		packet = self.__window[0]
		logging.debug(f'retransmitting {packet}')

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
		logging.debug(f'at __wait_server_ack')
		fin_seq = fin_packet.header.seq_num
		self.__state = TCP_CLIENT.FIN_WAIT_1

		# find FIN ACK packet
		check_threading = True
		while self.__state == TCP_CLIENT.FIN_WAIT_1:
			# wait
			time.sleep(1)
			self.rcv_lock.acquire()
			"""
			Obtain LOCK here so that:
			Case 1. the other thread in tcpclient.py obtained the lock and went rcv. 
				- self.__thread_fin_packets is 100% updated. This works
			Case 2. I got the lock
				- the other thread obviously went rcv. Also works
			"""
			# check list first
			if check_threading:
				for packet in self.__thread_fin_packets:
					# check if is the ACK for fin
					logging.debug(f'fin ack wait: checking {packet.header}')
					if packet.header.ack_num == fin_seq + 1 and packet.header.is_ack():
						self.__state = TCP_CLIENT.FIN_WAIT_2
						self.__thread_fin_packets.remove(packet)
						self.rcv_lock.release()
						return packet
				check_threading = False
			# receive
			packet = self.receive()
			self.rcv_lock.release()
			
			logging.debug(f'fin ack wait: {packet.header}')
			if packet.header.ack_num == fin_seq + 1 and packet.header.is_ack():
				self.__state = TCP_CLIENT.FIN_WAIT_2
				return packet
		return

	def __send_ack(self):
		logging.debug("at __send_ack")
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
		packet.compute_checksum()

		# 2. send packet
		self.send_packet(packet)

		# 3. No need to do anything
		self.__post_send(packet)
		return packet

	def __wait_server_fin(self):
		# wait for fin from server
		check_thread = True
		while self.__state == TCP_CLIENT.FIN_WAIT_2:
			# wait
			time.sleep(1)
			"""
			Obtain LOCK here so that:
			Case 1. the other thread in tcpclient.py obtained the lock and went rcv. 
				- self.__thread_fin_packets is 100% updated. This works
			Case 2. I got the lock
				- the other thread obviously went rcv. Also works
			"""
			self.rcv_lock.acquire()
			if check_thread:
				logging.debug(f'fin wait thread')
				for packet in self.__thread_fin_packets:
					if packet.header.is_fin():
						# send ack
						final_ack = self.__send_ack()
						self.__state = TCP_CLIENT.TIME_WAIT
						self.rcv_lock.release()
						return
				check_thread = False
			# try to receive
			packet = self.receive()
			self.rcv_lock.release()
			# check if it is fin
			logging.debug(f'fin wait: {packet.header}')
			if packet.header.is_fin():
				# send ack
				final_ack = self.__send_ack()
				break

		self.__state = TCP_CLIENT.TIME_WAIT
		return final_ack

	def __time_wait(self, final_ack:Packet):
		logging.debug(f'at __time_wait')
		fin_seq = final_ack.header.seq_num
		start_time = time.time()
		while time.time() - start_time < TCP_CLIENT.CLOSE_WAIT_TIME:
			# if received ack for final ack, done
			self.rcv_lock.acquire()
			packet = self.receive()
			self.rcv_lock.release()

			logging.debug(f'at __time_wait with {packet.header}')
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

	def terminate(self):
		# 0. wait for all other retransmission to be done
		while len(self.__window) > 0:
			# the other thread will timeout and retransmit
			time.sleep(1)

		# change state so that the other thread will not receive packets
		self.__state = TCP_CLIENT.BEGIN_CLOSE

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
		packet.compute_checksum()
		self.__fin_start_seq = self.__seq_num

		# 2. send packet
		self.send_packet(packet)

		# 3. start timers
		self.__post_send(packet)

		# 4. wait for acks and etc
		self.__post_fin(packet)
		return super().terminate()

	# for multithreading
	def update_fin_packets(self, packet:Packet):
		# in case if the thread grabbed one of those packets, client won't be able to terminate
		# if packet.header.ack_num >= self.__fin_start_seq or packet.header.seq_num >= self.__fin_start_seq:
		logging.debug("adding in update_fin_packets")
		if len(self.__thread_fin_packets) == 0:
			logging.debug("added")
			self.__thread_fin_packets.append(packet)
		else:
			if packet not in self.__thread_fin_packets:
				logging.debug("added")
				self.__thread_fin_packets.append(packet)
		return
