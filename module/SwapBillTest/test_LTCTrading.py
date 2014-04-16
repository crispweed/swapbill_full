from __future__ import print_function
import unittest
from SwapBill import LTCTrading

class Test(unittest.TestCase):
	def test(self):
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x80000000, 122), 61)
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x40000000, 100), 25)
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x40000000, 101), 25)
		## ltc calculation rounds down
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x100000000 // 10, 100000000), 100000000 // 10 - 1)
		## TODO: define maximum range for swapbill values, and test with these?

		## Matt's sell offer which didn't get added to state
		self.assertEqual(LTCTrading.LTCWithExchangeRate(1503238553, 5000), 1749)
		self.assertFalse(LTCTrading.SatisfiesMinimumExchange(1503238553,  5000))

		milliSatoshi = 100000
		self.assertEqual(LTCTrading.minimumExchangeLTC, 10 * milliSatoshi)
		self.assertTrue(LTCTrading.SatisfiesMinimumExchange(0x80000000,  20 * milliSatoshi))
		self.assertFalse(LTCTrading.SatisfiesMinimumExchange(0x70000000,  20 * milliSatoshi))

