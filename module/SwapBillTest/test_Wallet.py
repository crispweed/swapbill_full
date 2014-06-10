from __future__ import print_function
import unittest, os
from SwapBill import Wallet
#from SwapBill import Address

walletFile = 'testWallet.txt'

class Test(unittest.TestCase):
	def test(self):
		if os.path.exists(walletFile):
			os.remove(walletFile)
		wallet = Wallet.Wallet(walletFile, b'\xef') # litecoin testnet private key address version)
		#print(Address.FromPubKeyHash(b'\x6f', wallet.addKeyPairAndReturnPubKeyHash()))
		addresses = []
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys1 = wallet._privateKeys
		self.assertEqual(len(privateKeys1), 2)
		wallet = Wallet.Wallet(walletFile, b'\xef') # litecoin testnet private key address version)
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys2 = wallet._privateKeys
		self.assertEqual(len(privateKeys2), 3)
		self.assertEqual(privateKeys2[:2], privateKeys1)
		self.assertFalse(wallet.hasKeyPairForPubKeyHash(b'fakePubKeyHash'))
		os.remove(walletFile)

	def test_key_pairs(self):
		generator = Wallet.DefaultKeyGenerator()
		pubKeyHash = generator.privateKeyToPubKeyHash(b"\x0c\x28\xfc\xa3\x86\xc7\xa2'`\x0b/\xe5\x0b|\xae\x11\xec\x86\xd3\xbf\x1f\xbeG\x1b\xe8\x98'\xe1\x9dr\xaa\x1d")
		self.assertEqual(pubKeyHash, b'\xa6]\x1a#\x9dN\xc6fd=5\x0c{\xb8\xfcD\xd2\x88\x11(')
		privateKey = generator.generatePrivateKey()
		pubKeyHash = generator.privateKeyToPubKeyHash(privateKey)
		self.assertIs(type(pubKeyHash), type(b''))
		self.assertEqual(len(pubKeyHash), 20)

