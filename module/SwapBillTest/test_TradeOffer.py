from __future__ import print_function
import unittest
from SwapBill import TradeOffer
from SwapBill.TradeOffer import RemainderIsBelowMinimumExchange, OfferIsBelowMinimumExchange
from SwapBill.Amounts import e

def Over256(value):
	assert value > 0
	assert value < 256
	return 0x1000000 * value

class Test(unittest.TestCase):
	def test_internal(self):
		self.assertEqual(TradeOffer._ltcWithExchangeRate(0x80000000, 122), 61)
		self.assertEqual(TradeOffer._ltcWithExchangeRate(0x40000000, 100), 25)
		self.assertEqual(TradeOffer._ltcWithExchangeRate(0x40000000, 101), 25)
		## ltc calculation rounds down
		self.assertEqual(TradeOffer._ltcWithExchangeRate(0x100000000 // 10, 100000000), 100000000 // 10 - 1)
		## TODO: define maximum range for swapbill values, and test with these?

		## Matt's sell offer which didn't get added to state
		self.assertEqual(TradeOffer._ltcWithExchangeRate(1503238553, 5000), 1749)
		#self.assertFalse(TradeOffer.SatisfiesMinimumExchange(1503238553,  5000))

		self.assertEqual(TradeOffer._minimumExchangeLTC, 1*e(6))
		#self.assertTrue(TradeOffer.SatisfiesMinimumExchange(0x80000000,  20 * milliSatoshi))
		#self.assertFalse(TradeOffer.SatisfiesMinimumExchange(0x70000000,  20 * milliSatoshi))

	def test_offer_creation(self):
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 5000, 1503238553)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 2*e(6), 0x70000000)
		buy = TradeOffer.BuyOffer(2*e(6), 0x80000000)
		self.assertDictEqual(buy.__dict__, {'rate': 2147483648, '_swapBillOffered': 2000000})
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, 100, TradeOffer._minimumExchangeLTC-1, 0x70000000)
		sell = TradeOffer.SellOffer(100, TradeOffer._minimumExchangeLTC, 0x70000000)
		self.assertDictEqual(sell.__dict__, {'_swapBillDeposit': 100, 'rate': 1879048192, '_ltcOffered': 1000000})

	#def test_match(self):
		##def Match2(buyRate, buyDetails, sellRate, sellDetails):
		#buyDetails = MockDetails()
		#buyDetails.swapBillOffered = 1*e(8)
		#buyDetails.receivingAccount = "buyReceive"
		#buyDetails.refundAccount = "buyRefund"
		#sellDetails = MockDetails()
		#sellDetails.ltcOffered = 1*e(8)
		#sellDetails.swapBillDeposit = 1*e(6)
		#sellDetails.receivingAccount = "sellReceive"
		#buyRate = Over256(128)
		#sellRate = Over256(128)
		#exchange, outstandingBuy, outstandingSell = LTCTrading.Match2(buyRate, buyDetails, sellRate, sellDetails)
		#if outstandingBuy is not None: print('buy:', outstandingBuy.__dict__)
		#if outstandingSell is not None: print('sell:', outstandingSell.__dict__)
		#print('exchange:', exchange.__dict__)
