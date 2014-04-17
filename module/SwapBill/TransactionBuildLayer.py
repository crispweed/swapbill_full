from SwapBill import RawTransaction

class TransactionBuildLayer(object):
	def __init__(self, host):
		self._host = host

	def getUnspent(self):
		## higher level interface that caches scriptPubKey for later lookup
		## this to be called once before each transaction send
		## (but can also be called without subsequent transaction send)
		self._scriptPubKeyLookup = {}
		addresses = []
		amounts = []
		asInputs = []
		allUnspent = self._host.getUnspent()
		for output in allUnspent:
			assert 'address' in output
			key = (output['txid'], output['vout'])
			assert not key in self._scriptPubKeyLookup
			self._scriptPubKeyLookup[key] = output['scriptPubKey']
			addresses.append(output['address'])
			amounts.append(output['amount'])
			asInputs.append((output['txid'], output['vout']))
		return addresses, amounts, asInputs

	def sendTransaction(self, tx):
		# higher level transaction send interface
		unsignedData = RawTransaction.Create(tx, self._scriptPubKeyLookup)
		unsignedHex = RawTransaction.ToHex(unsignedData)
		return self._host.signAndSend(unsignedHex)

	#def getNonSwapBillUnspent(self, swapBillBalances):
		#return GetUnspent.AllNonSwapBill(self._addressVersion, self._rpcHost, swapBillBalances)
	#def getSingleUnspentForAddress(self, pubKeyHash):
		#return GetUnspent.SingleForAddress(self._addressVersion, self._rpcHost, pubKeyHash)

	#def getAddressesWithUnspent(self, swapBillBalances):
		#return GetUnspent.AddressesWithUnspent(self._addressVersion, self._rpcHost, swapBillBalances)

