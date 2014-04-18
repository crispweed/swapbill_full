from __future__ import print_function
import sys
PY3 = sys.version_info.major > 2
if PY3:
	import pickle
else:
	import cPickle as pickle
from os import path
from collections import deque
from SwapBill import State, DecodeTransaction, TransactionTypes, SourceLookup, ControlAddressEncoding

class ReindexingRequiredException(Exception):
	pass

if sys.version_info > (3, 0):
	defaultCacheFile = 'SwapBill.py3.cache'
else:
	defaultCacheFile = 'SwapBill.cache'
cacheVersion = 0.6

def _load(cacheFile):
	if cacheFile is None:
		cacheFile = defaultCacheFile
	if not path.exists(cacheFile):
		raise ReindexingRequiredException('no cache file found')
	f = open(cacheFile, 'rb')
	savedCacheVersion = pickle.load(f)
	if savedCacheVersion != cacheVersion:
		raise ReindexingRequiredException('cached data is from old version')
	blockIndex = pickle.load(f)
	blockHash = pickle.load(f)
	state = pickle.load(f)
	f.close()
	return blockIndex, blockHash, state

def _save(blockIndex, blockHash, state, cacheFile):
	if cacheFile is None:
		cacheFile = defaultCacheFile
	try:
		f = open(cacheFile, 'wb')
		pickle.dump(cacheVersion, f, 2)
		pickle.dump(blockIndex, f, 2)
		pickle.dump(blockHash, f, 2)
		pickle.dump(state, f, 2)
		f.close()
	except:
		print("Error, failed to write cache:", sys.exc_info()[0])

def _processBlock(host, state, blockHash, out):
	transactions = host.getBlockTransactions(blockHash)
	for litecoinTXHex in transactions:
		#hostTX = DecodeTransaction.Transaction(litecoinTXHex, host._rpcHost)
		hostTX = DecodeTransaction.Decode(litecoinTXHex)
		if hostTX == None:
			continue
		try:
			decodedTX = TransactionTypes.Decode(host, hostTX)
		except ControlAddressEncoding.NotSwapBillControlAddress:
			continue
		except TransactionTypes.NotValidSwapBillTransaction:
			continue
		except TransactionTypes.UnsupportedTransaction:
			continue
		#decodedTX.apply(state)
		state.applyTransaction(decodedTX.__class__.__name__, decodedTX.details())
		print('applied transaction:', decodedTX, file=out)
	state.advanceToNextBlock()

def SyncAndReturnState(cacheFile, startBlockIndex, startBlockHash, host, out):
	try:
		blockIndex, blockHash, state = _load(cacheFile)
	except ReindexingRequiredException as e:
		print('Failed to load from cache, full index generation required (' + str(e) + ')', file=out)
		loaded = False
	else:
		loaded = True
	if loaded and host.getBlockHash(blockIndex) != blockHash:
		print('The block corresponding with cached state has been orphaned, full index generation required.', file=out)
		loaded = False
	if loaded and not state.startBlockMatches(startBlockHash):
		print('Start config does not match config from loaded state, , full index generation required.', file=out)
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

	_save(blockIndex, blockHash, state, cacheFile)

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
