import struct, binascii

class NotSwapBillTransaction(Exception):
	pass
class NotEnoughOutputs(Exception):
	pass

class _RanOutOfData(Exception):
	pass

# Constants
OP_RETURN = b'\x6a'
OP_PUSHDATA1 = b'\x4c'
OP_DUP = b'\x76'
OP_HASH160 = b'\xa9'
OP_EQUALVERIFY = b'\x88'
OP_CHECKSIG = b'\xac'
OP_1 = b'\x51'
OP_2 = b'\x52'
OP_CHECKMULTISIG = b'\xae'

def _encodeVarInt(i):
	if i < 0xfd:
		return struct.pack("<B", i)
	elif i <= 0xffff:
		return b'\xfd' + struct.pack("<H", i)
	elif i <= 0xffffffff:
		return b'\xfe' + struct.pack("<L", i)
	else:
		return b'\xff' + struct.pack("<Q", i)

def _decodeVarInt(data, startPos):
	assert type(data) == type(b'')
	firstByte = data[startPos:startPos + 1]
	if firstByte == b'\xff':
		if startPos + 9 > len(data):
			raise _RanOutOfData()
		return startPos + 9, struct.unpack("<Q", data[startPos + 1:startPos + 9])[0]
	if firstByte == b'\xfe':
		if startPos + 5 > len(data):
			raise _RanOutOfData()
		return startPos + 5, struct.unpack("<L", data[startPos + 1:startPos + 5])[0]
	if firstByte == b'\xfd':
		if startPos + 3 > len(data):
			raise _RanOutOfData()
		return startPos + 3, struct.unpack("<H", data[startPos + 1:startPos + 3])[0]
	if startPos + 1 > len(data):
		raise _RanOutOfData()
	return startPos + 1, struct.unpack("<B", data[startPos:startPos + 1])[0]

def _opPush(i):
	if i < 0x4c:
		return struct.pack("<B", i)
	elif i <= 0xff:
		return b'\x4c' + struct.pack("<B", i)
	elif i <= 0xffff:
		return b'\x4d' + struct.pack("<H", i)
	else:
		return b'\x4e' + struct.pack("<L", i)

def ScriptPubKeyForPubKeyHash(pubKeyHash):
	assert type(pubKeyHash) == type(b'')
	assert len(pubKeyHash) == 20
	expectedScriptStart = OP_DUP
	expectedScriptStart += OP_HASH160
	expectedScriptStart += _opPush(20)
	expectedScriptEnd = OP_EQUALVERIFY
	expectedScriptEnd += OP_CHECKSIG
	return binascii.hexlify(expectedScriptStart + pubKeyHash + expectedScriptEnd).decode('ascii')
def PubKeyHashForScriptPubKey(scriptPubKey):
	scriptPubKeyBytes = binascii.unhexlify(scriptPubKey.encode('ascii'))
	expectedScriptStart = OP_DUP
	expectedScriptStart += OP_HASH160
	expectedScriptStart += _opPush(20)
	expectedScriptEnd = OP_EQUALVERIFY
	expectedScriptEnd += OP_CHECKSIG
	assert scriptPubKeyBytes.startswith(expectedScriptStart)
	assert scriptPubKeyBytes.endswith(expectedScriptEnd)
	pubKeyHash = scriptPubKeyBytes[len(expectedScriptStart):-len(expectedScriptEnd)]
	assert len(pubKeyHash) == 20
	return pubKeyHash

def Create(tx, scriptPubKeyLookup):
	data = struct.pack("<L", 1) # version, 4 byte little endian

	# Number of inputs.
	## TODO: force to  < 0xfd for SB transactions?
	data += _encodeVarInt(int(tx.numberOfInputs()))

	# List of Inputs.
	for i in range(tx.numberOfInputs()):
		txid = tx.inputTXID(i)
		vout = tx.inputVOut(i)
		scriptPubKey = scriptPubKeyLookup[(txid, vout)]
		#assert type(txid) == str
		#assert type(scriptPubKey) == str
		txIDBytes = binascii.unhexlify(txid.encode('ascii'))[::-1]
		assert len(txIDBytes) == 32
		data += txIDBytes
		data += struct.pack("<L", vout)
		script = binascii.unhexlify(scriptPubKey.encode('ascii'))
		## TODO: force script length to < 0xfd for SB transactions?
		data += _encodeVarInt(int(len(script)))
		data += script
		data += b'\xff' * 4                                    # Sequence

	# Number of outputs.
	data += _encodeVarInt(tx.numberOfOutputs())

	for i in range(tx.numberOfOutputs()):
		pubKeyHash = tx.outputPubKeyHash(tx.numberOfOutputs() - 1 - i)
		value = tx.outputAmount(tx.numberOfOutputs() - 1 - i)
		assert len(pubKeyHash) == 20
		data += struct.pack("<Q", value)
		script = OP_DUP
		script += OP_HASH160
		script += _opPush(20)
		script += pubKeyHash
		script += OP_EQUALVERIFY
		script += OP_CHECKSIG
		data += _encodeVarInt(int(len(script)))
		data += script

	data += struct.pack("<L", 0)                # LockTime
	return data

