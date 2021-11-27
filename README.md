# TCP over UDP
computer networks: programming assignment 2

## Usage
Below is the setup for local testing
1. Starting up the `newudpl` proxy server
	```bash
	➜ ./newudpl -i 127.0.0.1:*
	Network emulator with UDP link
	Copyright (c) 2021 by Columbia University; all rights reserved

	Link established:
	localhost(127.0.0.1)/***** ->
		Xiaos-MacBook-Pro.local(127.0.0.1)/41192
	/41193 ->
		localhost(127.0.0.1)/41194

	emulating speed  : 1000 kb/s
	delay            : 0.000000 sec
	Ethernet         : 10 Mb/s
	Queue buffersize : 8192 bytes

	error rate
	Random packet loss: 0%
	Bit error         : 0 (1/100000 per bit)
	Out of order      : 0%
	Jitter            : 0% of delay
	```
2. Start the server client respectively by:
	```bash
	➜ python tcpserver.py 
	The server is ready to receive
	```
	and
	```bash
	➜SIGINT python tcpclient.py 
	Input: (type something)
	```