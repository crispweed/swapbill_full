from __future__ import print_function
import unittest, os
from SwapBill import Wallet
#from SwapBill import Address

walletFile = 'testWallet.txt'

class Test(unittest.TestCase):
	def test(self):
		if os.path.exists(walletFile):
			os.remove(walletFile)
		wallet = Wallet.Wallet(walletFile)
		#print(Address.FromPubKeyHash(b'\x6f', wallet.addKeyPairAndReturnPubKeyHash()))
		addresses = []
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys1 = wallet.getAllPrivateKeys()
		self.assertEqual(len(privateKeys1), 2)
		wallet = Wallet.Wallet(walletFile)
		addresses.append(wallet.addKeyPairAndReturnPubKeyHash())
		for address in addresses:
			self.assertTrue(wallet.hasKeyPairForPubKeyHash(address))
		privateKeys2 = wallet.getAllPrivateKeys()
		self.assertEqual(len(privateKeys2), 3)
		self.assertEqual(privateKeys2[:2], privateKeys1)
		self.assertFalse(wallet.hasKeyPairForPubKeyHash(b'fakePubKeyHash'))
		os.remove(walletFile)
