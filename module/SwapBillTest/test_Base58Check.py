from __future__ import print_function
import unittest
from SwapBill import Base58Check

class Test(unittest.TestCase):

	def test(self):
		data = b'\x00\x01\x02\x03'
		s = Base58Check.Encode(data)
		self.assertEqual(s, '13DV5niCGP')
		self.assertEqual(Base58Check.Decode(s), data)
		s = b'13DV5niCGP'.decode('ascii')
		self.assertEqual(Base58Check.Decode(s), data)

