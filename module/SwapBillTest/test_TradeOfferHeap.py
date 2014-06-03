from __future__ import print_function
import unittest
from SwapBill import TradeOfferHeap

class MockOffer(object):
	pass

class Test(unittest.TestCase):
	def addOffer(self, rate, expiry, s):
		offer = MockOffer()
		if self.negateExchangeRates:
			offer.rate = -rate
		else:
			offer.rate = rate
		offer.expiry = expiry
		offer.s = s
		self.h.addOffer(offer)

	def currentBestExchangeRate(self):
		if self.negateExchangeRates:
			return self.h.currentBestExchangeRate() * -1
		return self.h.currentBestExchangeRate()

	def doTests(self):
		h = TradeOfferHeap.Heap(100, self.negateExchangeRates)
		self.h = h
		self.assertTrue(h.empty())
		self.addOffer(1000, 103, 'offer1')
		self.assertFalse(h.empty())
		self.assertEqual(h.peekCurrentBest().s, 'offer1')
		self.assertEqual(self.currentBestExchangeRate(), 1000)
		self.addOffer(999, 104, 'offer2')
		self.assertEqual(h.size(), 2)
		self.assertEqual(h.peekCurrentBest().s, 'offer2')
		self.assertEqual(self.currentBestExchangeRate(), 999)
		self.addOffer(1001, 105, 'offer3')
		self.assertEqual(h.size(), 3)
		self.assertEqual(h.peekCurrentBest().s, 'offer2')
		self.assertEqual(self.currentBestExchangeRate(), 999)
		expired = h.advanceToBlock(101)
		self.assertEqual(expired, [])
		self.assertEqual(h.size(), 3)
		self.assertEqual(h.peekCurrentBest().s, 'offer2')
		self.assertEqual(self.currentBestExchangeRate(), 999)
		expired = h.advanceToBlock(104)
		self.assertEqual(len(expired), 1)
		self.assertEqual(expired[0].s, 'offer1')
		self.assertEqual(h.size(), 2)
		self.assertEqual(h.peekCurrentBest().s, 'offer2')
		self.assertEqual(self.currentBestExchangeRate(), 999)
		expired = h.advanceToBlock(105)
		self.assertEqual(len(expired), 1)
		self.assertEqual(expired[0].s, 'offer2')
		self.assertEqual(h.size(), 1)
		self.assertEqual(h.peekCurrentBest().s, 'offer3')
		self.assertEqual(self.currentBestExchangeRate(), 1001)
		expired = h.advanceToBlock(111)
		self.assertEqual(len(expired), 1)
		self.assertEqual(expired[0].s, 'offer3')
		self.assertTrue(h.empty())
		self.addOffer(1000, 120, 'offer4')
		self.addOffer(999, 120, 'offer5')
		self.addOffer(1001, 121, 'offer6')
		self.addOffer(900, 120, 'offer7')
		self.assertEqual(h.size(), 4)
		self.assertEqual(h.peekCurrentBest().s, 'offer7')
		self.assertEqual(self.currentBestExchangeRate(), 900)
		popped = h.popCurrentBest()
		self.assertEqual(popped.s, 'offer7')
		self.assertEqual(h.size(), 3)
		self.assertEqual(h.peekCurrentBest().s, 'offer5')
		self.assertEqual(self.currentBestExchangeRate(), 999)
		expired = h.advanceToBlock(121)
		self.assertEqual(len(expired), 2)
		self.assertEqual(sorted([expired[0].s, expired[1].s]), ['offer4', 'offer5'])
		self.assertEqual(h.size(), 1)
		self.assertEqual(h.peekCurrentBest().s, 'offer6')
		self.assertEqual(self.currentBestExchangeRate(), 1001)

	def test(self):
		self.negateExchangeRates = False
		self.doTests()
		self.negateExchangeRates = True
		self.doTests()
