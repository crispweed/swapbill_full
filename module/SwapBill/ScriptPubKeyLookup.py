from SwapBill import Address

class Lookup(object):
	def __init__(self, unspentList, singleAdditionalUnspent = None):
		self._d = {}
		for unspent in unspentList:
			key = (unspent[0], unspent[1])
			assert not key in self._d
			self._d[key] = unspent[2]
		if not singleAdditionalUnspent is None:
			unspent = singleAdditionalUnspent
			key = (unspent[0], unspent[1])
			assert not key in self._d
			self._d[key] = unspent[2]
	def lookupScriptPubKey(self, key):
		return self._d[key]
