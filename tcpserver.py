import globals
import logging
import argparse

from tcp.server import TCP_SERVER


if __name__ == "__main__":
	parser = argparse.ArgumentParser('TCP data receiver')
	parser.add_argument('file', type=str, help='output file to write to')
	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG)

	server = TCP_SERVER(
		lsten_port=globals.SERVER_LSTN_PORT,
		ack_addr=globals.ACK_IP_ADDR,
		ack_port=globals.ACK_LSTN_PORT)
	server.start(args)
