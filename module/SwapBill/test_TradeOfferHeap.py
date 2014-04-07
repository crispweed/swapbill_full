from __future__ import print_function
import unittest
from SwapBill import TradeOfferHeap

def DoTest(negateExchangeRates):
	rateSign = 1
	if negateExchangeRates:
		rateSign = -1
	h = TradeOfferHeap.Heap(100, negateExchangeRates)
	assert h.empty()
	h.addOffer('a', 10, 1000 * rateSign, 103)
	assert not h.empty()
	assert h.currentBestAmount() == 10
	assert h.currentBestExchangeRate() == 1000 * rateSign
	h.addOffer('b', 12, 999 * rateSign, 104)
	assert h.size() == 2
	assert h.currentBestAmount() == 12
	assert h.currentBestExchangeRate() == 999 * rateSign
	h.addOffer('c', 11, 1001 * rateSign, 105)
	assert h.size() == 3
	assert h.currentBestAmount() == 12
	assert h.currentBestExchangeRate() == 999 * rateSign
	h.advanceToBlock(101)
	assert h.size() == 3
	assert h.currentBestAmount() == 12
	assert h.currentBestExchangeRate() == 999 * rateSign
	h.advanceToBlock(103)
	assert h.size() == 2
	assert h.currentBestAmount() == 12
	assert h.currentBestExchangeRate() == 999 * rateSign
	h.advanceToBlock(104)
	assert h.size() == 1
	assert h.currentBestAmount() == 11
	assert h.currentBestExchangeRate() == 1001 * rateSign
	h.advanceToBlock(110)
	assert h.empty()
	h.addOffer('d', 20, 1000 * rateSign, 120)
	h.addOffer('e', 21, 999 * rateSign, 120)
	h.addOffer('f', 22, 1001 * rateSign, 121)
	h.addOffer('e', 31, 900 * rateSign, 120)
	assert h.size() == 4
	assert h.currentBestAmount() == 31
	assert h.currentBestExchangeRate() == 900 * rateSign
	h.popCurrentBest()
	assert h.size() == 3
	assert h.currentBestAmount() == 21
	assert h.currentBestExchangeRate() == 999 * rateSign
	h.partiallyUseCurrentBest(15)
	assert h.size() == 3
	assert h.currentBestAmount() == 6
	assert h.currentBestExchangeRate() == 999 * rateSign
	h.advanceToBlock(120)
	assert h.size() == 1
	assert h.currentBestAmount() == 22
	assert h.currentBestExchangeRate() == 1001 * rateSign

class Test(unittest.TestCase):
	def test(self):
		DoTest(False)
		DoTest(True)
