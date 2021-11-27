import globals

from socket import *
from structure.header import TCPHeader, Flags
from structure.packet import Packet
from utils import serialize


PROXY_SEND_PORT = 41194


class UDP_SERVER():
	def __init__(self, lsten_port, ack_addr, ack_port) -> None:
		self.__serveraddress = ('', lsten_port) # the socket is reachable by any address the machine happens to have
		self.__ack_address = ack_addr, ack_port
		self.__buffersize = 2048
		self.__socket = socket(family=AF_INET, type=SOCK_DGRAM)
		return

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
	
	def start(self):
		server = self.__socket
		server.bind(self.__serveraddress)
		print("The server is ready to receive")

		while True:
			try:
				service_client(self)
			except Exception as err:
				print(err)
				pass
		return


def service_client(server:UDP_SERVER):
	# receive packet
	received, client_address = server.receive_packet()
	print(f"[LOG] servicing {client_address}")
	print(received)

	# send packet
	client_address = server.ack_addr
	_, src_port = server.get_info()
	header = TCPHeader(src_port, client_address[1], 1, 2, Flags(4,5,6,7,8), 9)
	packet = Packet(header, "hello I am server")
	server.send_packet(packet, client_address)
	return

if __name__ == "__main__":
	server = UDP_SERVER(
		lsten_port=globals.SERVER_LSTN_PORT,
		ack_addr=globals.ACK_IP_ADDR,
		ack_port=globals.ACK_LSTN_PORT)
	server.start()
