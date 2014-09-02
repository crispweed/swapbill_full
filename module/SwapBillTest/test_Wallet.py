from __future__ import print_function
import unittest, os
from SwapBill import Wallet, FileBackedList

walletFile = 'testWallet.txt'

class Test(unittest.TestCase):
	def test(self):
		if os.path.exists(walletFile):
			os.remove(walletFile)
		walletPrivateKeys = FileBackedList.FileBackedList(walletFile)
		wallet = Wallet.Wallet(walletPrivateKeys)
		addresses = []
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys1 = list(wallet._privateKeys)
		self.assertEqual(len(privateKeys1), 2)
		walletPrivateKeys = FileBackedList.FileBackedList(walletFile)
		wallet = Wallet.Wallet(walletPrivateKeys)
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys2 = list(wallet._privateKeys)
		self.assertEqual(len(privateKeys2), 3)
		self.assertEqual(privateKeys2[:2], privateKeys1)
		self.assertFalse(wallet.hasKeyPairForPubKeyHash(b'fakePubKeyHash'))
		os.remove(walletFile)

