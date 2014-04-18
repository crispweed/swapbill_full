import struct

class NotSwapBillControlAddress(Exception):
	pass

prefix = b'SWB'
formatStruct = struct.Struct('<BHLL')

#def Encode(transaction):
	#typeCode, amount, maxBlock, extraData = transaction.encode()
def Encode(typeCode, amount, maxBlock, extraData):
	assert type(typeCode) is int
	assert typeCode >= 0 and typeCode <= 0xff
	assert type(amount) is int
	assert amount >= 0 and amount <= 0xffffffffffff
	assert type(maxBlock) is int
	assert maxBlock >= 0 and maxBlock <= 0xffffffff
	assert type(extraData) is type(b'0')
	assert len(extraData) is 6
	amountLow = (amount & 0xffff)
	amountHigh = (amount >> 16)
	return prefix + formatStruct.pack(typeCode, amountLow, amountHigh, maxBlock) + extraData

def Decode(pubKeyHash):
	assert type(pubKeyHash) is type(b'0')
	assert len(pubKeyHash) == 20
	decodedPrefix = pubKeyHash[:3]
	if prefix != decodedPrefix:
		raise NotSwapBillControlAddress
	typeCode, amountLow, amountHigh, maxBlock = formatStruct.unpack(pubKeyHash[3:-6])
	extraData = pubKeyHash[-6:]
	amount = (amountHigh << 16) + amountLow
	return typeCode, amount, maxBlock, extraData
