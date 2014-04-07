from __future__ import print_function
import struct, binascii
from SwapBill import ControlAddressEncoding, TransactionTypes, Address
from SwapBill.Amounts import FromSatoshis, ToSatoshis

def _singleAddressFromOutput(output):
	if not 'scriptPubKey' in output:
		return None
	scriptPubKey = output['scriptPubKey']
	if not 'addresses' in scriptPubKey:
		return None
	addresses = scriptPubKey['addresses']
	if len(addresses) != 1:
		return None
	return addresses[0]

scriptStart = '76a914' ## (OP_DUP OP_HASH160)
scriptEnd = '88ac' ## (OP_EQUALVERIFY OP_CHECKSIG)

## *** optimisation - include SWB prefix in the initial check
## TODO reorganise stuff around this!
scriptStartWithCheck = '76a914535742' ## (OP_DUP OP_HASH160)

def _singlePubKeyHashFromOutput(output):
	if not 'scriptPubKey' in output:
		return None
	scriptHex = output['scriptPubKey']['hex']
	#if not scriptHex.startswith(scriptStart):
	if not scriptHex.startswith(scriptStartWithCheck):
		return None
	if not scriptHex.endswith(scriptEnd):
		return None
	hexPubKeyHash = scriptHex[len(scriptStart):-len(scriptEnd)]
	if len(hexPubKeyHash) != 40:
		return None
	return binascii.unhexlify(hexPubKeyHash)

def _singleSourceAddress(decodedTX, rpcHost):
	lastInput = decodedTX['vin'][-1]
	sourceTXID = lastInput['txid']
	sourceVOut = lastInput['vout']
	redeemedTX = rpcHost.call('getrawtransaction', sourceTXID, 1)
	return _singleAddressFromOutput(redeemedTX['vout'][sourceVOut])

def Decode(config, rpcHost, decodedTX):
	#controlAddress = _singleAddressFromOutput(decodedTX['vout'][0])
	#if controlAddress == None:
		#return None
	#try:
	#	data = Address.ToData(config.addressVersion, controlAddress)
	#except Address.BadAddress:
	#	return None
	data = _singlePubKeyHashFromOutput(decodedTX['vout'][0])

	if data == None:
		raise TransactionTypes.InvalidTransaction()

	try:
		typeCode, amount, maxBlock, extraData = ControlAddressEncoding.Decode(data)
	except ControlAddressEncoding.InvalidControlAddress as e:
		raise TransactionTypes.InvalidTransaction(e)

	print('control address appears valid for', decodedTX['txid'])

	swapBillTransaction = TransactionTypes.Decode(typeCode, amount, maxBlock, extraData)
	if swapBillTransaction.needsControlAddressAmount:
		swapBillTransaction.controlAddressAmount = ToSatoshis(float(decodedTX['vout'][0]['value']))
	if swapBillTransaction.needsSourceAddress:
		swapBillTransaction.sourceAddress = _singleSourceAddress(decodedTX, rpcHost)
		if swapBillTransaction.sourceAddress == None:
			print('Looks like swapbill transaction, but no single source address')
			return None
	if swapBillTransaction.needsDestinationAddress:
		if len(decodedTX['vout']) < 2:
			print('Looks like swapbill transaction, but missing destination address')
			return None
		swapBillTransaction.destinationAddress = _singleAddressFromOutput(decodedTX['vout'][1])

	return swapBillTransaction
