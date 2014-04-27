from __future__ import print_function
import unittest
from SwapBill import Address

class Test(unittest.TestCase):
	def CheckRoundTrip(self, pubKeyHash, version=b'\x6f'):
		version = b'\x6f'
		address = Address.FromPubKeyHash(version, pubKeyHash)
		pubKeyHash2 = Address.ToPubKeyHash(version, address)
		self.assertEqual(pubKeyHash, pubKeyHash2)		
		
	def test(self):
		version = b'\x6f'
		# note old control address suffix here
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

	def test_bad_address(self):
		version = b'\x6f'
		self.assertRaisesRegexp(Address.BadAddress, 'Not a valid base58 character', Address.ToPubKeyHash, version, 'm$5DS9xE4PBBhB5eHKRCNaEzekgspzxATY')
		self.assertRaisesRegexp(Address.BadAddress, 'incorrect version byte', Address.ToPubKeyHash, version, 'm')
		self.assertRaisesRegexp(Address.BadAddress, 'checksum mismatch', Address.ToPubKeyHash, version, 'mh5DS9xE4PBBhB6eHKRCNaEzekgspzxATY')
		self.assertRaisesRegexp(Address.BadAddress, 'incorrect version byte', Address.ToPubKeyHash, version, 'mh5DS9xE4PBBhB6eHKRCNaEzekgspzxAT')

	def test_round_trips(self):
		self.CheckRoundTrip(b'\x00' * 20)
		self.CheckRoundTrip(b'\x01' * 20)
		self.CheckRoundTrip(b'\x80' * 20)
		self.CheckRoundTrip(b'\xff' * 20)
		self.CheckRoundTrip(b'\x00' * 20, version=b'\x00')
		self.CheckRoundTrip(b'\x01' * 20, version=b'\x00')
		self.CheckRoundTrip(b'\x80' * 20, version=b'\x00')
		self.CheckRoundTrip(b'\xff' * 20, version=b'\x00')
		self.CheckRoundTrip(b'\x00' * 20, version=b'\xff')
		self.CheckRoundTrip(b'\x01' * 20, version=b'\xff')
		self.CheckRoundTrip(b'\x80' * 20, version=b'\xff')
		self.CheckRoundTrip(b'\xff' * 20, version=b'\xff')
