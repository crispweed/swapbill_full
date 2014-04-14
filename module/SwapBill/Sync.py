from __future__ import print_function
import sys
PY3 = sys.version_info.major > 2
if PY3:
	import pickle
else:
	import cPickle as pickle
from os import path
from collections import deque
from SwapBill import State, DecodeTransaction, TransactionTypes, LTCTrading, SourceLookup, ControlAddressEncoding

class ReindexingRequiredException(Exception):
	pass

if sys.version_info > (3, 0):
	cacheFileName = 'SwapBill.py3.cache'
else:
	cacheFileName = 'SwapBill.cache'
cacheVersion = 0.5

def _load():
	if not path.exists(cacheFileName):
		raise ReindexingRequiredException('no cache file found')
	f = open(cacheFileName, 'rb')
	savedCacheVersion = pickle.load(f)
	if savedCacheVersion != cacheVersion:
		raise ReindexingRequiredException('cached data is from old version')
	blockIndex = pickle.load(f)
	blockHash = pickle.load(f)
	state = pickle.load(f)
	f.close()
	return blockIndex, blockHash, state

def _save(blockIndex, blockHash, state):
	try:
		f = open(cacheFileName, 'wb')
		pickle.dump(cacheVersion, f, 2)
		pickle.dump(blockIndex, f, 2)
		pickle.dump(blockHash, f, 2)
		pickle.dump(state, f, 2)
		f.close()
	except:
		print("Error, failed to write cache:", sys.exc_info()[0])

def _processBlock(config, rpcHost, state, blockHash):
	block = rpcHost.call('getblock', blockHash)
	sourceLookup = SourceLookup.Lookup(config.addressVersion, rpcHost)
	transactions = block['tx']
	assert len(transactions) >= 1
	for txHash in transactions[1:]:
		litecoinTXHex = rpcHost.call('getrawtransaction', txHash)
		hostTX = DecodeTransaction.Transaction(litecoinTXHex, rpcHost)
		try:
			decodedTX = TransactionTypes.Decode(sourceLookup, hostTX)
		except ControlAddressEncoding.NotSwapBillControlAddress:
			continue
		except TransactionTypes.NotValidSwapBillTransaction:
			continue
		except TransactionTypes.UnsupportedTransaction:
			continue
		decodedTX.apply(state)
		print('applied transaction:', decodedTX)
		LTCTrading.Match(state)

def SyncAndReturnState(config, rpcHost):
	try:
		blockIndex, blockHash, state = _load()
	except ReindexingRequiredException as e:
		print('Failed to load from cache, full index generation required (' + str(e) + ')')
		loaded = False
	else:
		loaded = True
	if loaded and rpcHost.call('getblockhash', blockIndex) != blockHash:
		print('The block corresponding with cached state has been orphaned, full index generation required.')
		loaded = False
	if loaded and not state.startBlockMatches(config.startBlockHash):
		print('Start config does not match config from loaded state, , full index generation required.')
		loaded = False
	if loaded:
		print('Loaded cached state data successfully')
	else:
		blockIndex = config.startBlockIndex
		blockHash = config.startBlockHash
		assert rpcHost.call('getblockhash', blockIndex) == blockHash
		state = State.State(blockIndex, blockHash)

	print('Starting from block', blockIndex)

	toProcess = deque()
	mostRecentHash = blockHash
	while True:
		block = rpcHost.call('getblock', mostRecentHash)
		if not 'nextblockhash' in block:
			break
		if len(toProcess) == config.blocksBehindForCachedState:
			## advance cached state
			_processBlock(config, rpcHost, state, blockHash)
			popped = toProcess.popleft()
			blockIndex += 1
			blockHash = popped
		mostRecentHash = block['nextblockhash']
		toProcess.append(mostRecentHash)

	_save(blockIndex, blockHash, state)

	while len(toProcess) > 0:
		## advance in memory state
		_processBlock(config, rpcHost, state, blockHash)
		state.advanceToNextBlock()
		popped = toProcess.popleft()
		blockIndex += 1
		blockHash = popped

	_processBlock(config, rpcHost, state, blockHash)

	return state

def LoadAndReturnStateWithoutUpdate(config):
	try:
		blockIndex, blockHash, state = _load()
	except ReindexingRequiredException as e:
		print('Could not load cached state, so returning empty initial state! (' + str(e) + ')')
	return state
