from __future__ import print_function
import sys
from os import path
from collections import deque
from SwapBill import State, DecodeTransaction, TransactionEncoding, PickledCache
from SwapBill import FormatTransactionForUserDisplay

stateVersion = 0.7
ownedAccountsVersion = 0.1

def _processTransactions(host, state, ownedAccounts, transactions, applyToState, out):
	for txID, hostTXHex in transactions:
		hostTX, scriptPubKeys = DecodeTransaction.Decode(hostTXHex)
		if hostTX == None:
			continue
		for i in range(hostTX.numberOfInputs()):
			spentAccount = (hostTX.inputTXID(i), hostTX.inputVOut(i))
			if spentAccount in ownedAccounts:
				ownedAccounts.pop(spentAccount)
		try:
			transactionType, outputs, transactionDetails = TransactionEncoding.ToStateTransaction(hostTX)
		except TransactionEncoding.NotValidSwapBillTransaction:
			continue
		except TransactionEncoding.UnsupportedTransaction:
			continue
		if not state.checkTransaction(transactionType, outputs, transactionDetails)[0]:
			outputPubKeyHashes = []
			for i in range(len(outputs)):
				outputPubKeyHashes.append(hostTX.outputPubKeyHash(i + 1))
			print('Transaction fails:'+ FormatTransactionForUserDisplay.Format(host, transactionType, outputs, outputPubKeyHashes, transactionDetails), file=out)
			continue
		if applyToState:
			outputPubKeyHashes = []
			for i in range(len(outputs)):
				outputPubKeyHashes.append(hostTX.outputPubKeyHash(i + 1))
			state.applyTransaction(transactionType, txID, outputs, transactionDetails)
			print('applied ' + FormatTransactionForUserDisplay.Format(host, transactionType, outputs, outputPubKeyHashes, transactionDetails), file=out)
		if applyToState:
			for i in range(len(outputs)):
				newOwnedAccount = (txID, i + 1)
				if newOwnedAccount in state._balances:
					privateKey = host.privateKeyForPubKeyHash(outputPubKeyHashes[i])
					if privateKey is not None:
						#print("added owned account for:", transactionType, outputs[i], txID[-3:], i + 1)
						assert not newOwnedAccount in ownedAccounts
						ownedAccounts[newOwnedAccount] = (hostTX.outputAmount(i + 1), privateKey, scriptPubKeys[i + 1])


def _processBlock(host, state, ownedAccounts, blockHash, out):
	transactions = host.getBlockTransactions(blockHash)
	_processTransactions(host, state, ownedAccounts, transactions, True, out)
	state.advanceToNextBlock()

def SyncAndReturnStateAndOwnedAccounts(cacheDirectory, startBlockIndex, startBlockHash, host, includePending, out):
	try:
		(blockIndex, blockHash, state) = PickledCache.Load(cacheDirectory, 'State', stateVersion)
		ownedAccounts = PickledCache.Load(cacheDirectory, 'OwnedAccounts', ownedAccountsVersion)
	except PickledCache.LoadFailedException as e:
		print('Failed to load from cache, full index generation required (' + str(e) + ')', file=out)
		loaded = False
	else:
		loaded = True
	if loaded and host.getBlockHash(blockIndex) != blockHash:
		print('The block corresponding with cached state has been orphaned, full index generation required.', file=out)
		loaded = False
	if loaded and not state.startBlockMatches(startBlockHash):
		print('Start config does not match config from loaded state, full index generation required.', file=out)
		loaded = False
	if loaded:
		print('Loaded cached state data successfully', file=out)
	else:
		blockIndex = startBlockIndex
		blockHash = startBlockHash
		assert host.getBlockHash(blockIndex) == blockHash
		state = State.State(blockIndex, blockHash)
		ownedAccounts = {}

	print('Starting from block', blockIndex, file=out)

	toProcess = deque()
	mostRecentHash = blockHash
	while True:
		nextBlockHash = host.getNextBlockHash(mostRecentHash)
		if nextBlockHash is None:
			break
		## hard coded value used here for number of blocks to lag behind with persistent state
		if len(toProcess) == 20:
			## advance cached state
			_processBlock(host, state, ownedAccounts, blockHash, out=out)
			popped = toProcess.popleft()
			blockIndex += 1
			blockHash = popped
		mostRecentHash = nextBlockHash
		toProcess.append(mostRecentHash)

	PickledCache.Save((blockIndex, blockHash, state), stateVersion, cacheDirectory, 'State')
	PickledCache.Save(ownedAccounts, ownedAccountsVersion, cacheDirectory, 'OwnedAccounts')

	while len(toProcess) > 0:
		## advance in memory state
		_processBlock(host, state, ownedAccounts, blockHash, out=out)
		popped = toProcess.popleft()
		blockIndex += 1
		blockHash = popped

	_processBlock(host, state, ownedAccounts, blockHash, out=out)
	blockIndex += 1

	assert state._currentBlockIndex == blockIndex

	# note that the best block chain may have changed during the above
	# and so the following set of memory pool transactions may not correspond to the actual block chain endpoint we synchronised to
	# and this may then result in us trying to make double spends, in certain situations
	# the host should then refuse these transactions, and so this is not a disaster
	# (and double spend situations can probably also arise more generally in the case of block chain forks, with it not possible for us to always prevent this)
	# but we can potentially be more careful about this by checking best block chain after getting memory pool transactions
	# and restarting the block chain traversal if this does not match up
	memPoolTransactions = host.getMemPoolTransactions()
	_processTransactions(host, state, ownedAccounts, memPoolTransactions, includePending, out)

	return state, ownedAccounts

#def LoadAndReturnStateWithoutUpdate(config):
	#try:
		#blockIndex, blockHash, state = _load()
	#except ReindexingRequiredException as e:
		#print('Could not load cached state, so returning empty initial state! (' + str(e) + ')')
	#return state
