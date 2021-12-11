import logging
import time

from pathlib import Path
from structure.header import TCPHeader, Flags
from structure.packet import Packet
from utils import serialize, util
from socket import *

class UDP_SERVER():
	"""Underlying unreliable UDP server/receiver
	"""
	
	def __init__(self, lsten_port, ack_addr, ack_port) -> None:
		self.__serveraddress = ('', lsten_port) # the socket is reachable by any address the machine happens to have
		self.__ack_address = ack_addr, ack_port
		self.__buffersize = 2048
		self.__socket = socket(family=AF_INET, type=SOCK_DGRAM)
		return

	@property
	def _serveraddress(self):
		return self.__serveraddress

	@property
	def _socket(self):
		return self.__socket

	@property
	def ack_addr(self):
		return self.__ack_address

	def send_packet(self, packet:Packet, client_address):
		socket = self.__socket
		packet = serialize.serialize(packet)
		ret = socket.sendto(packet, client_address)
		return ret

	def receive_packet(self):
		server = self.__socket
		raw_packet, client_address = server.recvfrom(self.__buffersize)
		try:
			# e.g. corruption
			packet = serialize.deserialize(raw_packet)
			logging.debug(f'rcvd {packet}')
		except:
			packet = None
		return packet, client_address

	def get_info(self):
		info = self.__socket.getsockname()
		return info


