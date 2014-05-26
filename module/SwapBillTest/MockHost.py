import binascii
from SwapBill import RawTransaction, TransactionFee
from SwapBill import Host ## just for insufficient fee exception
from SwapBill import Address ## just for bad address exception
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

addressPrefix = 'adr_'
privateKeyPrefix = 'privateKey_'

def TextAsPaddedData(s, size):
	assert len(s) <= size
	assert not '-' in s
	padded = s + '-' * (size - len(s))
	result = padded.encode('ascii')
	assert len(result) == size
	return result
def PaddedDataAsText(data, size):
	assert type(data) is type(b'')
	assert len(data) == size
	padded = data.decode('ascii')
	return padded.strip('-')

def TextAsPubKeyHash(s):
	if not s.startswith(addressPrefix):
		raise Address.BadAddress()
	return TextAsPaddedData(s[len(addressPrefix):], 20)
def PubKeyHashAsText(data):
	return addressPrefix + PaddedDataAsText(data, 20)

def TextAsPrivateKey(s):
	if not s.startswith(privateKeyPrefix):
		raise Exception('bad private key')
	return TextAsPaddedData(s[len(privateKeyPrefix):], 32)
def PrivateKeyAsText(data):
	return privateKeyPrefix + PaddedDataAsText(data, 32)

def MakeTXID(i):
	txid = '00' * 31 + '{:02X}'.format(i)
	# make case consistent with hexlify!
	txid = binascii.hexlify(binascii.unhexlify(txid.encode('ascii'))).decode('ascii')
	return txid


class MockHost(object):
	defaultOwner = '0'

	def __init__(self, ownerID=None):
		if ownerID is None:
			ownerID = self.defaultOwner
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
		self.holdNewTransactions = False
		self.hideMemPool = False

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
		self._nextSuppliedOutput += 1
		pubKeyHash = TextAsPubKeyHash(addressPrefix + self._id + '_host_supplied' + str(self._nextSuppliedOutput))
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
		if self.hideMemPool:
			return []
		return self._memPool

	def _advance(self, numberOfBlocks):
		self._nextBlock += numberOfBlocks

	def getUnspent(self):
		result = []
		for entry in self._unspent:
			if self.addressIsMine(entry['address']):
				result.append(entry)
		return result

	def getNewNonSwapBillAddress(self):
		self._nextChange += 1
		#print('new non swap bill address', self._id, self._nextSwapBill)
		return TextAsPubKeyHash(addressPrefix + self._id + '_host_getnew' + str(self._nextChange))
	def getNewSwapBillAddress(self):
		self._nextSwapBill += 1
		#print('new swap bill address', self._id, self._nextSwapBill)
		return TextAsPubKeyHash(addressPrefix + self._id + '_swapbill' + str(self._nextSwapBill))
	def addressIsMine(self, pubKeyHash):
		try:
			asText = PubKeyHashAsText(pubKeyHash)
		except UnicodeDecodeError:
			# control address
			return False
		return asText.startswith(addressPrefix + self._id + '_host_')

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
		if self.addressIsMine(pubKeyHash):
			requiredPrivateKey = None
		else:
			requiredPrivateKey = self.privateKeyForPubKeyHash(pubKeyHash)
			assert requiredPrivateKey is not None
		if hasattr(self, '_logConsumeUnspent') and self._logConsumeUnspent:
			print('consuming unspent:')
			print(found)
		self._unspent = unspentAfter
		return found['amount'], requiredPrivateKey

	def privateKeyForPubKeyHash(self, pubKeyHash):
		#print('self._id in privateKeyForPubKeyHash is:', self._id)
		asText = PubKeyHashAsText(pubKeyHash)
		beforeCount = addressPrefix + self._id + '_swapbill'
		if asText.startswith(beforeCount):
			count = str(asText[len(beforeCount):])
			return TextAsPrivateKey(privateKeyPrefix + self._id + '_' + count)
		return None

	def signAndSend(self, unsignedTransactionHex, privateKeys=[]):
		unsignedTransactionBytes = RawTransaction.FromHex(unsignedTransactionHex)
		decoded = RawTransaction.Decode(unsignedTransactionBytes)
		sumOfInputs = 0
		requiredPrivateKeys = []
		for entry in decoded['vin']:
			amount, privateKeyRequired = self._consumeUnspent(entry['txid'], entry['vout'])
			sumOfInputs += amount
			if privateKeyRequired is not None:
				requiredPrivateKeys.append(privateKeyRequired)
		if sorted(privateKeys) != sorted(requiredPrivateKeys):
			raise Exception('supplied private keys do not match required private keys')
		self._nextTXID += 1
		txid = MakeTXID(self._nextTXID)
		outputAmounts = []
		for vout in range(len(decoded['vout'])):
			entry = decoded['vout'][vout]
			toAdd = {'txid':txid, 'vout':vout}
			scriptPubKey = entry['scriptPubKey']
			pubKeyHash = binascii.unhexlify(entry['pubKeyHash'].encode('ascii'))
			assert pubKeyHash == RawTransaction.PubKeyHashForScriptPubKey(scriptPubKey)
			toAdd['scriptPubKey'] = scriptPubKey
			toAdd['address'] = pubKeyHash
			toAdd['amount'] = entry['value']
			self._unspent.append(toAdd)
			outputAmounts.append(entry['value'])
		transactionFee = sumOfInputs - sum(outputAmounts)
		byteSize = len(unsignedTransactionHex) / 2
		feeRequired = TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputAmounts)
		if transactionFee < feeRequired:
			raise Host.InsufficientTransactionFees
		assert transactionFee >= feeRequired
		if transactionFee >= feeRequired + TransactionFee.dustLimit:
			print('transactionFee:', transactionFee)
			print('feeRequired:', feeRequired)
		assert transactionFee < feeRequired + TransactionFee.dustLimit ## can potentially overspend, in theory, but will be nice to see the actual test case info that causes this
		self._addTransaction(txid, unsignedTransactionHex)

	def formatAddressForEndUser(self,  pubKeyHash):
		return PubKeyHashAsText(pubKeyHash)
	def addressFromEndUserFormat(self,  address):
		return TextAsPubKeyHash(address)

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
