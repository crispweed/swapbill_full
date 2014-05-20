from __future__ import print_function
import binascii
from SwapBill import RawTransaction, HostTransaction, ControlAddressPrefix

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