class TCP_SERVER(UDP_SERVER):
	# state flags
	CLOSED = 0
	LISTEN = 1
	ESTABLISHED = 2
	CLOSE_WAIT = 3
	LAST_ACK = 4

	def __init__(self, lsten_port, ack_addr, ack_port) -> None:
		"""A TCP reliable receiver implementation

		Args:
			lsten_port (int): port to listen/bind to
			ack_addr (str): IP address to send ACK
			ack_port (int): port to send ACK
		"""
		super().__init__(lsten_port, ack_addr, ack_port)
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0
		self.__received_seqs = set()
		self.__state = TCP_SERVER.CLOSED

		# for fin specifically
		self.__fin_packets = {}

	@property
	def state(self):
		"""Returns the current state of the TCP connection
		Possible values are 
			CLOSED = 0
			LISTEN = 1
			ESTABLISHED = 2
			CLOSE_WAIT = 3
			LAST_ACK = 4

		Returns:
			[int]: current state information
		"""
		return self.__state

	def __next_seq(self, payload):
		num_bytes = len(payload) or 1
		return self.__seq_num + num_bytes

	def __post_send(self, packet:Packet):
		self.__seq_num = self.__next_seq(packet.payload)
		return

	def send(self, payload):
		"""Construct and send a packet with payload @payload

		Args:
			payload (bytes): payload, should not exceeed MSS=512

		Returns:
			int: 0=packet accepted, -1=packet rejected (due to full window)
		"""
		# 1. construct packet
		client_address = self.ack_addr
		_, src_port = self.get_info()
		header = TCPHeader(
			src_port=src_port, 
			dst_port=client_address[1], 
			seq_num=self.__seq_num, 
			ack_num=self.__ack_num, 
			_flags=Flags(cwr=0, ece=0, ack=1, syn=0,fin=0), 
			rcvwd=10)
		packet = Packet(header, payload)
		packet.compute_checksum()

		# 2. send packet
		self.send_packet(packet, client_address)

		# 3. update seq_num, etc
		self.__post_send(packet)
		return packet

	def __next_ack(self, packet:Packet):
		# 1. add the received packet to list of received_seqs
		if packet.header.seq_num < self.__ack_num:
			return self.__ack_num
		
		self.__received_seqs.add(packet)
		rcvd_min_seq = min([pkt.header.seq_num for pkt in self.__received_seqs])
		logging.debug(f"rcvd_min_seq={rcvd_min_seq} and self.__ack_num={self.__ack_num}")
		if rcvd_min_seq > self.__ack_num:
			return self.__ack_num # the first packet is out of order
		
		# 2. find out the largest continously recevied one
		largest_seq_pkt, self.__received_seqs = util.largest_contionus(
			self.__received_seqs, 
			sort_key=lambda pkt: pkt.header.seq_num,
			next_diff=lambda pkt: len(pkt.payload) or 1,
			pop=True)

		# 3. ACK = last_recvned_packet.seq_num + len
		num_bytes = len(largest_seq_pkt.payload) or 1
		logging.debug(f"new_ack_cumu={largest_seq_pkt.header.seq_num + num_bytes}")
		return largest_seq_pkt.header.seq_num + num_bytes
	
	def __post_recv(self, packet:Packet):
		logging.debug(f"current seq_num={self.__seq_num}, old_ack_num={self.__ack_num}")
		
		self.__ack_num = self.__next_ack(packet) # position of next byte
		logging.debug(f'sender new cumu ack {self.__ack_num}')
		if packet.header.is_fin() and packet.header.seq_num + 1 >= self.__ack_num:
			logging.info('closing connection')
			logging.info(packet)
			packet = self.close_connection(packet)
			logging.info('connection closed')
		return packet

	def receive(self):
		"""Blocking receive a packet

		Returns:
			(Packet, tuple): returns (Packet, client_address) if packet is not corrupt. 
			Else, returns (None, client_address)
		"""
		# 1. receive packet
		packet, client_address = self.receive_packet()
		# 2. check if packet is corrupt
		if packet is not None and not packet.is_corrupt():
			# 3. if not, update ack_num
			packet = self.__post_recv(packet)
		else:
			packet = None
		return packet, client_address

	def __send_fin(self):
		logging.debug('sending fin')
		logging.debug(f"current seq_num={self.__seq_num}, old_ack_num={self.__ack_num}")
		# 1. construct packet
		client_address = self.ack_addr
		_, src_port = self.get_info()
		header = TCPHeader(
			src_port=src_port, 
			dst_port=client_address[1], 
			seq_num=self.__seq_num, 
			ack_num=self.__ack_num, 
			_flags=Flags(cwr=0, ece=0, ack=0, syn=0, fin=1), 
			rcvwd=10)
		packet = Packet(header, '')
		packet.compute_checksum()

		# 2. send packet
		self.send_packet(packet, client_address)
		self.__state = TCP_SERVER.LAST_ACK
		logging.info(f'sent {packet}')
		# store for potential retransmit
		self.__fin_packets[packet.header.seq_num] = packet

		# 3. update seq_num, etc
		self.__post_send(packet)
		return packet

	def __wait_fin_ack(self, fin_packet:Packet):
		logging.debug('wait fin ack')
		
		fin_seq = fin_packet.header.seq_num
		while self.__state == TCP_SERVER.LAST_ACK:
			packet, client_address = self.receive_packet()
			# check if packet is corrupt
			if packet is not None and not packet.is_corrupt():
				# check if is the ACK for fin
				logging.debug(f'sent {fin_packet.header} need fin ack wait: {packet.header}')
				if packet.header.ack_num >= fin_seq + 1 and packet.header.is_ack():
					self.send('')
					self.__state = TCP_SERVER.CLOSED
					logging.debug(f"sent: {packet}")
					return packet
				else:
					packet = self.__fin_packets.get(packet.header.ack_num)
					if packet is None:
						logging.error(f"No fix for packet {packet}, I have {self.__fin_packets}")
					else:
						self.send_packet(packet, client_address)
			# wait
			time.sleep(0.2)
		return

	def reset(self):
		"""Resets the server's state. Waiting for a new client
		"""
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0
		self.__state = TCP_SERVER.LISTEN
		self.__received_seqs = set()
		pass

	def close_connection(self, packet:Packet):
		"""Inner helper function when client intiates FIN requests. 
		
		Essentially performs the FIN handshake with the client and does 
		:func:self.reset when done.

		Args:
			packet (Packet): FIN packet received from client

		Returns:
			None: None
		"""
		# 1. send ack for fin
		packet = self.send('')
		logging.info(f'sent {packet}')
		# store for potential retransmit
		self.__fin_packets[packet.header.seq_num] = packet
		self.__state = TCP_SERVER.CLOSE_WAIT

		# 2. sned fin
		fin_packet = self.__send_fin()

		# 3. wait for ack
		# fin_ack = self.__wait_fin_ack(fin_packet) #TODO
		# 4. reset
		self.reset()
		
		logging.debug(f"reset to {self.__seq_num} and {self.__ack_num}")
		return None

	def start(self, args):
		"""Start the server
		Start to listen and accept clients.
		Reset when client intiates FIN requests and completed the handshake

		Args:
			args (namespace): command line arguments for the program, e.g. which file to write to
		"""
		server = self._socket
		server.bind(self._serveraddress)
		# other application related init
		init(args)
		self.__state = TCP_SERVER.LISTEN
		print("The server is ready to receive")

		while True:
			try:
				self.__state = TCP_SERVER.ESTABLISHED
				service_client(self, args)
				self.__state = TCP_SERVER.LISTEN
			except Exception as err:
				print(err)
				pass
		return


