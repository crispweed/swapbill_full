from __future__ import print_function
from os import path
from SwapBill import ParseConfig, RPC, GetUnspent, RawTransaction, Address, TransactionFee

class SigningFailed(Exception):
	pass
class InsufficientTransactionFees(Exception):
	pass

class Host(object):
	def __init__(self, useTestNet, configFile=None):
		if configFile is None:
			configFile = path.join(path.expanduser("~"), '.litecoin', 'litecoin.conf')

		with open(configFile, mode='rb') as f:
			configFileBuffer = f.read()
		clientConfig = ParseConfig.Parse(configFileBuffer)

		assert useTestNet
		self._addressVersion = b'\x6f'

		RPC_HOST = clientConfig.get('externalip', 'localhost')

		try:
			RPC_PORT = clientConfig['rpcport']
		except KeyError:
			if useTestNet:
				RPC_PORT = 19332
			else:
				RPC_PORT = 9332

		assert int(RPC_PORT) > 1 and int(RPC_PORT) < 65535

		try:
			RPC_USER = clientConfig['rpcuser']
			RPC_PASSWORD = clientConfig['rpcpassword']
		except KeyError:
			print('Values for rpcuser and rpcpassword must both be set in your config file.')
			exit()

		self._rpcHost = RPC.Host('http://' + RPC_USER + ':' + RPC_PASSWORD + '@' + RPC_HOST + ':' + str(RPC_PORT))

	def getNewChangeAddress(self):
		return Address.ToPubKeyHash(self._addressVersion, self._rpcHost.call('getnewaddress'))
	def getNewSwapBillAddress(self):
		return Address.ToPubKeyHash(self._addressVersion, self._rpcHost.call('getnewaddress', 'SwapBill'))

	def getNonSwapBillUnspent(self, swapBillBalances):
		return GetUnspent.AllNonSwapBill(self._addressVersion, self._rpcHost, swapBillBalances)
	def getSingleUnspentForAddress(pubKeyHash):
		return GetUnspent.SingleForAddress(self._addressVersion, self._rpcHost, pubKeyHash)

	## TODO - get rid of scriptPubKeyLookup parameter here, cache unspents provided in the methods above and look up there instead
	def sendTransaction(self, tx, scriptPubKeyLookup):
		unsignedData = RawTransaction.Create(tx, scriptPubKeyLookup)
		unsignedHex = RawTransaction.ToHex(unsignedData)
		#signingResult = rpcHost.call('signrawtransaction_simplified', unsignedHex)
		signingResult = self._rpcHost.call('signrawtransaction', unsignedHex)
		if signingResult['complete'] != True:
			raise SigningFailed()
		signedHex = signingResult['hex']
		if not TransactionFee.TransactionFeeIsSufficient(self._rpcHost, signedHex):
			raise InsufficientTransactionFees()
		txID = self._rpcHost.call('sendrawtransaction', signedHex)
		return txID
		#print('Transaction sent with transactionID:')
		#print(txID)

