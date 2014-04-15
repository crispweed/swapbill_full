from SwapBill import RPC ## for setup only

class Host(object):
	def __init__(self):
		self._d = {}
	def _connect(self, password):
		self._actualHost = RPC.Host('http://litecoinrpc:' + password + '@localhost:19332')
	def call(self, *arguments):
		if hasattr(self, '_actualHost'):
			print('\t\texpectedQuery =', arguments.__repr__())
			result = self._actualHost.call(*arguments)
			print('\t\tqueryResult =', result.__repr__())
			print('\t\trpcHost._d[expectedQuery] = queryResult')
			return result
		return self._d[arguments]
