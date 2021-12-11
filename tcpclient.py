import globals
import logging
import argparse
import time
import threading
import os.path as path

from tcp.client import TCP_CLIENT


def __receive(client:TCP_CLIENT):
	while client.state == TCP_CLIENT.ESTABLISHED:
		# check again
		client.rcv_lock.acquire()
		if client.state == TCP_CLIENT.ESTABLISHED:
			received = client.receive() # blocking
			logging.info(f'state {client.state}')
			if client.state != TCP_CLIENT.ESTABLISHED:
				client.update_fin_packets(received)
			logging.info(f'thread recevied: {received}')
		
		client.rcv_lock.release()
		time.sleep(0.1)
	return

def send_file(client:TCP_CLIENT, args):
	"""Send (any type of) file to server

	This will do two things: 1) start a thread to do BLOCKING receive 2) start a loop,
	read MSS=512 bytes, and send to server.

	Args:
		client (TCP_CLIENT): a configured TCP_CLIENT, which knows where to send data to
		args (namespace): command line arguments for the program
	"""
	receiv_thread = threading.Thread(target=__receive, args=(client,))
	with open(args.file, 'rb') as openfile:
		receiv_thread.start()
		data = openfile.read(globals.MSS)
		while data != b'':
			ret = client.send(data)
			while ret == -1:
				time.sleep(1)
				ret = client.send(data)
			data = openfile.read(globals.MSS)
		client.terminate()
		receiv_thread.join()
	return

def init_args(args):
	"""Check whether if arguments specified are expected
	"""
	# check window size
	if args.window_size >= globals.MSS and args.window_size % globals.MSS == 0:
		args.window_size = args.window_size / globals.MSS
	else:
		raise Exception(f"Please specify to be '{args.window_size}' to be integer multiple of MSS={globals.MSS}")
	
	# check file existence
	if not path.exists(args.file):
		raise Exception(f"File: '{args.file}' does not exist!")
	return args


if __name__ == "__main__":
	parser = argparse.ArgumentParser('TCP data sender')
	parser.add_argument('file', type=str, help='output file to send')
	parser.add_argument('udpl_addr', type=str, help='IP address of UDPL to send to')
	parser.add_argument('udpl_port', type=int, help='Port number of UDPL to send to')
	parser.add_argument('window_size', type=int, help='Sender window size in bytes. (multiple of MSS=512B)')
	parser.add_argument('ack_port', type=int, help='Port number to listen on, for receiving ACK from server')
	args = parser.parse_args()
	args = init_args(args)

	logging.basicConfig(level=logging.DEBUG)

	client = TCP_CLIENT(
		udpl_ip=args.udpl_addr,
		udpl_port=args.udpl_port,
		window_size=args.window_size,
		ack_lstn_port=args.ack_port)
	
	send_file(client, args)