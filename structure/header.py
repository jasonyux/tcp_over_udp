from typing import Callable


class Printable(object):
	def __init__(self) -> None:
		super().__init__()
	
	def __str__(self):
		ret = ""
		for attribute in dir(self):
			if attribute[:1] != "_":
				data = getattr(self, attribute)
				if not isinstance(data, Callable):
					ret += f"{attribute}: {data}\n\t\t\t"
		return ret


class Flags(Printable):
	def __init__(self, cwr, ece, ack, syn, fin) -> None:
		super().__init__()
		self.__cwr = cwr
		self.__ece = ece
		self.__ack = ack
		self.__syn = syn
		self.__fin = fin

	@property
	def cwr(self):
		return self.__cwr

	@property
	def ece(self):
		return self.__ece

	@property
	def ack(self):
		return self.__ack

	@property
	def syn(self):
		return self.__syn

	@property
	def fin(self):
		return self.__fin

	def __int__(self):
		return self.cwr + self.ece + self.ack + self.syn + self.fin


class Header(Printable):
	def __init__(self) -> None:
		super().__init__()

	def compute_checksum(self):
		ret = 0
		for attribute in dir(self):
			if attribute[:1] != "_":
				data = getattr(self, attribute)
				if not isinstance(data, Callable):
					ret += int(data)
		return ret


class TCPHeader(Header):
	def __init__(self, src_port, dst_port, seq_num, ack_num, _flags, rcvwd) -> None:
		self.__src_port = src_port
		self.__dst_port = dst_port
		self.__seq_num = seq_num
		self.__ack_num = ack_num
		self.__flags = _flags
		self.__rcvwd = rcvwd
		self.__checksum = 0
		self.__header_len = 20
		self.__checksum = self.compute_checksum()
	
	@property
	def src_port(self):
		return self.__src_port

	@property
	def dst_port(self):
		return self.__dst_port

	@property
	def seq_num(self):
		return self.__seq_num

	@property
	def ack_num(self):
		return self.__ack_num

	@property
	def flags(self):
		return self.__flags

	@property
	def rcvwd(self):
		return self.__rcvwd

	@property
	def checksum(self):
		return self.__checksum

	@property
	def header_len(self):
		return self.__header_len


	