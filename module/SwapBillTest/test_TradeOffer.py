from __future__ import print_function
import unittest
from SwapBill import TradeOffer, Amounts
from SwapBill.TradeOffer import OfferIsBelowMinimumExchange, OfferIsBelowMinimumExchange
from SwapBill.HardCodedProtocolConstraints import Constraints
from SwapBill.Amounts import e

def MatchOffersWrapper(originalFunction):
	def Wrapper(buy, sell):
		swapBillOffered = buy._swapBillOffered
		swapBillDeposit = sell._swapBillDeposit
		ltcOffered = sell._ltcOffered
		exchange = originalFunction(buy=buy, sell=sell)
		swapBillOffered -= exchange.swapBillAmount
		swapBillDeposit -= exchange.swapBillDeposit
		ltcOffered -= exchange.ltc
		swapBillOffered -= buy._swapBillOffered
		swapBillDeposit -= sell._swapBillDeposit
		ltcOffered -= sell._ltcOffered
		assert swapBillOffered == 0
		assert swapBillDeposit == 0
		assert ltcOffered == 0
		return exchange
	return Wrapper
TradeOffer.MatchOffers = MatchOffersWrapper(TradeOffer.MatchOffers)

class Test(unittest.TestCase):
	def MinimumSellOffer(self, rate):
		ltcOffered = TradeOffer.MinimumSellOfferWithRate(rate)
		deposit = TradeOffer.DepositRequiredForLTCSell(rate, ltcOffered)
		return TradeOffer.SellOffer(deposit, ltcOffered, rate)
	def SellOffer(self, rate, ltcOffered):
		deposit = TradeOffer.DepositRequiredForLTCSell(rate, ltcOffered)
		return TradeOffer.SellOffer(deposit, ltcOffered, rate)

	def test_offer_requirements(self):
		# (based on current protocol constraints)
		self.assertEqual(TradeOffer.MinimumBuyOfferWithRate(500000000), Constraints.minimumSwapBillBalance)
		self.assertEqual(TradeOffer.MinimumSellOfferWithRate(500000000), Constraints.minimumSwapBillBalance//2)
		self.assertEqual(TradeOffer.MinimumBuyOfferWithRate(62500000), Constraints.minimumExchangeLTC*16)
		self.assertEqual(TradeOffer.MinimumSellOfferWithRate(62500000), Constraints.minimumExchangeLTC)
		# deposit is rounded up
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(500000000, 1*e(7)), 1*e(7)*2//Constraints.depositDivisor)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(250000000, 1*e(7)), 1*e(7)*4//Constraints.depositDivisor)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(62500000, 1*e(7)), 1*e(7)*16//Constraints.depositDivisor)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(500000000, 1*e(7)+1), 1*e(7)*2//Constraints.depositDivisor+1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(250000000, 1*e(7)+1), 1*e(7)*4//Constraints.depositDivisor+1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(500000000, 1*e(7)-1), 1*e(7)*2//Constraints.depositDivisor)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(250000000, 1*e(7)-1), 1*e(7)*4//Constraints.depositDivisor)
		# (based on current protocol constraints)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(rate=500000000, ltcOffered=0), 0)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(rate=500000000, ltcOffered=1), 1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(rate=500000000, ltcOffered=7), 1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(rate=500000000, ltcOffered=8), 1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(rate=500000000, ltcOffered=9), 2)

	def test_internal(self):
		self.assertEqual(TradeOffer._ltcWithExchangeRate(500000000, 122), 61)
		self.assertEqual(TradeOffer._ltcWithExchangeRate(250000000, 100), 25)
		self.assertEqual(TradeOffer._ltcWithExchangeRate(250000000, 101), 25)
		# ltc calculation rounds down
		self.assertEqual(TradeOffer._ltcWithExchangeRate(Amounts.percentDivisor // 3, 100000000), 100000000 // 3)
		## TODO: define maximum range for swapbill values, and test with these?

	def test_offer_creation(self):
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 5000, 375000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 2*e(6), 437500000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 2*e(6), 500000000) # swapbill offered below minimum balance
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, 1*e(7)-1, 500000000)
		buy = TradeOffer.BuyOffer(1*e(7), 500000000)
		self.assertDictEqual(buy.__dict__, {'rate': 500000000, '_swapBillOffered': 1*e(7)})
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, 100, Constraints.minimumExchangeLTC-1, 437500000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, 2*e(6)//16, 1*e(6), 500000000) # swapbill equivalent below minimum balance
		rate = 437500000
		ltcOffered = TradeOffer.MinimumSellOfferWithRate(rate)
		deposit = TradeOffer.DepositRequiredForLTCSell(rate=rate, ltcOffered=ltcOffered)
		sell = TradeOffer.SellOffer(deposit,ltcOffered, rate)
		self.assertDictEqual(sell.__dict__, {'_swapBillDeposit': deposit, 'rate': rate, '_ltcOffered': ltcOffered})
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, deposit, ltcOffered-1, rate)

	def test_meet_or_overlap(self):
		buy = TradeOffer.BuyOffer(1*e(7), 500000000)
		sell = self.MinimumSellOffer(250000000)
		self.assertFalse(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))
		sell = self.MinimumSellOffer(500000000)
		self.assertTrue(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))
		sell = self.MinimumSellOffer(562500000)
		self.assertTrue(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))

	def test_match(self):
		# test assertion about offers meeting or overlapping
		buy = TradeOffer.BuyOffer(2*e(7), 500000000)
		sell = self.MinimumSellOffer(250000000)
		self.assertRaises(AssertionError, TradeOffer.MatchOffers, buy=buy, sell=sell)
		# offer adjustments and match call
		buy = TradeOffer.BuyOffer(2*e(7), 500000000)
		sell = self.SellOffer(rate=500000000, ltcOffered=1*e(7))
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# offers should match exactly
		self.assertTrue(buy.hasBeenConsumed())
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 2*e(7)//16})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(2*e(7), 500000000)
		sell = TradeOffer.SellOffer(12*e(6)//16, 6*e(6), 500000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, buy=buy, sell=sell)
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(22*e(6), 500000000)
		sell = TradeOffer.SellOffer(12*e(6)//16, 6*e(6), 500000000)
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# sell should be consumed, and buy remainder left outstanding
		self.assertDictEqual(buy.__dict__, {'rate': 500000000, '_swapBillOffered': 1*e(7)})
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 12*e(6), 'ltc': 6*e(6), 'swapBillDeposit': 12*e(6)//16})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(2*e(7), 500000000)
		sell = TradeOffer.SellOffer(6*e(7)//16, 3*e(7), 500000000)
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertTrue(buy.hasBeenConsumed())
		self.assertDictEqual(sell.__dict__, {'rate': 500000000, '_swapBillDeposit': 4*e(7)//16, '_ltcOffered': 2*e(7)})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 2*e(7)//16})
		# similar set of tests, but with different buy and sell rates
		# offer setup and match call
		buy = TradeOffer.BuyOffer(2*e(7), 437500000)
		sell = TradeOffer.SellOffer(1111112, 1*e(7), 562500000)
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# offers should match exactly (at applied rate)
		self.assertTrue(buy.hasBeenConsumed())
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 1111112})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(2*e(7), 437500000)
		sell = TradeOffer.SellOffer(666667, 6*e(6), 562500000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, buy=buy, sell=sell)
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(22*e(6), 437500000)
		sell = TradeOffer.SellOffer(666667, 6*e(6), 562500000)
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# sell should be consumed, and buy remainder left outstanding
		self.assertDictEqual(buy.__dict__, {'rate': 437500000, '_swapBillOffered': 1*e(7)})
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 12*e(6), 'ltc': 6*e(6), 'swapBillDeposit': 666667})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(2*e(7), 437500000)
		sell = TradeOffer.SellOffer(3333334, 3*e(7), 562500000)
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertTrue(buy.hasBeenConsumed())
		self.assertDictEqual(sell.__dict__, {'rate': 562500000, '_swapBillDeposit': 2222223, '_ltcOffered': 2*e(7)})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 1111111})

	def test_match_remainder_too_small(self):
		buy = TradeOffer.BuyOffer(2*e(7)-1, 500000000)
		sell = TradeOffer.SellOffer(2*e(7)//16, 1*e(7), 500000000)
		# the ltc equivalent for this buy offer now gets rounded up
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		self.assertTrue(buy.hasBeenConsumed())
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7)-1, 'ltc': 1*e(7), 'swapBillDeposit': 2*e(7)//16})
		buy = TradeOffer.BuyOffer(2*e(7)-2, 500000000)
		sell = TradeOffer.SellOffer(2*e(7)//16, 1*e(7), 500000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, buy=buy, sell=sell)
		buy = TradeOffer.BuyOffer(2*e(7), 500000000)
		sell = TradeOffer.SellOffer((2*e(7)-2)//16+1, 1*e(7)-1, 500000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, buy=buy, sell=sell)

	def test_non_simple_overlap(self):
		buyRate = 250000000
		buy = TradeOffer.BuyOffer(1*e(7), buyRate)
		sellRate = 0x45 * 3906250
		ltcOffered = 2*e(7) * sellRate // Amounts.percentDivisor
		deposit = 2*e(7) // 16
		sell = TradeOffer.SellOffer(deposit, ltcOffered, sellRate)
		appliedRate = (buyRate + sellRate) // 2
		ltcInExchange = 1*e(7) * appliedRate // Amounts.percentDivisor
		assert ltcInExchange < ltcOffered // 2
		self.assertEqual(ltcInExchange, 2597656)
		n = ltcInExchange
		d = ltcOffered
		exchangeFractionAsFloat = float(n)/d
		assert exchangeFractionAsFloat < 0.482 and exchangeFractionAsFloat > 0.481
		depositInExchange = deposit * n // d
		exchange = TradeOffer.MatchOffers(buy=buy, sell=sell)
		self.assertTrue(buy.hasBeenConsumed())
		self.assertDictEqual(sell.__dict__, {'rate': sellRate, '_swapBillDeposit': deposit-depositInExchange, '_ltcOffered': ltcOffered-ltcInExchange})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 1*e(7), 'ltc': ltcInExchange, 'swapBillDeposit': depositInExchange})

	def test_attempt_break_deposit_invariant(self):
		# set up sell which is split exactly in half by partially matching buy
		# the idea being that one half of the split has to lose the rounding up unit
		buy = TradeOffer.BuyOffer(1*e(7)+2, 500000000)
		deposit = TradeOffer.DepositRequiredForLTCSell(rate=500000000, ltcOffered=1*e(7)+2)
		sell = TradeOffer.SellOffer(deposit, 1*e(7)+2, 500000000)
		# attempted to break the invariant for deposit always being the exact required deposit, by division rounded up
		# but it turns out the invariant holds here, because *the exchange* loses the rounding up unit, not the outstanding sell
		exchange= TradeOffer.MatchOffers(buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertTrue(buy.hasBeenConsumed)
		self.assertDictEqual(sell.__dict__, {'_swapBillDeposit': 625001, 'rate': 500000000, '_ltcOffered': 5000001})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 10000002, 'ltc': 5000001, 'swapBillDeposit': 625000})

