from SwapBill import Address

class Lookup(object):
	def __init__(self, addressVersion, rpcHost):
		self._addressVersion = addressVersion
		self._rpcHost = rpcHost
	def getSourceFor(self, txID, vOut):
		redeemedTX = self._rpcHost.call('getrawtransaction', txID, 1)
		output = redeemedTX['vout'][vOut]
		if not 'scriptPubKey' in output:
			return None
		scriptPubKey = output['scriptPubKey']
		if not 'addresses' in scriptPubKey:
			return None
		addresses = scriptPubKey['addresses']
		if len(addresses) != 1:
			return None
		return Address.ToPubKeyHash(self._addressVersion, addresses[0])
