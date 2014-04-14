from __future__ import print_function
import unittest
from SwapBill import Address

class Test(unittest.TestCase):
	def test(self):
		version = b'\x6f'
		pubKeyHash = b'SWB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00extrad'
		address = Address.FromPubKeyHash(version, pubKeyHash)
		assert type(address) is str
		self.assertEqual(address, 'mo7cukkECVHPxAEApxTJAQnbRj8xSHUzkH')
		pubKeyHash2 = Address.ToPubKeyHash(version, address)
		assert type(pubKeyHash2) is type(b'')
		self.assertEqual(pubKeyHash, pubKeyHash2)
		pubKeyHash = b'SWB\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0bxtrada'
		address = Address.FromPubKeyHash(version, pubKeyHash)
		self.assertEqual(address, 'mo7cukopgWjYZqRxZ5gxbYWXqHrLS9tKsx')
		pubKeyHash2 = Address.ToPubKeyHash(version, address)
		self.assertEqual(pubKeyHash, pubKeyHash2)
		pubKeyHash = b'\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1babcdefghi'
		address = Address.FromPubKeyHash(version, pubKeyHash)
		self.assertEqual(address, 'mh5DS9xE4PBBhB5eHKRCNaEzekgspzxATY')
		pubKeyHash2 = Address.ToPubKeyHash(version, address)
		self.assertEqual(pubKeyHash, pubKeyHash2)
