import binascii
from SwapBill import RawTransaction, TransactionFee
from SwapBill import Host ## just for insufficient fee exception

def TextAsPubKeyHash(s):
	assert len(s) <= 20
	assert not '-' in s
	padded = s + '-' * (20 - len(s))
	result = padded.encode('ascii')
	assert len(result) == 20
	return result
def PubKeyHashAsText(data):
	assert type(data) is type(b'')
	assert len(data) == 20
	padded = data.decode('ascii')
	return padded.strip('-')
def MakeTXID(i):
	txid = '00' * 31 + '{:02X}'.format(i)
	# make case consistent with hexlify!
	txid = binascii.hexlify(binascii.unhexlify(txid.encode('ascii'))).decode('ascii')
	return txid


class MockHost(object):
	def __init__(self, id=''):
		self._id = id
		self._nextChange = 0
		self._nextSwapBill = 0
		# start block is zero, already confirmed, contains no transactions
		# block 1 will be confirmed when it has transactions and next block is queried
		self._nextBlock = 1
		self._transactionsByBlock = {0:[]}
		self._nextTXID = 0
		self._nextSuppliedOutput = 0
		self._sourceLookup = {}
		self._unspent = []

	def _setOwner(self, id):
		assert not '_' in id
		self._id = id

	def _addUnspent(self, amount):
		self._nextTXID += 1
		txid = MakeTXID(self._nextTXID)
		vout = 7
		toAdd = {'txid':txid, 'vout':vout}
		self._nextSuppliedOutput += 1
		pubKeyHash = TextAsPubKeyHash(self._id + '_supplied' + str(self._nextSuppliedOutput))
		scriptPubKey = RawTransaction.ScriptPubKeyForPubKeyHash(pubKeyHash)
		toAdd['scriptPubKey'] = scriptPubKey
		toAdd['address'] = pubKeyHash
		toAdd['amount'] = amount
		self._sourceLookup[(txid, vout)] = pubKeyHash
		self._unspent.append(toAdd)

	def addTransaction(self, txid, unsignedTransactionHex):
		if not self._nextBlock in self._transactionsByBlock:
			self._transactionsByBlock[self._nextBlock] = []
		self._transactionsByBlock[self._nextBlock].append((txid, unsignedTransactionHex))

	def getBlockHash(self, blockIndex):
		assert blockIndex < self._nextBlock
		return str(blockIndex)
	def getNextBlockHash(self, blockHash):
		nextBlock = int(blockHash) + 1
		if nextBlock < self._nextBlock:
			return str(nextBlock)
		assert nextBlock == self._nextBlock
		pendingTransactions = self._transactionsByBlock.get(self._nextBlock, [])
		if len(pendingTransactions) == 0:
			return None
		result = str(self._nextBlock)
		self._nextBlock += 1
		return result
	def getBlockTransactions(self, blockHash):
		i = int(blockHash)
		return self._transactionsByBlock.get(i, [])

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
		return TextAsPubKeyHash(self._id + '_nonsb' + str(self._nextChange))
	def getNewSwapBillAddress(self):
		self._nextSwapBill += 1
		return TextAsPubKeyHash(self._id + '_swapbill' + str(self._nextSwapBill))
	def addressIsMine(self, pubKeyHash):
		try:
			asText = PubKeyHashAsText(pubKeyHash)
		except UnicodeDecodeError:
			# control address
			return False
		return asText.startswith(self._id + '_')

	def _consumeUnspent(self, txID, vOut, scriptPubKey):
		unspentAfter = []
		found = None
		for entry in self._unspent:
			if entry['txid'] == txID and entry['vout'] == vOut:
				assert entry['scriptPubKey'] == scriptPubKey
				assert found is None
				found = entry
			else:
				unspentAfter.append(entry)
		assert found is not None
		if not self.addressIsMine(found['address']):
			raise Exception('At least one unspent output used in the transaction cannot be signed.', self.formatAddressForEndUser(found['address']))
		self.unspent = unspentAfter
		return found['amount']

	def signAndSend(self, unsignedTransactionHex):
		unsignedTransactionBytes = RawTransaction.FromHex(unsignedTransactionHex)
		decoded = RawTransaction.Decode(unsignedTransactionBytes)
		sumOfInputs = 0
		for entry in decoded['vin']:
			sumOfInputs += self._consumeUnspent(entry['txid'], entry['vout'], entry['scriptPubKey'])
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
			self._sourceLookup[(txid, vout)] = pubKeyHash
			#print(toAdd)
			self._unspent.append(toAdd)
			outputAmounts.append(entry['value'])
		transactionFee = sumOfInputs - sum(outputAmounts)
		byteSize = len(unsignedTransactionHex) / 2
		feeRequired = TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputAmounts)
		if transactionFee < feeRequired:
			raise Host.InsufficientTransactionFees
			#print('byteSize:', byteSize)
			#print('outputAmounts:')
			#print(outputAmounts)
			#print('transactionFee:', transactionFee)
			#print('feeRequired:', feeRequired)
		assert transactionFee >= feeRequired
		if transactionFee >= feeRequired + TransactionFee.dustLimit:
			print('transactionFee:', transactionFee)
			print('feeRequired:', feeRequired)
		assert transactionFee < feeRequired + TransactionFee.dustLimit ## can potentially overspend, in theory, but will be nice to see the actual test case info that causes this
		self.addTransaction(txid, unsignedTransactionHex)

	def getSourceFor(self, txID, vOut):
		return self._sourceLookup[(txID, vOut)]

	def formatAddressForEndUser(self,  pubKeyHash):
		return PubKeyHashAsText(pubKeyHash)
	def addressFromEndUserFormat(self,  address):
		return TextAsPubKeyHash(address)

	def formatAccountForEndUser(self, account):
		txID, vOut = account
		return txID[-2:] + ':' + str(vOut)
