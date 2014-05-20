from __future__ import print_function
import unittest
from SwapBill import Base58Check
from SwapBill.Base58Check import CharacterNotPermittedInEncodedData, ChecksumDoesNotMatch

class Test(unittest.TestCase):

	def test(self):
		data = b'\x00\x01\x02\x03'
		s = Base58Check.Encode(data)
		self.assertEqual(s, '13DV5niCGP')
		self.assertEqual(Base58Check.Decode(s), data)
		s = b'13DV5niCGP'.decode('ascii')
		self.assertEqual(Base58Check.Decode(s), data)
		for i in (0,1,20,128,255):
			for j in (0,20,128,255):
				for k in (0,20,128,255):
					data = bytes([i, j, k])
					s = Base58Check.Encode(data)
					self.assertEqual(Base58Check.Decode(s), data)
		self.assertRaises(CharacterNotPermittedInEncodedData, Base58Check.Decode, '13DV5niCG$')
		self.assertRaises(ChecksumDoesNotMatch, Base58Check.Decode, '13DV5niCGQ')
