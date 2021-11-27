import globals

from socket import *
from structure.header import TCPHeader, Flags
from structure.packet import Packet
from utils import serialize


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


def get_pass(client:UDP_CLIENT):
	while True:
		msg = input("Input: ") + f"; I am at {client.get_info()}"
		
		# send packet
		_, src_port = client.get_info()
		header = TCPHeader(src_port, client.dst_addr[1], -1, -2, Flags(-4,-5,-6,-7,-8), -9)
		packet = Packet(header, msg)
		client.send_packet(packet)

		# receive packet
		received = client.receive_packet()
		print(received)
	client.terminate()
	return

if __name__ == "__main__":
	client = UDP_CLIENT(
		udpl_ip=globals.UDPL_IP_ADDR,
		udpl_port=globals.UDPL_LSTN_PORT,
		ack_lstn_port=globals.ACK_LSTN_PORT)
	
	get_pass(client)