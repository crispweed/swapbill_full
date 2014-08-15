from __future__ import print_function
import ecdsa, hashlib, os, binascii
from SwapBill import Address

def PublicKeyToPubKeyHash(publicKey):
	assert type(publicKey) is type(b'')
	ripemd160 = hashlib.new('ripemd160')
	ripemd160.update(hashlib.sha256(b'\x04' + publicKey).digest())
	return ripemd160.digest()

class DefaultKeyGenerator(object):
	def generatePrivateKey(self):
		return os.urandom(32)
	def privateKeyToPubKeyHash(self, privateKey):
		sk = ecdsa.SigningKey.from_string(privateKey, curve=ecdsa.SECP256k1)
		vk = sk.verifying_key
		publicKey = sk.verifying_key.to_string()
		return PublicKeyToPubKeyHash(publicKey)

class Wallet(object):
	def __init__(self, fileName, keyGenerator=None):
		if keyGenerator is None:
			keyGenerator = DefaultKeyGenerator()
		self._keyGenerator = keyGenerator
		self._fileName = fileName
		self._privateKeys = []
		self._pubKeyHashes = []
		if os.path.exists(fileName):
			with open(fileName, mode='r') as f:
				lines = f.readlines()
				for line in lines:
					privateKeyHex = line.strip()
					privateKey = binascii.unhexlify(privateKeyHex.encode('ascii'))
					assert type(privateKey) is type(b'')
					assert len(privateKey) == 32
					self._privateKeys.append(privateKey)
					pubKeyHash = self._keyGenerator.privateKeyToPubKeyHash(privateKey)
					self._pubKeyHashes.append(pubKeyHash)

	def addKeyPairAndReturnPubKeyHash(self):
		privateKey = self._keyGenerator.generatePrivateKey()
		privateKeyHex = binascii.hexlify(privateKey).decode('ascii')
		pubKeyHash = self._keyGenerator.privateKeyToPubKeyHash(privateKey)
		self._privateKeys.append(privateKey)
		self._pubKeyHashes.append(pubKeyHash)
		with open(self._fileName, mode='a') as f:
			f.write(privateKeyHex)
			f.write('\n')
		return pubKeyHash

	def hasKeyPairForPubKeyHash(self, pubKeyHash):
		return pubKeyHash in self._pubKeyHashes
	def privateKeyForPubKeyHash(self, pubKeyHash):
		for storedHash, privateKey in zip(self._pubKeyHashes, self._privateKeys):
			if storedHash == pubKeyHash:
				return privateKey
