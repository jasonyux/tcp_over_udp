import globals
import logging
import argparse
import time
import threading
from structure import packet

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
		client.terminate()
		receiv_thread.join()
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