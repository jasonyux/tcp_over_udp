import logging
import threading
import time
import structure.packet

from socket import *
from structure.packet import Packet
from structure.header import TCPHeader, Flags
from utils import timer
from utils.sampler import RTTSampler

class UDP_CLIENT():
	"""Underlying UDP client for communication
	"""

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
		packet = structure.packet.serialize(packet)
		ret = socket.sendto(packet, self.__dst_address)
		return ret

	def receive_packet(self):
		raw_packet, _ = self.__socket.recvfrom(self.__buffersize)
		return structure.packet.deserialize(raw_packet)

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

	INIT_TIMEOUT_INTERVAL = 1
	CLOSE_WAIT_TIME = 30

	def __init__(self, udpl_ip, udpl_port, window_size, ack_lstn_port):
		"""TCP reliable sender implementation

		Args:
			udpl_ip (str): udpl IP address to send to (proxy address)
			udpl_port (int): udpl port address to send to
			window_size (int): number of packets allowed in current window
			ack_lstn_port (int): port number of receiving ACK from server
		"""
		super().__init__(udpl_ip, udpl_port, ack_lstn_port)
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0
		self.__timer = timer.TCPTimer(TCP_CLIENT.INIT_TIMEOUT_INTERVAL, self.retransmit)
		self.__window = []
		self.__window_size = window_size
		self.__send_base = 0 # smallest unacked seq num
		self.__state = TCP_CLIENT.ESTABLISHED

		# used for RTT sampler
		self.__waiting_packets = {}
		self.__rtt_sampling = RTTSampler(TCP_CLIENT.INIT_TIMEOUT_INTERVAL)

		# used for threading
		self.window_lock = threading.Lock()
		self.rcv_lock = threading.Lock()
		self.__thread_fin_packets = []

	@property
	def state(self):
		"""Returns current state of the connection

		Takes value from
			CLOSED = 0 \n
			ESTABLISHED = 1 \n
			FIN_WAIT_1 = 2 \n
			FIN_WAIT_2 = 3 \n
			TIME_WAIT = 4 \n
			BEGIN_CLOSE = 5 \n

		Returns:
			[int]: current state information
		"""
		return self.__state

	def __next_seq(self, payload):
		num_bytes = len(payload) or 1
		return self.__seq_num + num_bytes

	def __post_send(self, packet:Packet):
		logging.debug("at __post_send")
		# 1. update seq_num
		self.__seq_num = self.__next_seq(packet.payload)

		# 2. update window
		self.window_lock.acquire()
		self.__window.append(packet)

		# 3. check if timer is running
		self.__rtt_sampling.double_interval(enabled=False, restore=False)
		if not self.__timer.is_alive():
			self.__timer.restart(new_interval=self.__rtt_sampling.get_interval())
		# checknig twice in case there is __timer timedout in one of them
		if not self.__timer.is_alive():
			logging.debug("restart timer")
			self.__timer.restart(new_interval=self.__rtt_sampling.get_interval())
		# 4. update RTT sampler
		packet_ack = packet.header.seq_num + (len(packet.payload) or 1)
		start_time = self.__waiting_packets.get(packet_ack)
		if start_time is None:
			self.__waiting_packets[packet_ack] = time.time()
			logging.debug(f'adding __waiting_packets {packet_ack} for payload={packet.payload} at {time.time()}')
		else: # this should not happen
			logging.error(f'self.__waiting_packets already has {packet}')
		self.window_lock.release()
		return

	def send(self, payload:str):
		"""Reliably send a packet with payload @payload

		Args:
			payload (str or bytes): payload

		Returns:
			int: success=0
		"""
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
			_flags=Flags(cwr=0, ece=0, ack=0, syn=0,fin=0),
			rcvwd=10)
		packet = Packet(header, payload)
		packet.compute_checksum()

		# 2. send packet
		self.send_packet(packet)

		# 3. update seq_num, etc
		self.__post_send(packet)
		return 0

	def retransmit(self):
		"""Actions when timer timed out, retransmitting the oldest UNACKED packet

		1. Attempts to aquire the window lock, as it will need to extract a packet
		from the current window
		2. retransmit
		3. double timeout interval and restart timer
		4. update self.__waiting_packets, which contains packet that could be RTT sampled.
		If there is a timeout, then all packets in current window should NOT be inside
		self.__waiting_packets (as discussed in post @331)
		"""
		logging.debug('retransmitting')
		# 0. if connection is closed, stop whatever you haven't finished
		self.window_lock.acquire() # need to read
		if self.__state == TCP_CLIENT.CLOSED or len(self.__window) == 0:
			self.window_lock.release()
			return
		# 1. retransmit
		# self.__window = sorted(self.__window, key= lambda pkt: pkt.header.seq_num)
		
		packet = self.__window[0]
		logging.debug(f'retransmitting {packet}')
		self.send_packet(packet)

		# 2. restart timer
		self.__rtt_sampling.double_interval() # doubling timeout interval
		new_timeout_interval = self.__rtt_sampling.get_interval()
		logging.debug(f'doubling to {new_timeout_interval}')
		self.__timer.restart(new_interval=new_timeout_interval)

		# 3. do not track RTT for retransmitted packets and all packets inside the window
		tmp = [pkt.header.seq_num + (len(pkt.payload) or 1) for pkt in self.__window]
		logging.debug(f"currently having {tmp}")
		for unacked in self.__window:
			packet_ack = unacked.header.seq_num + (len(unacked.payload) or 1)
			start_time = self.__waiting_packets.get(packet_ack)
			if start_time is not None:
				self.__waiting_packets.pop(packet_ack, None)
		self.window_lock.release()
		logging.debug(f'now {self.__waiting_packets.keys()}')
		return

	def __next_ack(self, packet:Packet):
		num_bytes = len(packet.payload) or 1
		return packet.header.seq_num + num_bytes
	
	def __post_recv(self, packet:Packet):
		# 0. If I received a FIN, then ACK will be the same as last one
		if packet.header.is_fin():
			self.__ack_num = self.__next_ack(packet) # position of next byte
		
		logging.debug(f"{packet.header.ack_num} > send_base: {self.__send_base}")
		self.__rtt_sampling.double_interval(enabled=False)
		# 1. update window, received ACK
		if packet.header.ack_num > self.__send_base:
			# 2. new ACK received
			
			self.__send_base = packet.header.ack_num
			logging.debug(f"post_recv, send_base={self.__send_base}")
			# update packets in window
			self.window_lock.acquire()
			new_window = []
			for unacked in self.__window:
				# cumulative ack
				if unacked.header.seq_num >= self.__send_base:
					new_window.append(unacked)
			self.__window = new_window
			self.window_lock.release()
			# if still some unacked packets
			if len(self.__window) > 0:
				self.__timer.restart(new_interval=self.__rtt_sampling.get_interval())
			# all done
			else:
				self.__timer.cancel()
		
			self.__ack_num = self.__next_ack(packet) # position of next byte

			# 3. update RTT
			start_time = self.__waiting_packets.get(packet.header.ack_num)
			if start_time is not None: # not retransmitted
				end_time = time.time()
				self.__rtt_sampling.update_interval(end_time - start_time)
				self.__waiting_packets.pop(packet.header.ack_num, None)
				logging.debug(f'first time received {packet.header.ack_num} at {end_time}, now {self.__waiting_packets.keys()}')
			return
		else:
			# TODO:duplicate ack, fast retransmit possible
			pass
		return
		

	def receive(self):
		"""Receving a packet from server

		Returns:
			[Packet]: packet received.
		"""
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
					if packet.header.ack_num >= fin_seq + 1 and packet.header.is_ack():
						self.__state = TCP_CLIENT.FIN_WAIT_2
						self.__thread_fin_packets.remove(packet)
						self.__window = []
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
			_flags=Flags(cwr=0, ece=0, ack=1, syn=0,fin=0),
			rcvwd=10)
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
				logging.debug(f'fin wait check thread')
				for packet in self.__thread_fin_packets:
					if packet.header.is_fin():
						# send ack
						# final_ack = self.__send_ack()
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
				# final_ack = self.__send_ack()
				break

		self.__state = TCP_CLIENT.TIME_WAIT
		#return final_ack
		return None

	def __time_wait(self, final_ack:Packet):
		logging.debug(f'at __time_wait')
		self.rcv_lock.acquire()
		fin_seq = final_ack.header.seq_num
		start_time = time.time()
		while time.time() - start_time < TCP_CLIENT.CLOSE_WAIT_TIME:
			# if received ack for final ack, done
			packet = self.receive()

			logging.debug(f'at __time_wait with {packet.header}')
			if packet.header.ack_num >= fin_seq + 1 and packet.header.is_ack():
				self.__state = TCP_CLIENT.FIN_WAIT_2
				self.__window = []
				break
			time.sleep(0.2)
		self.__state = TCP_CLIENT.CLOSED
		self.rcv_lock.release()
		return

	def reset(self):
		"""Clean up (optional as the program terminates anyway)
		"""
		self.__state = TCP_CLIENT.CLOSED
		self.window_lock.acquire()
		self.__timer.cancel()
		self.__window = []
		self.window_lock.release()
		return

	def __post_fin(self, packet:Packet):
		# 1. wait for ACK for FIN sent
		self.__wait_server_ack(packet)
		# 2. wait for FIN from server
		final_ack = self.__wait_server_fin()
		# 3. time wait
		# self.__time_wait(final_ack) #TODO
		self.reset()
		return

	def terminate(self):
		"""Terminate the connection

		After the FIN handshake, close the underlying UDP socket.

		Returns:
			None: None
		"""
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
			rcvwd=10)
		packet = Packet(header, b'')
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
		"""Method for adding packets into the self.__thread_fin_packets list

		This is needed since I am doing multithreading: a threading running :func:receive could
		accidentally grabbed a FIN ACK packet, which the main thread would be waiting on. This 
		would cause a HANG in the program. 

		So the solution is to use lock + a safety measure such that if those termination packets
		are grabbed, it is appended in the self.__thread_fin_packets list which the main thread
		will also check.

		Args:
			packet (Packet): packet in the FIN handshake accidentally grabbed by slave thread
		"""
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
