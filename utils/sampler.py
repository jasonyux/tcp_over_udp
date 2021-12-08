import logging

class RTTSampler(object):
	def __init__(self, init_interval) -> None:
		super().__init__()
		self.__timeout_interval = init_interval

		# used for estimation
		self.__estimated_rtt = init_interval
		self.__alpha = 0.125
		self.__dev_rtt = 0
		self.__beta = 0.25
		self.__gamma = 2

		# used for doubling timeout
		self.__within_timeout = False
		pass
	
	def double_interval(self, enabled=True, restore=True):
		self.__within_timeout = enabled
		if enabled is False and restore: # when sending new packets, do not restore
			self.__timeout_interval = round(self.__estimated_rtt + self.__gamma * self.__dev_rtt, 3)
		return
		
	def update_interval(self, sample_rtt):
		# we received something, switch back to using normal timeout
		self.__within_timeout = False

		alpha = self.__alpha
		beta = self.__beta
		self.__estimated_rtt = (1-alpha) * self.__estimated_rtt + alpha * sample_rtt
		self.__dev_rtt = (1-beta) * self.__dev_rtt + beta * (abs(sample_rtt - self.__estimated_rtt))
		self.__timeout_interval = round(self.__estimated_rtt + self.__gamma * self.__dev_rtt, 3)
		logging.debug(f"""
		sample with {sample_rtt}
		new self.__estimated_rtt {self.__estimated_rtt}
		new self.__dev_rtt {self.__dev_rtt}
		rounded new timeout interval {self.__timeout_interval}
		""")
		return

	def get_interval(self):
		if self.__within_timeout:
			self.__timeout_interval *= 2
		return self.__timeout_interval