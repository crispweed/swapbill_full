from __future__ import print_function
import struct, collections
from SwapBill import State, DecodeTransaction, TransactionTypes

class Follower(object):
	def __init__(self, startBlockCount):
		self._state = State.State(startBlockCount)
		self._log = collections.deque('', 500)

	def addBlock(self, config, rpcHost, blockHash):
		block = rpcHost.call('getblock', blockHash)
		for txHash in block['tx']:
			litecoinTX = rpcHost.call('getrawtransaction', txHash, 1)
			try:
				decodedTX = DecodeTransaction.Decode(config, rpcHost, litecoinTX)
			except TransactionTypes.InvalidTransaction:
				pass
			else:
				decodedTX.apply(self._state)
				print('applied transaction:', decodedTX)
				self._log.append(decodedTX)

	def removeBlock(self, config, rpcHost, blockHash):
		block = rpcHost.call('getblock', blockHash)
		for txHash in block['tx'][::-1]:
			litecoinTX = rpcHost.call('getrawtransaction', txHash, 1)
			try:
				decodedTX = DecodeTransaction.Decode(config, rpcHost, litecoinTX)
			except TransactionTypes.InvalidTransaction:
				pass
			else:
				if len(self._log) == 0:
					print('rewinding transaction:', decodedTX)
					decodedTX.rewind(self._state)
				else:
					loggedTX = self._log.pop()
					print('rewinding transaction:', loggedTX)
					loggedTX.rewind(self._state)
					if not loggedTX.__dict__ == decodedTX.__dict__:
						if config.allowRewindMismatch:
							print('**** mismatch on rewind! (permitted by config) ****')
							print('loggedTX:', str(loggedTX))
							print('decodedTX:', str(decodedTX))
							print('loggedTX.__dict__', loggedTX.__dict__)
							print('decodedTX.__dict__', decodedTX.__dict__)
						else:
							raise Exception('Mismatch on rewind transaction, loggedTX:', str(loggedTX), 'decodedTX:', str(decodedTX))

