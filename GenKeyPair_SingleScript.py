from __future__ import print_function
import sys
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
import os
import binascii
import hashlib
import ecdsa # try "pip install ecdsa"!

digits = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def Base58Check_CheckSum(data):
	return hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]

def Base58Check_Encode(data):
	assert type(data) is type(b'')
	withChecksum = data + Base58Check_CheckSum(data)
	n = int('0x0' + binascii.hexlify(withChecksum).decode('ascii'), 16)
	base58 = ''
	while n > 0:
		n, r = divmod(n, 58)
		base58 += digits[r]
	pad = 0
	while data[pad:pad+1] == b'\x00':
		pad += 1
	return digits[0] * pad + base58[::-1]

def AddressFromPubKeyHash(addressVersion, data):
	assert type(addressVersion) is type(b'.')
	assert type(data) is type(b'.')
	assert len(addressVersion) == 1
	assert len(data) == 20
	return Base58Check_Encode(addressVersion + data)

def PrivateKeyToWIF(data, addressVersion):
	assert type(addressVersion) is type(b'.')
	assert type(data) is type(b'.')
	assert len(addressVersion) == 1
	assert len(data) == 32
	return Base58Check_Encode(addressVersion + data)

def GeneratePrivateKey():
	return os.urandom(32)
def PrivateKeyToPubKeyHash(privateKey):
	sk = ecdsa.SigningKey.from_string(privateKey, curve=ecdsa.SECP256k1)
	vk = sk.verifying_key
	publicKey = sk.verifying_key.to_string()
	ripemd160 = hashlib.new('ripemd160')
	ripemd160.update(hashlib.sha256(b'\x04' + publicKey).digest())
	return ripemd160.digest()

privateKey = GeneratePrivateKey()
print(PrivateKeyToWIF(privateKey, b'\x80')) # bitcoin mainnet private key address version
pubKeyHash = PrivateKeyToPubKeyHash(privateKey)
address = AddressFromPubKeyHash(b'\x00', pubKeyHash) # bitcoin mainnet address version
print(address)
