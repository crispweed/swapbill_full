import struct, binascii
from SwapBill import Address

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

def var_int (i):
	if i < 0xfd:
		#return (i).to_bytes(1, byteorder='little')
		return struct.pack("<B", i)
	elif i <= 0xffff:
		#return b'\xfd' + (i).to_bytes(2, byteorder='little')
		return b'\xfd' + struct.pack("<H", i)
	elif i <= 0xffffffff:
		#return b'\xfe' + (i).to_bytes(4, byteorder='little')
		return b'\xfe' + struct.pack("<L", i)
	else:
		#return b'\xff' + (i).to_bytes(8, byteorder='little')
		return b'\xff' + struct.pack("<Q", i)

def op_push (i):
	if i < 0x4c:
		#return (i).to_bytes(1, byteorder='little')              # Push i bytes.
		return struct.pack("<B", i)
	elif i <= 0xff:
		#return b'\x4c' + (i).to_bytes(1, byteorder='little')    # OP_PUSHDATA1
		return b'\x4c' + struct.pack("<B", i)
	elif i <= 0xffff:
		#return b'\x4d' + (i).to_bytes(2, byteorder='little')    # OP_PUSHDATA2
		return b'\x4d' + struct.pack("<H", i)
	else:
		#return b'\x4e' + (i).to_bytes(4, byteorder='little')    # OP_PUSHDATA4
		return b'\x4e' + struct.pack("<L", i)

def CreateRawTransaction(config, inputs, targetAddresses, targetAmounts):
	assert len(targetAddresses) == len(targetAmounts)

	#s  = (1).to_bytes(4, byteorder='little')                # Version
	s = struct.pack("<L", 1) # version, 4 byte little endian

	# Number of inputs.
	s += var_int(int(len(inputs)))

	# List of Inputs.
	for i in range(len(inputs)):
		txid, vout, scriptPubKey = inputs[i]
		#print(scriptPubKey)
		#s += binascii.unhexlify(bytes(txid, 'utf-8'))[::-1]         # TxOutHash
		s += binascii.unhexlify(txid)[::-1]         # TxOutHash
		#s += vout.to_bytes(4, byteorder='little')   # TxOutIndex
		s += struct.pack("<L", vout)
		#script = binascii.unhexlify(bytes('scriptPubKey', 'utf-8'))
		script = binascii.unhexlify(scriptPubKey)
		s += var_int(int(len(script)))                      # Script length
		s += script                                         # Script
		s += b'\xff' * 4                                    # Sequence

	# Number of outputs.
	s += var_int(len(targetAddresses))

	for i in range(len(targetAddresses)):
		address = targetAddresses[i]
		value = targetAmounts[i]
		pubkeyhash = Address.ToData(config.addressVersion, address)
		#s += value.to_bytes(8, byteorder='little')          # Value
		s += struct.pack("<Q", value)
		script = OP_DUP                                     # OP_DUP
		script += OP_HASH160                                # OP_HASH160
		script += op_push(20)                               # Push 0x14 bytes
		script += pubkeyhash                                # pubKeyHash
		script += OP_EQUALVERIFY                            # OP_EQUALVERIFY
		script += OP_CHECKSIG                               # OP_CHECKSIG
		s += var_int(int(len(script)))                      # Script length
		s += script

	#s += (0).to_bytes(4, byteorder='little')                # LockTime
	s += struct.pack("<L", 0)                # LockTime
	#return s
	return binascii.hexlify(s)