def UnexpectedFormat_Fast(txBytes, controlAddressPrefix):
	## TODO: optimise this by putting the control address at the end of the transaction!
	assert type(txBytes) is type(b'')
	assert type(controlAddressPrefix) is type(b'')
	assert len(controlAddressPrefix) <= 20
	if len(txBytes) < 6: ## actual minimum is greater than this, work this out!
		return True
	version = struct.unpack("<L", txBytes[:4])[0]
	if version != 1:
		return True
	pos = 4
	try:
		pos, numberOfInputs = _decodeVarInt(txBytes, pos)
		for i in range(numberOfInputs):
			pos += 36
			pos, scriptLen = _decodeVarInt(txBytes, pos)
			pos += scriptLen
			pos += 4
		pos, numberOfOutputs = _decodeVarInt(txBytes, pos)
		if numberOfOutputs == 0:
			return True
		for i in range(numberOfOutputs):
			pos += 8
			pos, scriptLen = _decodeVarInt(txBytes, pos)
			if i == 0:
				script = txBytes[pos:pos + scriptLen]
				expectedScriptStart = OP_DUP
				expectedScriptStart += OP_HASH160
				expectedScriptStart += _opPush(20)
				expectedScriptEnd = OP_EQUALVERIFY
				expectedScriptEnd += OP_CHECKSIG
				if len(script) != len(expectedScriptStart) + 20 + len(expectedScriptEnd):
					return True
				if not script.startswith(expectedScriptStart):
					return True
				if not script[len(expectedScriptStart):].startswith(controlAddressPrefix):
					return True
				if not script.endswith(expectedScriptEnd):
					return True
			pos += scriptLen
	except _RanOutOfData:
		return True
	if pos + 4 != len(txBytes):
		return True
	return False

def ExtractOutputPubKeyHash(txBytes, outputIndex):
	assert type(txBytes) is type(b'')
	assert outputIndex >= 0

	if UnexpectedFormat_Fast(txBytes, b''):
		raise NotSwapBillTransaction()

	pos = 4

	pos, numberOfInputs = _decodeVarInt(txBytes, pos)

	for i in range(numberOfInputs):
		pos += 32
		pos += 4
		pos, scriptLen = _decodeVarInt(txBytes, pos)
		#print(i, scriptLen)
		pos += scriptLen
		pos += 4
		assert pos < len(txBytes)

	pos, numberOfOutputs = _decodeVarInt(txBytes, pos)

	if outputIndex >= numberOfOutputs:
		raise NotEnoughOutputs()

	for i in range(outputIndex):
		pos += 8
		pos, scriptLen = _decodeVarInt(txBytes, pos)
		pos += scriptLen

	pos += 8
	pos, scriptLen = _decodeVarInt(txBytes, pos)
	expectedScriptStart = OP_DUP
	expectedScriptStart += OP_HASH160
	expectedScriptStart += _opPush(20)
	pos += len(expectedScriptStart)
	assert len(txBytes) > pos + 20
	return txBytes[pos:pos + 20]

## TODO change this to decode to in memory transaction
def Decode(txBytes):
	assert type(txBytes) is type(b'')
	assert not UnexpectedFormat_Fast(txBytes, b'')

	result = {}

	pos = 4
	pos, numberOfInputs = _decodeVarInt(txBytes, pos)

	inputs = []
	for i in range(numberOfInputs):
		thisInput = {}
		txIDBytes = txBytes[pos:pos + 32]
		pos += 32
		thisInput['txid'] = binascii.hexlify(txIDBytes[::-1]).decode('ascii')
		#thisInput['txID'] = txIDBytes[::-1]
		thisInput['vout'] = struct.unpack("<L", txBytes[pos:pos + 4])[0]
		pos += 4
		pos, scriptLen = _decodeVarInt(txBytes, pos)
		scriptPubKeyBytes = txBytes[pos:pos + scriptLen]
		pos += scriptLen
		thisInput['scriptPubKey'] = binascii.hexlify(scriptPubKeyBytes).decode('ascii')
		#thisInput['scriptPubKey'] = scriptPubKeyBytes
		pos += 4 # sequence
		inputs.append(thisInput)
	result['vin'] = inputs

	pos, numberOfOutputs = _decodeVarInt(txBytes, pos)

	outputs = []
	for i in range(numberOfOutputs):
		thisOutput = {}
		thisOutput['value'] = struct.unpack("<Q", txBytes[pos:pos + 8])[0]
		pos += 8
		pos, scriptLen = _decodeVarInt(txBytes, pos)
		scriptSigBytes = txBytes[pos:pos + scriptLen]
		pos += scriptLen
		thisOutput['scriptPubKey'] = binascii.hexlify(scriptSigBytes).decode('ascii')
		expectedScriptStart = OP_DUP
		expectedScriptStart += OP_HASH160
		expectedScriptStart += _opPush(20)
		pubKeyHash = scriptSigBytes[len(expectedScriptStart):len(expectedScriptStart)+20]
		assert len(pubKeyHash) == 20
		#thisOutput['pubKeyHash'] = pubKeyHash
		thisOutput['pubKeyHash'] = binascii.hexlify(pubKeyHash).decode('ascii')
		outputs.append(thisOutput)
	outputs.reverse()
	result['vout'] = outputs

	return result

def FromHex(hexStr):
	return binascii.unhexlify(hexStr.encode('ascii'))
def ToHex(data):
	return binascii.hexlify(data).decode('ascii')

