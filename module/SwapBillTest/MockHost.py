import binascii
from SwapBill import RawTransaction, TransactionFee
from SwapBill import Host ## just for insufficient fee exception
from SwapBill import Address ## just for bad address exception
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

def MakeTXID(i):
	txid = '00' * 31 + '{:02X}'.format(i)
	# make case consistent with hexlify!
	txid = binascii.hexlify(binascii.unhexlify(txid.encode('ascii'))).decode('ascii')
	return txid

def MatchPubKeyHashAndRemovePrivateKey(keyGenerator, pubKeyHash, privateKeys):
	remainingPrivateKeys = []
	while True:
		if not privateKeys:
			raise Exception('Failed to sign input.')
		privateKey = privateKeys[0]
		generatedPubKeyHash = keyGenerator.privateKeyToPubKeyHash(privateKey)
		privateKeys = privateKeys[1:]
		if generatedPubKeyHash == pubKeyHash:
			return remainingPrivateKeys + privateKeys
		remainingPrivateKeys.append(privateKey)

class MockHost(object):
	defaultOwner = '0'

	def __init__(self, keyGenerator, ownerID=None):
		if ownerID is None:
			ownerID = self.defaultOwner
		self._keyGenerator = keyGenerator
		self._id = ownerID
		self._nextChange = 0
		self._nextSwapBill = 0
		# start block is zero, already confirmed, contains no transactions
		# block 1 will be confirmed when it has transactions and next block is queried
		self._nextBlock = 1
		self._transactionsByBlock = {0:[]}
		self._memPool = []
		self._nextTXID = 0
		self._nextSuppliedOutput = 0
		self._unspent = []
		self._keyPairs = []
		self.holdNewTransactions = False

	def _setOwner(self, id):
		assert not '_' in id
		self._id = id
	def _getOwner(self):
		return self._id

	def _addUnspent(self, amount):
		self._nextTXID += 1
		txid = MakeTXID(self._nextTXID)
		vout = 7
		toAdd = {'txid':txid, 'vout':vout}
		pubKeyHash = self.getNewNonSwapBillAddress()
		scriptPubKey = RawTransaction.ScriptPubKeyForPubKeyHash(pubKeyHash)
		toAdd['scriptPubKey'] = scriptPubKey
		toAdd['address'] = pubKeyHash
		toAdd['amount'] = amount
		self._unspent.append(toAdd)

	def _addTransaction(self, txid, unsignedTransactionHex):
		self._memPool.append((txid, unsignedTransactionHex))

	def getBlockHashAtIndexOrNone(self, blockIndex):
		if blockIndex >= self._nextBlock:
			return None
		return str(blockIndex)
	def getNextBlockHash(self, blockHash):
		nextBlock = int(blockHash) + 1
		if nextBlock < self._nextBlock:
			return str(nextBlock)
		assert nextBlock == self._nextBlock
		if self.holdNewTransactions or len(self._memPool) == 0:
			return None
		if not self._nextBlock in self._transactionsByBlock:
			self._transactionsByBlock[self._nextBlock] = []
		for entry in self._memPool:
			self._transactionsByBlock[self._nextBlock].append(entry)
		self._memPool = []
		pendingTransactions = self._transactionsByBlock.get(self._nextBlock, [])
		result = str(self._nextBlock)
		self._nextBlock += 1
		return result
	def getBlockTransactions(self, blockHash):
		i = int(blockHash)
		return self._transactionsByBlock.get(i, [])

	def getMemPoolTransactions(self):
		return self._memPool

	def _advance(self, numberOfBlocks):
		self._nextBlock += numberOfBlocks

	def getUnspent(self):
		result = []
		for entry in self._unspent:
			if self._isHostAddress(entry['address']):
				result.append(entry)
		return result

	def getNewNonSwapBillAddress(self):
		privateKey = self._keyGenerator.generatePrivateKey()
		pubKeyHash = self._keyGenerator.privateKeyToPubKeyHash(privateKey)
		self._keyPairs.append((privateKey, pubKeyHash))
		return pubKeyHash
	def _isHostAddress(self, pubKeyHash):
		for privateKey, storedPubKeyHash in self._keyPairs:
			if pubKeyHash == storedPubKeyHash:
				return True
		return False

	def _consumeUnspent(self, txID, vOut):
		unspentAfter = []
		found = None
		for entry in self._unspent:
			if entry['txid'] == txID and entry['vout'] == vOut:
				assert found is None
				found = entry
			else:
				unspentAfter.append(entry)
		if found is None:
			raise ExceptionReportedToUser('RPC error sending signed transaction: (from Mock Host, no unspent found for input, maybe already spent?)')
		pubKeyHash = found['address']
		if self._isHostAddress(pubKeyHash):
			pubKeyHashToBeSigned = None
		else:
			pubKeyHashToBeSigned = pubKeyHash
			assert pubKeyHashToBeSigned is not None
		self._unspent = unspentAfter
		return found['amount'], pubKeyHashToBeSigned

	def signAndSend(self, unsignedTransactionHex, privateKeys=[]):
		unsignedTransactionBytes = RawTransaction.FromHex(unsignedTransactionHex)
		decoded, scriptPubKeys = RawTransaction.Decode(unsignedTransactionBytes)
		sumOfInputs = 0
		pubKeyHashesToBeSigned = []
		for i in range(decoded.numberOfInputs()):
			amount, pubKeyHashToBeSigned = self._consumeUnspent(decoded.inputTXID(i), decoded.inputVOut(i))
			sumOfInputs += amount
			if pubKeyHashToBeSigned is not None:
				pubKeyHashesToBeSigned.append(pubKeyHashToBeSigned)
		if len(pubKeyHashesToBeSigned) != len(privateKeys):
			raise Exception('number of supplied private keys does not match number of required private keys')
		for pubKeyHash in pubKeyHashesToBeSigned:
			privateKeys = MatchPubKeyHashAndRemovePrivateKey(self._keyGenerator, pubKeyHash, privateKeys)
		self._nextTXID += 1
		txid = MakeTXID(self._nextTXID)
		outputAmounts = []
		for vout in range(decoded.numberOfOutputs()):
			toAdd = {'txid':txid, 'vout':vout}
			scriptPubKey = scriptPubKeys[vout]
			pubKeyHash = decoded.outputPubKeyHash(vout)
			assert pubKeyHash == RawTransaction.PubKeyHashForScriptPubKey(scriptPubKey)
			toAdd['scriptPubKey'] = scriptPubKey
			toAdd['address'] = pubKeyHash
			toAdd['amount'] = decoded.outputAmount(vout)
			self._unspent.append(toAdd)
			outputAmounts.append(decoded.outputAmount(vout))
		transactionFee = sumOfInputs - sum(outputAmounts)
		byteSize = len(unsignedTransactionHex) / 2
		feeRequired = TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputAmounts)
		if transactionFee < feeRequired:
			raise Host.InsufficientTransactionFees
		assert transactionFee >= feeRequired
		if transactionFee >= feeRequired + TransactionFee.dustLimit:
			print('transactionFee:', transactionFee)
			print('feeRequired:', feeRequired)
		assert transactionFee < feeRequired + TransactionFee.dustLimit # can potentially overspend, in theory, but will be nice to see the actual test case info that causes this
		self._addTransaction(txid, unsignedTransactionHex)

	def formatAddressForEndUser(self,  pubKeyHash):
		return Address.FromPubKeyHash(b'\x6f', pubKeyHash) # litecoin testnet address version
		#for i in range(len(self._keyPairs)):
			#privateKey, storedPubKeyHash = self._keyPairs[i]
			#if pubKeyHash == storedPubKeyHash:
				#return 'host_address_' + str(i)
		#startInHex = binascii.hexlify(pubKeyHash[:5]).decode('ascii')
		#return 'SwapBill address starting with ' + startInHex
	def addressFromEndUserFormat(self,  address):
		return Address.ToPubKeyHash(b'\x6f', address) # litecoin testnet address version

	def formatAccountForEndUser(self, account):
		txID, vOut = account
		assert txID[:-2] == '00' * 31
		return txID[-2:] + ':' + str(vOut)
	def _accountFromEndUserFormat(self, formatted):
		txID = '00' * 31 + formatted[:2]
		assert formatted[2:3] == ':'
		vOut = int(formatted[3:])
		return txID, vOut

	def _checkAccountHasUnspent(self, account):
		txID, vOut = account
		for entry in self._unspent:
			if entry['txid'] == txID and entry['vout'] == vOut:
				return
		raise Exception('no unspent for:', account)
