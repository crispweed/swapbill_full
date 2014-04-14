from __future__ import print_function
import unittest
from SwapBill import GetUnspent

class MockRPCHost(object):
	def __init__(self):
		self._d = {}
	def call(self, *arguments):
		return self._d[arguments]

class Test(unittest.TestCase):
	def test(self):
		addressVersion = b'\x6f'
		rpcHost = MockRPCHost()

		pubKeyHash1 = b'SWB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00extrad'
		address1 = 'mo7cukkECVHPxAEApxTJAQnbRj8xSHUzkH'
		pubKeyHash2 = b'SWB\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0bxtrada'
		address2 = 'mo7cukopgWjYZqRxZ5gxbYWXqHrLS9tKsx'
		pubKeyHash3 = b'\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1babcdefghi'
		address3 = 'mh5DS9xE4PBBhB5eHKRCNaEzekgspzxATY'

		rpcHost._d[('listunspent',)] = [
		    {'txid':'tx1', 'vout':0, 'amount':1.0, 'address':address1, 'scriptPubKey':'pubKey1', 'account':'account1'},
		    {'txid':'tx2', 'vout':1, 'amount':2.1, 'address':address1, 'scriptPubKey':'pubKey2', 'account':'account1'},
		    {'txid':'tx3', 'vout':3, 'amount':4.3, 'address':address2, 'scriptPubKey':'pubKey3', 'account':'account2'},
		    {'txid':'tx4', 'vout':0, 'amount':10.2, 'address':address3,  'scriptPubKey':'pubKey4'}
		]
		swapBillBalances = {pubKeyHash2:20}
		amounts, asInputs = GetUnspent.AllNonSwapBill(addressVersion, rpcHost, swapBillBalances)
		self.assertListEqual(amounts, [100000000, 210000000, 1019999999])
		self.assertListEqual(asInputs, [('tx1', 0, 'pubKey1'), ('tx2', 1, 'pubKey2'), ('tx4', 0, 'pubKey4')])
		amount, asInput = GetUnspent.SingleForAddress(addressVersion, rpcHost, pubKeyHash2)
		self.assertEqual(amount, 430000000)
		self.assertTupleEqual(asInput, ('tx3', 3, 'pubKey3'))
		amount, asInput = GetUnspent.SingleForAddress(addressVersion, rpcHost, pubKeyHash1)
		## (returns first with the address, currently, but could potentially do some kind of selection)
		self.assertEqual(amount, 100000000)
		self.assertTupleEqual(asInput, ('tx1', 0, 'pubKey1'))
