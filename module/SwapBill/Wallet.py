from __future__ import print_function
import ecdsa, hashlib, os, binascii
from SwapBill import KeyPair

class Wallet(object):
	def __init__(self, fileName):
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
					publicKey = KeyPair.PrivateKeyToPublicKey(privateKey)
					pubKeyHash = KeyPair.PublicKeyToPubKeyHash(publicKey)
					self._pubKeyHashes.append(pubKeyHash)

	def addKeyPairAndReturnPubKeyHash(self):
		privateKey = KeyPair.GeneratePrivateKey()
		privateKeyHex = binascii.hexlify(privateKey).decode('ascii')
		publicKey = KeyPair.PrivateKeyToPublicKey(privateKey)
		pubKeyHash = KeyPair.PublicKeyToPubKeyHash(publicKey)
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
	def publicKeyForPubKeyHash(self, pubKeyHash):
		for storedHash, privateKey in zip(self._pubKeyHashes, self._privateKeys):
			if storedHash == pubKeyHash:
				publicKey = KeyPair.PrivateKeyToPublicKey(privateKey)
				return publicKey
