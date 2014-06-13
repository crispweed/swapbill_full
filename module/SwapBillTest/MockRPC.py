from __future__ import print_function
from collections import deque
from SwapBill import RPC ## for setup only

# (worked fine, as long as queries did non contain non hashable elements such as lists)
#class Host_WithDict(object):
	#def __init__(self):
		#self._d = {}
	#def _connect(self, password):
		#self._actualHost = RPC.Host('http://litecoinrpc:' + password + '@localhost:19332')
	#def call(self, *arguments):
		#if hasattr(self, '_actualHost'):
			#print('\t\texpectedQuery =', arguments.__repr__())
			#result = self._actualHost.call(*arguments)
			#print('\t\tqueryResult =', result.__repr__())
			#print('\t\trpcHost._d[expectedQuery] = queryResult')
			#return result
		#return self._d[arguments]

class Host(object):
	def __init__(self):
		self.queue = deque()
	def _connect(self, password):
		self._actualHost = RPC.Host('http://litecoinrpc:' + password + '@localhost:19332')
	def call(self, *arguments):
		if hasattr(self, '_actualHost'):
			print('\t\texpectedQuery =', arguments.__repr__())
			try:
				result = self._actualHost.call(*arguments)
			except (RPC.RPCFailureWithMessage,RPC.RPCFailureWithMessage) as e:
				print('\t\tqueryResult =', e.__repr__())
				print('\t\trpcHost.queue.append((expectedQuery, queryResult))')
				raise e
			print('\t\tqueryResult =', result.__repr__())
			print('\t\trpcHost.queue.append((expectedQuery, queryResult))')
			return result
		expectedQuery, result = self.queue.popleft()
		if arguments != expectedQuery:
			print('arguments:', arguments)
			print('expectedQuery:', expectedQuery)
		assert arguments == expectedQuery
		if isinstance(result, (RPC.RPCFailureWithMessage,RPC.RPCFailureWithMessage)):
			raise result
		return result

