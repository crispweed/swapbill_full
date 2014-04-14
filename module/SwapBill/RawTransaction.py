import struct, binascii

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
		return startPos + 9, struct.unpack("<Q", data[startPos + 1:startPos + 9])[0]
	if firstByte == b'\xfe':
		return startPos + 5, struct.unpack("<L", data[startPos + 1:startPos + 5])[0]
	if firstByte == b'\xfd':
		return startPos + 3, struct.unpack("<H", data[startPos + 1:startPos + 3])[0]
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

def Create(tx, scriptPubKeyLookup):
	data = struct.pack("<L", 1) # version, 4 byte little endian

	# Number of inputs.
	## TODO: force to  < 0xfd for SB transactions?
	data += _encodeVarInt(int(tx.numberOfInputs()))

	# List of Inputs.
	for i in range(tx.numberOfInputs()):
		txid = tx.inputTXID(i)
		vout = tx.inputVOut(i)
		scriptPubKey = scriptPubKeyLookup.lookupScriptPubKey((txid, vout))
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
		pubKeyHash = tx.outputPubKeyHash(i)
		value = tx.outputAmount(i)
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

def ExtractOutputPubKeyHash(txBytes, outputIndex):
	assert type(txBytes) is type(b'')
	pos = 4
	pos, numberOfInputs = _decodeVarInt(txBytes, pos)
	#print(numberOfInputs)
	for i in range(numberOfInputs):
		pos += 32
		pos += 4
		pos, scriptLen = _decodeVarInt(txBytes, pos)
		#print(i, scriptLen)
		pos += scriptLen
		pos += 4
		assert pos < len(txBytes)
	pos, numberOfOutputs = _decodeVarInt(txBytes, pos)
	assert numberOfOutputs > 0
	#print(numberOfOutputs)
	for i in range(outputIndex):
		pos += 8
		pos, scriptLen = _decodeVarInt(txBytes, pos)
		pos += scriptLen
	pos += 8
	pos, scriptLen = _decodeVarInt(txBytes, pos)
	scriptStart = OP_DUP
	scriptStart += OP_HASH160
	scriptStart += _opPush(20)
	#if len(scriptStart) + 20 >= scriptLen:
		#print(pos)
		#print(scriptLen)
	assert len(scriptStart) + 20 < scriptLen
	pos += len(scriptStart)
	assert len(txBytes) > pos + 20
	return txBytes[pos:pos + 20]

def FromHex(hexStr):
	return binascii.unhexlify(hexStr.encode('ascii'))
def ToHex(data):
	return binascii.hexlify(data).decode('ascii')
