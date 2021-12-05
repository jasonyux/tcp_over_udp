import globals
import logging
import argparse
import time
import threading

from tcp.client import TCP_CLIENT

STOP_FLAG = False

def __receive(client):
	global STOP_FLAG
	while not STOP_FLAG:
		received = client.receive() # blocking
		logging.info(received)
	return

def send_file(client:TCP_CLIENT, args):
	global STOP_FLAG
	"""
	while True:
		msg = input("Input: ")# + f"; I am at {client.get_info()}"
		
		# send packet
		client.send(msg)

		# receive packet
		received = client.receive()
		logging.info(received)

		if "quit" in msg:
			client.terminate()
			break
	"""
	receiv_thread = threading.Thread(target=__receive, args=(client,))
	with open(args.file, 'r') as openfile:
		receiv_thread.start()
		for line in openfile:
			ret = client.send(line)
			while ret == -1:
				time.sleep(1)
				ret = client.send(line)
		STOP_FLAG = True
		receiv_thread.join()
		client.terminate()
	return


if __name__ == "__main__":
	parser = argparse.ArgumentParser('TCP data sender')
	parser.add_argument('file', type=str, help='output file to send')
	args = parser.parse_args()

	logging.basicConfig(level=logging.DEBUG)

	client = TCP_CLIENT(
		udpl_ip=globals.UDPL_IP_ADDR,
		udpl_port=globals.UDPL_LSTN_PORT,
		ack_lstn_port=globals.ACK_LSTN_PORT)
	
	send_file(client, args)