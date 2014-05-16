from __future__ import print_function
import unittest
from SwapBill import KeyPair
from SwapBill import Address

class Test(unittest.TestCase):
	def test(self):
		privateKey = KeyPair.privateKeyFromWIF('5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ')
		self.assertEqual(privateKey,  b"\x0c\x28\xfc\xa3\x86\xc7\xa2'`\x0b/\xe5\x0b|\xae\x11\xec\x86\xd3\xbf\x1f\xbeG\x1b\xe8\x98'\xe1\x9dr\xaa\x1d")
		publicKey = KeyPair.privateKeyToPublicKey(privateKey)
		self.assertEqual(publicKey,  b'\xd0\xde\n\xae\xae\xfa\xd0+\x8b\xdc\x8a\x01\xa1\xb8\xb1\x1cik\xd3\xd6j,_\x10x\r\x95\xb7\xdfBd\\\xd8R(\xa6\xfb)\x94\x0e\x85\x8e~U\x84*\xe2\xbd\x11]\x1e\xd7\xcc\x0e\x82\xd94\xe9)\xc9vH\xcb\n')
		pubKeyHash = KeyPair.publicKeyToPubKeyHash(publicKey)
		self.assertEqual(pubKeyHash, b'\x12m\xab\xa48\xea\x84\xe7\xc4</V\xa3 \x0e\xd6^7\x1b;')
		print(Address.FromPubKeyHash(b'\x6f', pubKeyHash))
		# sent to this address with txID = 6af9e8e3f4702e70666bd26d93d28e3722b5aa4ef2a8626b51289f707a78959a
