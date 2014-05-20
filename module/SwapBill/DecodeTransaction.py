from __future__ import print_function
import binascii
#from SwapBill import HostTransaction
from SwapBill import RawTransaction, HostTransaction, ControlAddressPrefix
#from SwapBill.Amounts import ToSatoshis

#class NotValidSwapBillTransaction(Exception):
	#pass

### TODO lose the need for RPC here, and just extract everything from the raw transaction
### (but can be useful keep an rpc based transaction around for testing)

#class Transaction(object):
	#def __init__(self, txHex, rpcHost):
		#self._hex = txHex
		#self._rpcHost = rpcHost
	#def _decodeIfNotDecoded(self):
		#if not hasattr(self, '_decoded'):
			#self._decoded = self._rpcHost.call('decoderawtransaction', self._hex)
	#def numberOfInputs(self):
		#self._decodeIfNotDecoded()
		#return len(self._decoded['vin'])
	#def inputTXID(self, i):
		#self._decodeIfNotDecoded()
		#return self._decoded['vin'][i]['txid']
	#def inputVOut(self, i):
		#self._decodeIfNotDecoded()
		#return self._decoded['vin'][i]['vout']
	#def numberOfOutputs(self):
		#self._decodeIfNotDecoded()
		#return len(self._decoded['vout'])
	#def outputPubKeyHash(self, i):
		### ** important optimisation - this is the first thing checked when filtering transactions
		#data = RawTransaction.FromHex(self._hex)
		### TODO raise NotValidSwapBillTransaction if output script does not match expected format!
		#firstOutputPubKeyHash = RawTransaction.ExtractOutputPubKeyHash(data, i)
		#return firstOutputPubKeyHash
	#def outputAmount(self, i):
		#self._decodeIfNotDecoded()
		#return ToSatoshis(float(self._decoded['vout'][i]['value']))

def Decode(txHex):
	txBytes = RawTransaction.FromHex(txHex)
	if RawTransaction.UnexpectedFormat_Fast(txBytes, ControlAddressPrefix.prefix):
		return None, None
	decoded = RawTransaction.Decode(txBytes)
	result = HostTransaction.InMemoryTransaction()
	for i in decoded['vin']:
		result.addInput(i['txid'], i['vout'])
	for o in decoded['vout']:
		pubKeyHashHex = o['pubKeyHash']
		pubKeyHash = binascii.unhexlify(pubKeyHashHex.encode('ascii'))
		result.addOutput(pubKeyHash, o['value'])
	scriptPubKeys = []
	for o in decoded['vout']:
		scriptPubKeys.append(o['scriptPubKey'])
	return result, scriptPubKeys
