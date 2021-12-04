import globals

from tcp.client import TCP_CLIENT


def send_file(client:TCP_CLIENT):
	while True:
		msg = input("Input: ")# + f"; I am at {client.get_info()}"
		
		# send packet
		client.send(msg)

		# receive packet
		received = client.receive()
		print(received)
	client.terminate()
	return


if __name__ == "__main__":
	client = TCP_CLIENT(
		udpl_ip=globals.UDPL_IP_ADDR,
		udpl_port=globals.UDPL_LSTN_PORT,
		ack_lstn_port=globals.ACK_LSTN_PORT)
	
	send_file(client)