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
		self.assertEqual(TradeOffer._minimumExchangeLTC, 1*e(6))

	def test_offer_creation(self):
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 5000, 1503238553)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 2*e(6), 0x70000000)
		buy = TradeOffer.BuyOffer(2*e(6), 0x80000000)
		self.assertDictEqual(buy.__dict__, {'rate': 2147483648, '_swapBillOffered': 2000000})
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, 100, TradeOffer._minimumExchangeLTC-1, 0x70000000)
		sell = TradeOffer.SellOffer(100, TradeOffer._minimumExchangeLTC, 0x70000000)
		self.assertDictEqual(sell.__dict__, {'_swapBillDeposit': 100, 'rate': 1879048192, '_ltcOffered': 1000000})

	def test_meet_or_overlap(self):
		buy = TradeOffer.BuyOffer(2*e(6), 0x80000000)
		sell = TradeOffer.SellOffer(100, TradeOffer._minimumExchangeLTC, 0x70000000)
		self.assertFalse(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))
		sell = TradeOffer.SellOffer(100, TradeOffer._minimumExchangeLTC, 0x80000000)
		self.assertTrue(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))
		sell = TradeOffer.SellOffer(100, TradeOffer._minimumExchangeLTC, 0x90000000)
		self.assertTrue(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))

	def test_match(self):
		# test assertion about offers meeting or overlapping
		buy = TradeOffer.BuyOffer(2*e(7), 0x80000000)
		sell = TradeOffer.SellOffer(100, TradeOffer._minimumExchangeLTC, 0x70000000)
		self.assertRaises(AssertionError, TradeOffer.MatchOffers, buy=buy, sell=sell)
		# offer adjustments and match call
		sell = TradeOffer.SellOffer(100, 1*e(7), 0x80000000)
		exchange, outstandingBuy, outstandingSell = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# offers should match exactly
		self.assertIsNone(outstandingBuy)
		self.assertIsNone(outstandingSell)
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 100})
		# offer adjustments and next match call
		sell = TradeOffer.SellOffer(100, 6*e(6), 0x80000000)
		exchange, outstandingBuy, outstandingSell = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# sell should be consumed, and buy remainder left outstanding
		self.assertDictEqual(outstandingBuy.__dict__, {'rate': 0x80000000, '_swapBillOffered': 8*e(6)})
		self.assertIsNone(outstandingSell)
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 12*e(6), 'ltc': 6*e(6), 'swapBillDeposit': 100})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(2*e(7), 0x80000000)
		sell = TradeOffer.SellOffer(100, 3*e(7), 0x80000000)
		exchange, outstandingBuy, outstandingSell = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertIsNone(outstandingBuy)
		self.assertDictEqual(outstandingSell.__dict__, {'rate': 0x80000000, '_swapBillDeposit': 67, '_ltcOffered': 2*e(7)})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 33})
		# similar set of tests, but with different buy and sell rates
		# offer setup and match call
		buy = TradeOffer.BuyOffer(2*e(7), 0x70000000)
		sell = TradeOffer.SellOffer(100, 1*e(7), 0x90000000)
		exchange, outstandingBuy, outstandingSell = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# offers should match exactly (at applied rate)
		self.assertIsNone(outstandingBuy)
		self.assertIsNone(outstandingSell)
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 100})
		# offer adjustments and next match call
		sell = TradeOffer.SellOffer(100, 6*e(6), 0x90000000)
		exchange, outstandingBuy, outstandingSell = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# sell should be consumed, and buy remainder left outstanding
		self.assertDictEqual(outstandingBuy.__dict__, {'rate': 0x70000000, '_swapBillOffered': 8*e(6)})
		self.assertIsNone(outstandingSell)
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 12*e(6), 'ltc': 6*e(6), 'swapBillDeposit': 100})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(2*e(7), 0x70000000)
		sell = TradeOffer.SellOffer(100, 3*e(7), 0x90000000)
		exchange, outstandingBuy, outstandingSell = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertIsNone(outstandingBuy)
		self.assertDictEqual(outstandingSell.__dict__, {'rate': 0x90000000, '_swapBillDeposit': 67, '_ltcOffered': 2*e(7)})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 33})

	def test_match_remainder_too_small(self):
		buy = TradeOffer.BuyOffer(2*e(7)-1, 0x80000000)
		sell = TradeOffer.SellOffer(100, 1*e(7), 0x80000000)
		#self.assertRaises(RemainderIsBelowMinimumExchange, TradeOffer.MatchOffers, buy=buy, sell=sell)
		buy = TradeOffer.BuyOffer(2*e(7), 0x80000000)
		sell = TradeOffer.SellOffer(100, 1*e(7)-1, 0x80000000)
		self.assertRaises(RemainderIsBelowMinimumExchange, TradeOffer.MatchOffers, buy=buy, sell=sell)


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
