from __future__ import print_function
import struct, binascii
from SwapBill import Address, HostTransaction

class UnsupportedTransaction(Exception):
	pass
class NotValidSwapBillTransaction(Exception):
	pass

_mappingByTypeCode = (
    ('Burn', None, ((0, 16), 'amount'), ('destinationAccount', None)),
    ('Pay', 'sourceAccount', (('amount', 6, 'maxBlock', 4, None, 6), None), ('changeAccount', None), ('destinationAccount', None)),
    ('LTCBuyOffer',
     'sourceAccount',
     (('swapBillOffered', 6, 'maxBlock', 4, 'exchangeRate', 4, 'maxBlockOffset', 2), None),
     ('changeAccount', None), ('receivingAccount', None), ('refundAccount', None)
	),
    ('LTCSellOffer',
     'sourceAccount',
     (('swapBillDesired', 6, 'maxBlock', 4, 'exchangeRate', 4, 'maxBlockOffset', 2), None),
     ('changeAccount', None), ('receivingAccount', None)
	),
    ('LTCExchangeCompletion', None, (('pendingExchangeIndex', 6, None, 10), None), ('destinationAccount', 'destinationAmount')),
	)

_forwardCompatibilityMapping = ('ForwardToFutureNetworkVersion', None, (('amount', 6, 'maxBlock', 4, None, 6), None), ('changeAccount', None))

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

def ToStateTransaction(sourceLookup, tx):
	controlAddressData = tx.outputPubKeyHash(0)
	assert controlAddressData.startswith(b'SWB')
	typeCode = _decodeInt(controlAddressData[3:4])
	if typeCode < len(_mappingByTypeCode):
		mapping = _mappingByTypeCode[typeCode]
	elif typeCode < 128:
		mapping = _forwardCompatibilityMapping
	else:
		raise UnsupportedTransaction()
	transactionType = mapping[0]
	details = {}
	if mapping[1] is not None:
		details[mapping[1]] = sourceLookup.first(tx)
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
	for i in range(len(mapping) - 3):
		addressMapping, amountMapping = mapping[3 + i]
		assert addressMapping is not None
		if addressMapping is not None:
			details[addressMapping] = tx.outputPubKeyHash(1 + i)
		if amountMapping is not None:
			details[amountMapping] = tx.outputAmount(1 + i)
	return transactionType, details

def _addInput(tx, inputProvider, sourceAccount):
	txID, vout = inputProvider.lookupUnspentFor(sourceAccount)
	tx.addInput(txID, vout)

def FromStateTransaction(transactionType, details, inputProvider):
	tx = HostTransaction.InMemoryTransaction()
	for i in range(len(_mappingByTypeCode)):
		if transactionType == _mappingByTypeCode[i][0]:
			mapping = _mappingByTypeCode[i]
			typeCode = i
			break
	if mapping[1] is not None:
		_addInput(tx, inputProvider, details[mapping[1]])
	controlAddressMapping, amountMapping = mapping[2]
	controlAddressData = b'SWB' + _encodeInt(typeCode, 1)
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
	for i in range(len(mapping) - 3):
		addressMapping, amountMapping = mapping[3 + i]
		assert addressMapping is not None
		amount = details[amountMapping] if amountMapping is not None else 0
		tx.addOutput(details[addressMapping], amount)
	return tx

