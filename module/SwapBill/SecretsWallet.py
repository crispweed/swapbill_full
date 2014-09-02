from __future__ import print_function
import ecdsa, hashlib, os
from SwapBill import KeyPair, FileBackedList, Util

class SecretsWallet(object):
	def __init__(self, fileName):
		self._fileName = fileName
		self._publicKeys = []
		self._pubKeyHashes = []
		if os.path.exists(fileName):
			with open(fileName, mode='r') as f:
				lines = f.readlines()
				for line in lines:
					publicKeyHex = line.strip()
					publicKey = Util.fromHex(publicKeyHex)
					assert type(publicKey) is type(b'')
					assert len(publicKey) == 64
					self._publicKeys.append(publicKey)
					pubKeyHash = KeyPair.PublicKeyToPubKeyHash(publicKey)
					self._pubKeyHashes.append(pubKeyHash)

	def addPublicKeySecret(self, publicKey=None):
		if publicKey is None:
			publicKey = KeyPair.GenerateRandomPublicKeyForUseAsSecret()
		publicKeyHex = Util.toHex(publicKey)
		pubKeyHash = KeyPair.PublicKeyToPubKeyHash(publicKey)
		self._publicKeys.append(publicKey)
		self._pubKeyHashes.append(pubKeyHash)
		with open(self._fileName, mode='a') as f:
			f.write(publicKeyHex)
			f.write('\n')
		return pubKeyHash

	def hasKeyPairForPubKeyHash(self, pubKeyHash):
		return pubKeyHash in self._pubKeyHashes
	def publicKeyForPubKeyHash(self, pubKeyHash):
		for storedHash, publicKey in zip(self._pubKeyHashes, self._publicKeys):
			if storedHash == pubKeyHash:
				return publicKey
