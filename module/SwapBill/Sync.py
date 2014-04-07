from __future__ import print_function
import sys
try:
	import cPickle as pickle
except ImportError:
	import pickle
from os import path
from SwapBill import BlockChain, BlockChainFollower

class ReindexingRequiredException(Exception):
	pass

if sys.version_info > (3, 0):
	cacheFileName = 'SwapBill.cache.python3'
else:
	cacheFileName = 'SwapBill.cache'

def _load(config):
	if not path.exists(cacheFileName):
		raise ReindexingRequiredException('no cache file found')
	f = open(cacheFileName, 'rb')
	cacheVersion = pickle.load(f)
	if cacheVersion != config.clientVersion:
		raise ReindexingRequiredException('cached data is from old version')
	follower = pickle.load(f)
	tracker = pickle.load(f)
	f.close()
	if cacheVersion != config.clientVersion:
		raise ReindexingRequiredException('cached data is from old version')
	print('cache version matches')
	if not tracker.setupMatches(config.startBlockIndex, config.startBlockHash):
		raise ReindexingRequiredException('cached data config is not compatible with current config')
	return follower, tracker

def _save(config, follower, tracker):
	try:
		f = open(cacheFileName, 'wb')
		pickle.dump(config.clientVersion, f, 2)
		pickle.dump(follower, f, 2)
		pickle.dump(tracker, f, 2)
		f.close()
	except:
		print("Error, failed to write cache:", sys.exc_info()[0])

def SyncAndReturnState(config, rpcHost):
	try:
		follower, tracker = _load(config)
	except ReindexingRequiredException as e:
		print('Full index generation required (' + str(e) + ')')
		loaded = False
	else:
		loaded = True
	if not loaded:
		follower = BlockChainFollower.Follower(config)
		tracker = BlockChain.Tracker(config, rpcHost)

	currentHash = tracker.currentHash()
	while True:
		increment = tracker.update(config, rpcHost)
		if increment == 0:
			break
		if increment == -1:
			follower.removeBlock(config, rpcHost, currentHash)
			currentHash = tracker.currentHash()
		else:
			assert increment == 1
			currentHash = tracker.currentHash()
			follower.addBlock(config, rpcHost, currentHash)

	_save(config, follower, tracker)
	return follower._state

def RewindLastBlockWithTransactions(config, rpcHost):
	try:
		follower, tracker = _load(config)
	except ReindexingRequiredException as e:
		print('Failed to load cache to rewind (' + str(e) + ')')
		return
	startingLogSize = len(follower._log)
	while len(follower._log) == startingLogSize:
		currentHash = tracker.currentHash()
		follower.removeBlock(config, rpcHost, currentHash)
		tracker.rewindOneBlock(config, rpcHost)
	_save(config, follower, tracker)

def LoadAndReturnStateWithoutUpdate(config):
	try:
		follower, tracker = _load(config)
	except ReindexingRequiredException as e:
		print('Could not load cache, so returning empty initial state! (' + str(e) + ')')
		follower = BlockChainFollower.Follower(config)
		tracker = BlockChain.Tracker(config, rpcHost, follower)
	return follower._state
