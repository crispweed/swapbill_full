from __future__ import print_function
import os
from os import path
from SwapBill import ParseConfig, RPC, RawTransaction, Address, Amounts
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

class SigningFailed(ExceptionReportedToUser):
	pass
class MaximumSignedSizeExceeded(Exception):
	pass

class Host(object):
	def __init__(self, useTestNet, dataDirectory, configFile=None):
		if configFile is None:
			if os.name == 'nt':
				configFile = path.join(path.expanduser("~"), 'AppData', 'Roaming', 'Litecoin', 'litecoin.conf')
			else:
				configFile = path.join(path.expanduser("~"), '.litecoin', 'litecoin.conf')

		with open(configFile, mode='rb') as f:
			configFileBuffer = f.read()
		clientConfig = ParseConfig.Parse(configFileBuffer)

		if useTestNet:
			self._addressVersion = b'\x6f'
			self._privateKeyAddressVersion = b'\xef'
		else:
			self._addressVersion = b'\x30'
			self._privateKeyAddressVersion = b'\xbf'

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
		#assert path.isdir(dataDirectory)
		#self._wallet = Wallet.Wallet(path.join(dataDirectory, 'wallet.txt'))

		blockHashForBlockZero = self._rpcHost.call('getblockhash', 0)
		self._hasExtendTransactionsInBlockQuery = True
		try:
			transactionsInBlockZero = self._rpcHost.call('getrawtransactionsinblock', blockHashForBlockZero)
		#except RPC.MethodNotFoundException:
		except RPC.RPCFailureException: # ** we get a different RPC error for this on Windows
			self._hasExtendTransactionsInBlockQuery = False

		self._submittedTransactionsFileName = path.join(dataDirectory, 'submittedTransactions.txt')

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

	def signAndSend(self, unsignedTransactionHex, privateKeys, maximumSignedSize):
		## lowest level transaction send interface
		signingResult = self._rpcHost.call('signrawtransaction', unsignedTransactionHex)
		if signingResult['complete'] != True:
			privateKeysWif = []
			for privateKey in privateKeys:
				privateKeys_WIF.append(Address.PrivateKeyToWIF(privateKey, self._privateKeyAddressVersion))
			signingResult = self._rpcHost.call('signrawtransaction', signingResult['hex'], None, privateKeys_WIF)
		if signingResult['complete'] != True:
			raise SigningFailed("RPC call to signrawtransaction did not set 'complete' to True")
		signedHex = signingResult['hex']
		byteSize = len(signedHex) / 2
		if byteSize > maximumSignedSize:
			raise MaximumSignedSizeExceeded()
		try:
			txID = self._rpcHost.call('sendrawtransaction', signedHex)
		except RPC.RPCFailureException as e:
			raise ExceptionReportedToUser('RPC error sending signed transaction: ' + str(e))
		with open(self._submittedTransactionsFileName, mode='a') as f:
			f.write(txID)
			f.write('\n')
			f.write(signedHex)
			f.write('\n')
		return txID

# block chain tracking, transaction stream and decoding

	def getBlockHashAtIndexOrNone(self, blockIndex):
		try:
			return self._rpcHost.call('getblockhash', blockIndex)
		except RPC.RPCFailureWithMessage as e:
			if str(e) == 'Block number out of range.':
				return None
		except RPC.RPCFailureException:
			pass
		raise ExceptionReportedToUser('Unexpected RPC error in call to getblockhash.')
	def _getBlock_Cached(self, blockHash):
		if self._cachedBlockHash != blockHash:
			self._cachedBlock = self._rpcHost.call('getblock', blockHash)
			self._cachedBlockHash = blockHash
		return self._cachedBlock

	def getNextBlockHash(self, blockHash):
		block = self._getBlock_Cached(blockHash)
		return block.get('nextblockhash', None)
	def getBlockTransactions(self, blockHash):
		result = []
		if self._hasExtendTransactionsInBlockQuery:
			transactions = self._rpcHost.call('getrawtransactionsinblock', blockHash)
			assert len(transactions) >= 1
			for entry in transactions[1:]:
				result.append((entry['txid'], entry['hex']))
		else:
			block = self._getBlock_Cached(blockHash)
			transactions = block['tx']
			assert len(transactions) >= 1
			for txHash in transactions[1:]:
				txHex = self._rpcHost.call('getrawtransaction', txHash)
				result.append((txHash, txHex))
		return result

	def getMemPoolTransactions(self):
		mempool = self._rpcHost.call('getrawmempool')
		result = []
		for txHash in mempool:
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
