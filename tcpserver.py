import globals
import logging
import argparse

from tcp.server import TCP_SERVER


if __name__ == "__main__":
	parser = argparse.ArgumentParser('TCP data receiver')
	parser.add_argument('file', type=str, help='output file to write to')
	parser.add_argument('lstn_port', type=int, help='server listening port')
	parser.add_argument('ack_addr', type=str, help='IP address for reaching client for ACK')
	parser.add_argument('ack_port', type=int, help='Port address for reaching client for ACK ')
	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG)
	
	server = TCP_SERVER(
		lsten_port=args.lstn_port,
		ack_addr=args.ack_addr,
		ack_port=args.ack_port)
	server.start(args)
