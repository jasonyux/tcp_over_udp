import logging
import time

from threading import Timer
from typing import *

class TCPTimer(object):
	def __init__(self, interval: float, function: Callable[..., Any], *args, **kwargs) -> None:
		self.__interval = interval
		self.__function = function
		self.__args = args
		self.__kwargs = kwargs
		self.__timer = None

	@property
	def interval(self):
		return self.__interval

	def start(self):
		if self.__timer is not None and self.__timer.is_alive():
			logging.error('timer already running')
			return
		self.__timer = Timer(self.__interval, self.__function, args=self.__args, kwargs=self.__kwargs)
		self.__timer.start()
		logging.info('timer started')
		return

	def is_alive(self):
		if self.__timer is None:
			return False
		return self.__timer.is_alive()
	
	def cancel(self):
		if self.__timer is None:
			return
		self.__timer.cancel()
		return
	
	def restart(self, new_interval=None):
		if self.__timer is not None and self.__timer.is_alive():
			self.__timer.cancel()
		# calling self.start() causes problem as the thread might NOT be finished 
		# (e.g. function still executing)
		self.__interval = new_interval or self.__interval
		self.__timer = Timer(self.__interval, self.__function, args=self.__args, kwargs=self.__kwargs)
		self.__timer.start()
		return