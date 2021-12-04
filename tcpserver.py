import globals
import logging

from tcp.server import TCP_SERVER


if __name__ == "__main__":
	logging.basicConfig(level=logging.DEBUG)
	
	server = TCP_SERVER(
		lsten_port=globals.SERVER_LSTN_PORT,
		ack_addr=globals.ACK_IP_ADDR,
		ack_port=globals.ACK_LSTN_PORT)
	server.start()
