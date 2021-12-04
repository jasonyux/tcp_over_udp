import globals

from socket import *
from structure.header import TCPHeader, Flags
from structure.packet import Packet
from tcp.client import TCP_CLIENT


def send_file(client:TCP_CLIENT):
	while True:
		msg = input("Input: ")# + f"; I am at {client.get_info()}"
		
		# send packet
		client.send(msg)
		"""
		_, src_port = client.get_info()
		header = TCPHeader(src_port, client.dst_addr[1], -1, -2, Flags(-4,-5,-6,-7,-8), -9)
		packet = Packet(header, msg)
		client.send_packet(packet)
		"""

		# receive packet
		received = client.receive()
		"""
		received = client.receive_packet()
		"""
		print(received)
	client.terminate()
	return

if __name__ == "__main__":
	client = TCP_CLIENT(
		udpl_ip=globals.UDPL_IP_ADDR,
		udpl_port=globals.UDPL_LSTN_PORT,
		ack_lstn_port=globals.ACK_LSTN_PORT)
	
	send_file(client)