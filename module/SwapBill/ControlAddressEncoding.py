import struct

class InvalidControlAddress(Exception):
	pass

prefix = b'SWB'
formatStruct = struct.Struct('<BHLL')

def Encode(transaction):
	typeCode = transaction.typeCode
	assert type(typeCode) is int
	assert typeCode >= 0 and typeCode <= 0xff
	amount, maxBlock, extraData = transaction.encode()
	assert type(amount) is int
	assert amount >= 0 and amount <= 0xffffffffffff
	assert type(maxBlock) is int
	assert maxBlock >= 0 and maxBlock <= 0xffffffff
	assert type(extraData) is type(b'0')
	assert len(extraData) is 6
	amountLow = (amount & 0xffff)
	amountHigh = (amount >> 16)
	return prefix + formatStruct.pack(typeCode, amountLow, amountHigh, maxBlock) + extraData

def Decode(address):
	assert type(address) is type(b'0')
	assert len(address) == 20
	decodedPrefix = address[:3]
	if prefix != decodedPrefix:
		raise InvalidControlAddress
	typeCode, amountLow, amountHigh, maxBlock = formatStruct.unpack(address[3:-6])
	extraData = address[-6:]
	amount = (amountHigh << 16) + amountLow
	return typeCode, amount, maxBlock, extraData
