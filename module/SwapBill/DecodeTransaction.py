from __future__ import print_function
from SwapBill import RawTransaction
from SwapBill.Amounts import ToSatoshis

class NotValidSwapBillTransaction(Exception):
	pass

## TODO lose the need for RPC here, and just extract everything from the raw transaction
## (but can be useful keep an rpc based transaction around for testing)

class Transaction(object):
	def __init__(self, txHex, rpcHost):
		self._hex = txHex
		self._rpcHost = rpcHost
	def _decodeIfNotDecoded(self):
		if not hasattr(self, '_decoded'):
			self._decoded = self._rpcHost.call('decoderawtransaction', self._hex)
	def numberOfInputs(self):
		self._decodeIfNotDecoded()
		return len(self._decoded['vin'])
	def inputTXID(self, i):
		self._decodeIfNotDecoded()
		return self._decoded['vin'][i]['txid']
	def inputVOut(self, i):
		self._decodeIfNotDecoded()
		return self._decoded['vin'][i]['vout']
	def numberOfOutputs(self):
		self._decodeIfNotDecoded()
		return len(self._decoded['vout'])
	def outputPubKeyHash(self, i):
		## ** important optimisation - this is the first thing checked when filtering transactions
		data = RawTransaction.FromHex(self._hex)
		## TODO raise NotValidSwapBillTransaction if output script does not match expected format!
		firstOutputPubKeyHash = RawTransaction.ExtractOutputPubKeyHash(data, i)
		return firstOutputPubKeyHash
	def outputAmount(self, i):
		self._decodeIfNotDecoded()
		return ToSatoshis(float(self._decoded['vout'][i]['value']))

