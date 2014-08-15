from __future__ import print_function
import unittest, os
from SwapBill import KeyPair

nextI = 0
def GeneratePrivateKey_ForTests():
	global nextI
	result = str(nextI) + '-' * 31
	nextI += 1
	return result[:32].encode('ascii')
def PrivateKeyToPublicKey_ForTests(privateKey):
	s = privateKey.decode('ascii').strip('-')
	i = int(s)
	result = str(i) + '+' * 63
	return result[:64].encode('ascii')
def PublicKeyToPubKeyHash_ForTests(publicKey):
	s = publicKey.decode('ascii').strip('+')
	i = int(s)
	result = str(i) + '*' * 19
	return result[:20].encode('ascii')

KeyPair.GeneratePrivateKey = GeneratePrivateKey_ForTests
KeyPair.PrivateKeyToPublicKey = PrivateKeyToPublicKey_ForTests
KeyPair.PublicKeyToPubKeyHash = PublicKeyToPubKeyHash_ForTests

class Test(unittest.TestCase):
	def test_key_pairs(self):
		privateKey = b"\x0c\x28\xfc\xa3\x86\xc7\xa2'`\x0b/\xe5\x0b|\xae\x11\xec\x86\xd3\xbf\x1f\xbeG\x1b\xe8\x98'\xe1\x9dr\xaa\x1d"
		publicKey = KeyPair._privateKeyToPublicKey(privateKey)
		self.assertEqual(publicKey, b'\xd0\xde\n\xae\xae\xfa\xd0+\x8b\xdc\x8a\x01\xa1\xb8\xb1\x1cik\xd3\xd6j,_\x10x\r\x95\xb7\xdfBd\\\xd8R(\xa6\xfb)\x94\x0e\x85\x8e~U\x84*\xe2\xbd\x11]\x1e\xd7\xcc\x0e\x82\xd94\xe9)\xc9vH\xcb\n')
		pubKeyHash = KeyPair._publicKeyToPubKeyHash(publicKey)
		self.assertEqual(pubKeyHash, b'\xa6]\x1a#\x9dN\xc6fd=5\x0c{\xb8\xfcD\xd2\x88\x11(')
		privateKey = KeyPair._generatePrivateKey()
		publicKey = KeyPair._privateKeyToPublicKey(privateKey)
		pubKeyHash = KeyPair._publicKeyToPubKeyHash(publicKey)
		self.assertIs(type(pubKeyHash), type(b''))
		self.assertEqual(len(pubKeyHash), 20)
