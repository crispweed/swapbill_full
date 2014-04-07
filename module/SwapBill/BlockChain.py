def _getCurrentBlockHashAt(rpcHost, blockIndex):
	(success, resultOrError) = rpcHost.call_ReturnResultOrError('getblockhash', blockIndex)
	if success:
		return resultOrError
	if resultOrError['message'] == "Block number out of range.":
		return None
	raise Exception('Unexpected error returned from getblockhash remote procedure call: {}'.format(resultOrError))

class Tracker(object):
	def __init__(self, config, rpcHost):
		assert rpcHost.call('getblockhash', config.startBlockIndex) == config.startBlockHash
		self._startIndex = config.startBlockIndex
		self._startHash = config.startBlockHash
		self._currentIndex = config.startBlockIndex
		self._currentHash = config.startBlockHash

	def setupMatches(self, startIndex, startHash):
		return self._startIndex == startIndex and self._startHash == startHash

	def rewindOneBlock(self, config, rpcHost):
		assert self._currentIndex != self._startIndex
		self._currentIndex -= 1
		block = rpcHost.call('getblock', self._currentHash)
		self._currentHash = block['previousblockhash']

	def currentHash(self):
		return self._currentHash

	def update(self, config, rpcHost):
		if rpcHost.call('getblockhash', self._currentIndex) != self._currentHash:
			self.rewindOneBlock(config, rpcHost)
			return -1
		nextHash = _getCurrentBlockHashAt(rpcHost, self._currentIndex + 1)
		if nextHash == None:
			return 0
		block = rpcHost.call('getblock', nextHash)
		if block['previousblockhash'] != self._currentHash:
			self.rewindOneBlock(config, rpcHost)
			return -1
		self._currentIndex += 1
		self._currentHash = nextHash
		return 1
