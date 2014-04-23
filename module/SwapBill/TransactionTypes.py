from __future__ import print_function
import struct, binascii
from SwapBill import Address, HostTransaction, ControlAddressPrefix

class UnsupportedTransaction(Exception):
	pass
class NotValidSwapBillTransaction(Exception):
	pass

_mappingByTypeCode = (
    ('Burn', None, ((0, 16), 'amount'), ('destination',), ()),
    ('Pay', 'sourceAccount', (('amount', 6, 'maxBlock', 4, None, 6), None), ('change','destination'), ()),
    ('LTCBuyOffer',
     'sourceAccount',
     (('swapBillOffered', 6, 'maxBlock', 4, 'exchangeRate', 4, 'maxBlockOffset', 2), None),
     ('change', 'refund'),
     (('receivingAddress', None),)
	),
    ('LTCSellOffer',
     'sourceAccount',
     (('swapBillDesired', 6, 'maxBlock', 4, 'exchangeRate', 4, 'maxBlockOffset', 2), None),
     ('change', 'receiving'),
     ()
	),
    ('LTCExchangeCompletion', None, (('pendingExchangeIndex', 6, None, 10), None), (), (('destinationAddress', 'destinationAmount'),)),
	)

_forwardCompatibilityMapping = ('ForwardToFutureNetworkVersion', None, (('amount', 6, 'maxBlock', 4, None, 6), None), ('change',), ())

def _mappingFromTypeString(transactionType):
	for i in range(len(_mappingByTypeCode)):
		if transactionType == _mappingByTypeCode[i][0]:
			return i, _mappingByTypeCode[i]
	raise Exception('Unknown transaction type string', transactionType)
def _mappingFromTypeCode(typeCode):
	if typeCode < len(_mappingByTypeCode):
		return _mappingByTypeCode[typeCode]
	if typeCode < 128:
		return _forwardCompatibilityMapping
	raise UnsupportedTransaction()

def _decodeInt(data):
	multiplier = 1
	result = 0
	for i in range(len(data)):
		byteValue = struct.unpack('<B', data[i:i + 1])[0]
		result += byteValue * multiplier
		multiplier = multiplier << 8
	return result

def _encodeInt(value, numberOfBytes):
	result = b''
	for i in range(numberOfBytes):
		byteValue = value & 255
		value = value // 256
		result += struct.pack('<B', byteValue)
	assert value == 0
	return result

def ToStateTransaction(tx):
	controlAddressData = tx.outputPubKeyHash(0)
	assert controlAddressData.startswith(ControlAddressPrefix.prefix)
	assert len(ControlAddressPrefix.prefix) == 3
	typeCode = _decodeInt(controlAddressData[3:4])
	mapping = _mappingFromTypeCode(typeCode)
	transactionType = mapping[0]
	details = {}
	if mapping[1] is not None:
		details[mapping[1]] = (tx.inputTXID(0), tx.inputVOut(0))
	controlAddressMapping, amountMapping = mapping[2]
	pos = 4
	for i in range(len(controlAddressMapping) // 2):
		valueMapping = controlAddressMapping[i * 2]
		numberOfBytes = controlAddressMapping[i * 2 + 1]
		data = controlAddressData[pos:pos + numberOfBytes]
		if valueMapping == 0:
			if data != struct.pack('<B', 0) * numberOfBytes:
				raise NotValidSwapBillTransaction
		elif valueMapping is not None:
			details[valueMapping] = _decodeInt(data)
		pos += numberOfBytes
	assert pos == 20
	if amountMapping is not None:
		details[amountMapping] = tx.outputAmount(0)
	outputs = mapping[3]
	destinations = mapping[4]
	for i in range(len(destinations)):
		addressMapping, amountMapping = destinations[i]
		assert addressMapping is not None
		if addressMapping is not None:
			details[addressMapping] = tx.outputPubKeyHash(1 + len(outputs) + i)
		if amountMapping is not None:
			details[amountMapping] = tx.outputAmount(1 + len(outputs) + i)
	return transactionType, outputs, details

def FromStateTransaction(transactionType, outputs, outputPubKeyHashes, details):
	assert len(outputs) == len(outputPubKeyHashes)
	typeCode, mapping = _mappingFromTypeString(transactionType)
	tx = HostTransaction.InMemoryTransaction()
	if mapping[1] is not None:
		txID, vout = details[mapping[1]]
		tx.addInput(txID, vout)
	controlAddressMapping, amountMapping = mapping[2]
	controlAddressData = ControlAddressPrefix.prefix + _encodeInt(typeCode, 1)
	for i in range(len(controlAddressMapping) // 2):
		valueMapping = controlAddressMapping[i * 2]
		numberOfBytes = controlAddressMapping[i * 2 + 1]
		#data = controlAddressData[pos:pos + numberOfBytes]
		value = 0
		if valueMapping is not None and valueMapping != 0:
			value = details[valueMapping]
		controlAddressData += _encodeInt(value, numberOfBytes)
	assert len(controlAddressData) == 20
	if amountMapping is None:
		amount = 0
	else:
		amount = details[amountMapping]
	tx.addOutput(controlAddressData, amount)
	expectedOutputs = mapping[3]
	assert expectedOutputs == outputs
	for pubKeyHash in outputPubKeyHashes:
		tx.addOutput(pubKeyHash, 0)
	destinations = mapping[4]
	for addressMapping, amountMapping in destinations:
		assert addressMapping is not None
		amount = details[amountMapping] if amountMapping is not None else 0
		tx.addOutput(details[addressMapping], amount)
	transactionType_Check, outputs_Check, details_Check = ToStateTransaction(tx)
	assert transactionType_Check == transactionType
	assert outputs_Check == outputs
	assert details_Check == details
	return tx
