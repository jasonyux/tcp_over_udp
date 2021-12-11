# TCP over UDP
computer networks: programming assignment 2. Implementing a TCP client/server ensuring reliable delivery when the underlying channel is UDP.

## Setup

This project assumes the following:
- a compiled/working `newudpl` copied to current directory
- a working `python3.x` (referred to as `python` for the rest of the documentation)
- run `pip install -r requirements.txt` for installing some additional dependencies, such as `argparse`.
  
## Project Structure

The project structure should look like:
```bash
.
├── README.md
├── __init__.py
├── file1.txt			[sample text file for sender transmission]
├── globals.py
├── image1.png			[sample non-text file for sender transmission]
├── requirements.txt
├── submission_docs		[folder containing screen dumps and pdf write up]
├── structure			[code for TCP packet related structure]
│   ├── __init__.py
│   ├── header.py
│   └── packet.py
├── tcp					[code for TCP reliable delivery]
│   ├── __init__.py
│   ├── client.py
│   └── server.py
├── tcpclient.py	[code for sender when using TCP reliable delivery]
├── tcpserver.py	[code for receiver when using TCP reliable delivery]
└── utils			[code for components used in TCP reliable delivery]
    ├── __init__.py
    ├── __pycache__
    ├── sampler.py
    ├── timer.py
    └── util.py
```

## Usage
Below are some configurations that have been already tested and should work. They also demonstrate some of the capabilities of the code. 

> Note: 
> 
> - all tests have been done in a **local environment**. It should work even if one of the server/client/newudpl is in remote, but that haven't yet been tested.
> - all examples below also assume your local loopback address is `127.0.0.1`. This should be the case unless you have done something special before about it.
-  **Packet Loss, Bit Error, Out of Order, and Delay tolerant**.
    1. start up the `newudpl` by:
        
		```bash
		➜ ./newudpl -O 50 -L 50 -B 20 -d 2
		```

		or for robustness `./newudpl -O 50 -L 50 -B 20 -d 2 -i 127.0.0.1:41191 -o 127.0.0.1:41194`
    2. start up the `tcpserver` by:
		```bash
		➜ python tcpserver.py file2.txt 41194 127.0.0.1 41191
		```
		(assumed `python3`)
    3. start up the `tcpclient` by:
		```bash
		➜ python tcpclient.py file1.txt 127.0.0.1 41192 2048 41191
		```
		where `file1.txt` can be replaced by any file with extension `.txt` in this example.
	
	> Note:
	> - if bit error `-b` is made to be very big, it will incur a chance that `checksum` itself will not be able to detect error. In that case, server/client may hang as corrupted packets will be treated as normal packets.
-  **Transmitting non-text files**.
    
    Currently it should also be able to handle any non-text files, as long as the extension matches up in the server and client side. For example, I have placed a `image1.png` file under the directory, and you can try transmitting that by:
    1. start up the `newupdl` by:

		```bash
		➜ ./newudpl -O 50 -L 50 -B 20 -d 2
		```
		or for robustness `./newudpl -O 50 -L 50 -B 20 -d 2 -i 127.0.0.1:41191 -o 127.0.0.1:41194`
    2. start up the `tcpserver` by
		```bash
		➜ python tcpserver.py image2.png 41194 127.0.0.1 41191
		```
		(or any other file name you want, such as `hello.png`, etc. You just need to make sure in this example it ends with `.png`)
    3. start up the `tcpclient` by:
		```bash
		➜ python tcpclient.py image1.png 127.0.0.1 41192 2048 41191
		```
		(or any other file yuo want, as long as the file extension of the `file` argument on server and client matches up)
- **Multiple Client Runs**
  
  The above setups should also work through multiple runs of client. In other words:

  1. start up `newudpl` and `server.py`
  2. run `tcpclient.py` to transfer some files
  3. When step (ii) terminated, you can run `tcpclient.py` again (without restarting the server) as the server should have resetted and will treat the connection as a new client!

## Documentations
A detailed report on how various parts of the code work can be found under `submission_docs/report.md` or `submission_docs/report.pdf`.

Screen dumps running instances I tested can be found under `submission_docs` as well.