def init(args):
	if not Path(args.file).exists():
		Path(args.file).touch()
	else:
		with open(args.file, 'r+') as f:
			f.truncate(0)
	return

def __to_file(packets:Packet, dst:str):
	with open(dst, 'ab+') as openfile:
		for packet in packets:
			logging.debug(f'writing {packet.payload} to {packet.header.seq_num}')
			openfile.seek(packet.header.seq_num)
			"""
			content = openfile.read()
			# insert new content
			start_pos = packet.header.seq_num
			content = __insert_content(content, start_pos, packet.payload)
			# write
			openfile.write(content)
			openfile.truncate()
			"""
			openfile.write(packet.payload)

rcvd_seq = set()
rcvd = []
last_wrote = 0
def to_file(packet:Packet, dst:str):
	"""Writes the content of a packet to a file

	Args:
		packet (Packet): a non-corrupt packet received
		dst (str): destination file to write to
	"""
	global rcvd, last_wrote

	if packet.header.seq_num in rcvd_seq:
		return
	
	rcvd.append(packet)
	rcvd_seq.add(packet.header.seq_num)
	# 1. sort
	rcvd = sorted(rcvd, key=lambda pkt: pkt.header.seq_num)
	# logging.debug([(pkt.payload, pkt.header.seq_num) for pkt in rcvd])

	# 2. find consecutive ones
	largest_seq_pkt, ready_packets = util.largest_contionus(
			set(rcvd), 
			sort_key=lambda pkt: pkt.header.seq_num,
			next_diff=lambda pkt: len(pkt.payload) or 1,
			pop=False)
	ready_packets = sorted(ready_packets, key=lambda pkt: pkt.header.seq_num)
	smallest_seq_pkt = None if len(ready_packets) == 0 else ready_packets[0]
	if  len(ready_packets) == 0 or smallest_seq_pkt.header.seq_num > last_wrote:
		return

	# 3. write the consecutive ones to file
	ready_packets = sorted(ready_packets, key=lambda pkt: pkt.header.seq_num)
	__to_file(ready_packets, dst)
	last_wrote = largest_seq_pkt.header.seq_num + (len(largest_seq_pkt.payload) or 1)

	# 4. clean up
	new_rcvd = []
	for pkt in rcvd:
		if pkt not in ready_packets:
			new_rcvd.append(pkt)
	rcvd = new_rcvd
	return

def service_client(server:TCP_SERVER, args):
	"""Specifies what to do when received something from client
	
	Essentially does 1) receive 2) check packet received 
	3) write to file 4) send ACK

	Args:
		server (TCP_SERVER): running instance of TCP_SERVER
		args (namespace): command line arguments
	"""
	# receive packet
	received, client_address = server.receive()
	logging.info(f"[LOG] serviced {client_address}")
	logging.info(f"{received or 'Discarded or Residual'}")

	if received is not None:
		# write to file
		to_file(received, dst=args.file)

	# send ACK
	if server.state == TCP_SERVER.ESTABLISHED:
		server.send('')
	return