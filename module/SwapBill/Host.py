from __future__ import print_function
from os import path
from SwapBill import ParseConfig, RPC, RawTransaction, Address, TransactionFee, Amounts
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

class SigningFailed(ExceptionReportedToUser):
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
		self._cachedBlockHash = None

# unspents, addresses, transaction encode and send

	def getUnspent(self):
		## lowest level getUnspent interface
		result = []
		allUnspent = self._rpcHost.call('listunspent')
		for output in allUnspent:
			if not 'address' in output: ## is this check required?
				continue
			filtered = {}
			for key in ('txid', 'vout', 'scriptPubKey'):
				filtered[key] = output[key]
			filtered['address'] = Address.ToPubKeyHash(self._addressVersion, output['address'])
			filtered['amount'] = Amounts.ToSatoshis(output['amount'])
			result.append(filtered)
		return result

	def getNewNonSwapBillAddress(self):
		return Address.ToPubKeyHash(self._addressVersion, self._rpcHost.call('getnewaddress'))
	def getNewSwapBillAddress(self):
		return Address.ToPubKeyHash(self._addressVersion, self._rpcHost.call('getnewaddress', 'SwapBill'))

	def addressIsMine(self, pubKeyHash):
		address = Address.FromPubKeyHash(self._addressVersion, pubKeyHash)
		validateResults = self._rpcHost.call('validateaddress', address)
		result = validateResults['ismine']
		assert result in (True, False)
		return result

	def signAndSend(self, unsignedTransactionHex):
		## lowest level transaction send interface
		signingResult = self._rpcHost.call('signrawtransaction', unsignedTransactionHex)
		if signingResult['complete'] != True:
			raise SigningFailed("RPC call to signrawtransaction did not set 'complete' to True")
		signedHex = signingResult['hex']
		# move out of lowest level send interface?
		# (or repeat in higher level code?)
		if not TransactionFee.TransactionFeeIsSufficient(self._rpcHost, signedHex):
			raise InsufficientTransactionFees()
		txID = self._rpcHost.call('sendrawtransaction', signedHex)
		return txID

# block chain tracking, transaction stream and decoding

	def getBlockHash(self, blockIndex):
		return self._rpcHost.call('getblockhash', blockIndex)

	def _getBlock_Cached(self, blockHash):
		if self._cachedBlockHash != blockHash:
			self._cachedBlock = self._rpcHost.call('getblock', blockHash)
			self._cachedBlockHash = blockHash
		return self._cachedBlock

	def getNextBlockHash(self, blockHash):
		block = self._getBlock_Cached(blockHash)
		return block.get('nextblockhash', None)
	def getBlockTransactions(self, blockHash):
		block = self._getBlock_Cached(blockHash)
		transactions = block['tx']
		assert len(transactions) >= 1
		result = []
		for txHash in transactions[1:]:
			txHex = self._rpcHost.call('getrawtransaction', txHash)
			result.append((txHash, txHex))
		return result

# convenience

	def formatAddressForEndUser(self,  pubKeyHash):
		return Address.FromPubKeyHash(self._addressVersion, pubKeyHash)
	def addressFromEndUserFormat(self,  address):
		return Address.ToPubKeyHash(self._addressVersion, address)

	def formatAccountForEndUser(self, account):
		txID, vOut = account
		return txID + ':' + str(vOut)
