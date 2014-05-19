from __future__ import print_function
import unittest, os
from SwapBill import Wallet, Address

walletFile = 'testWallet.txt'

class Test(unittest.TestCase):
	def test(self):
		if os.path.exists(walletFile):
			os.remove(walletFile)
		wallet = Wallet.Wallet(walletFile)
		Address.FromPubKeyHash(b'\x6f', wallet.addKeyPairAndReturnPubKeyHash())
		Address.FromPubKeyHash(b'\x6f', wallet.addKeyPairAndReturnPubKeyHash())
		#print(Address.FromPubKeyHash(b'\x6f', wallet.addKeyPairAndReturnPubKeyHash()))
		#print(wallet.getAllPrivateKeys())
		privateKeys1 = wallet.getAllPrivateKeys()
		self.assertEqual(len(privateKeys1), 2)
		wallet = Wallet.Wallet(walletFile)
		Address.FromPubKeyHash(b'\x6f', wallet.addKeyPairAndReturnPubKeyHash())
		#print(wallet.getAllPrivateKeys())
		privateKeys2 = wallet.getAllPrivateKeys()
		self.assertEqual(len(privateKeys2), 3)
		self.assertEqual(privateKeys2[:2], privateKeys1)
