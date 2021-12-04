from structure.header import TCPHeader, Flags
from structure.packet import Packet
from utils import serialize
from socket import *

class UDP_SERVER():
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
		return serialize.deserialize(raw_packet), client_address

	def get_info(self):
		info = self.__socket.getsockname()
		return info


class TCP_SERVER(UDP_SERVER):
	def __init__(self, lsten_port, ack_addr, ack_port) -> None:
		super().__init__(lsten_port, ack_addr, ack_port)
		self.__seq_num = 0
		self.__ack_num = 0 # assumes both sides start with seq=0

	def __next_seq(self, payload):
		num_bytes = len(payload)
		return self.__seq_num + num_bytes

	def __post_send(self, packet:Packet):
		self.__seq_num = self.__next_seq(packet.payload)
		return

	def send(self, payload):
		# 1. construct packet
		client_address = self.ack_addr
		_, src_port = self.get_info()
		header = TCPHeader(
			src_port=src_port, 
			dst_port=client_address[1], 
			seq_num=self.__seq_num, 
			ack_num=self.__ack_num, 
			_flags=Flags(4,5,6,7,8), 
			rcvwd=9)
		packet = Packet(header, payload)

		# 2. send packet
		self.send_packet(packet, client_address)

		# 3. update seq_num, etc
		self.__post_send(packet)
		return

	def __next_ack(self, packet:Packet):
		num_bytes = len(packet.payload)
		return packet.header.seq_num + num_bytes
	
	def __post_recv(self, packet:Packet):
		self.__ack_num = self.__next_ack(packet) # position of next byte
		return

	def receive(self):
		# 1. receive packet
		packet, client_address = self.receive_packet()

		# 2. update ack_num
		self.__post_recv(packet)
		return packet, client_address

	def start(self):
		server = self._socket
		server.bind(self._serveraddress)
		print("The server is ready to receive")

		while True:
			try:
				service_client(self)
			except Exception as err:
				print(err)
				pass
		return


def service_client(server:TCP_SERVER):
	# receive packet
	received, client_address = server.receive()
	print(f"[LOG] servicing {client_address}")
	print(received)

	# send packet
	server.send('server')
	return