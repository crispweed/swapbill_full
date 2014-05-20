from __future__ import print_function
import sys
from os import path
from collections import deque
from SwapBill import State, DecodeTransaction, TransactionEncoding, PickledCache
from SwapBill import FormatTransactionForUserDisplay

stateVersion = 0.7
#ownedOutputsVersion = 0.1

def _processBlock(host, state, blockHash, out):
	transactions = host.getBlockTransactions(blockHash)
	for txID, litecoinTXHex in transactions:
		hostTX = DecodeTransaction.Decode(litecoinTXHex)
		if hostTX == None:
			continue
		try:
			transactionType, outputs, outputPubKeyHashes, transactionDetails = TransactionEncoding.ToStateTransaction(hostTX)
		except TransactionEncoding.NotValidSwapBillTransaction:
			continue
		except TransactionEncoding.UnsupportedTransaction:
			continue
		state.applyTransaction(transactionType, txID, outputs, transactionDetails)
		print('applied ' + FormatTransactionForUserDisplay.Format(host, transactionType, outputs, outputPubKeyHashes, transactionDetails), file=out)
	state.advanceToNextBlock()

def SyncAndReturnState(cacheDirectory, startBlockIndex, startBlockHash, host, out):
	try:
		(blockIndex, blockHash, state) = PickledCache.Load(cacheDirectory, 'State', stateVersion)
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
			_processBlock(host, state, blockHash, out=out)
			popped = toProcess.popleft()
			blockIndex += 1
			blockHash = popped
		mostRecentHash = nextBlockHash
		toProcess.append(mostRecentHash)

	PickledCache.Save((blockIndex, blockHash, state), stateVersion, cacheDirectory, 'State')

	while len(toProcess) > 0:
		## advance in memory state
		_processBlock(host, state, blockHash, out=out)
		popped = toProcess.popleft()
		blockIndex += 1
		blockHash = popped

	_processBlock(host, state, blockHash, out=out)

	return state

#def LoadAndReturnStateWithoutUpdate(config):
	#try:
		#blockIndex, blockHash, state = _load()
	#except ReindexingRequiredException as e:
		#print('Could not load cached state, so returning empty initial state! (' + str(e) + ')')
	#return state
