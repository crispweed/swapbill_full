from __future__ import print_function
import unittest, os
from SwapBill import Wallet

walletFile = 'testWallet.txt'

class Test(unittest.TestCase):
	def test(self):
		if os.path.exists(walletFile):
			os.remove(walletFile)
		wallet = Wallet.Wallet(walletFile)
		addresses = []
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys1 = wallet._privateKeys
		self.assertEqual(len(privateKeys1), 2)
		wallet = Wallet.Wallet(walletFile) # litecoin testnet private key address version)
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys2 = wallet._privateKeys
		self.assertEqual(len(privateKeys2), 3)
		self.assertEqual(privateKeys2[:2], privateKeys1)
		self.assertFalse(wallet.hasKeyPairForPubKeyHash(b'fakePubKeyHash'))
		os.remove(walletFile)

