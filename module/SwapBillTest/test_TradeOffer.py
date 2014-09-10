from __future__ import print_function
import unittest
from SwapBillTest import hook_TradeOffer
from SwapBill import TradeOffer, Amounts
from SwapBill.TradeOffer import OfferIsBelowMinimumExchange
from SwapBill.Amounts import e

defaultParams = {
'minimumHostExchangeAmount':1000000,
'minimumSwapBillBalance':10000000,
'depositDivisor':16
}

class Test(unittest.TestCase):
	def MinimumSellOffer(self, rate, protocolParams=defaultParams):
		hostCoinOffered = TradeOffer.MinimumSellOfferWithRate(protocolParams, rate=rate)
		deposit = TradeOffer.DepositRequiredForLTCSell(protocolParams, rate, hostCoinOffered)
		return TradeOffer.SellOffer(protocolParams, deposit, hostCoinOffered, rate)
	def SellOffer(self, rate, hostCoinOffered, protocolParams=defaultParams):
		deposit = TradeOffer.DepositRequiredForLTCSell(protocolParams, rate=rate, hostCoinOffered=hostCoinOffered)
		return TradeOffer.SellOffer(protocolParams, swapBillDeposit=deposit, hostCoinOffered=hostCoinOffered, rate=rate)

	def test_offer_requirements(self):
		# (based on current protocol constraints)
		self.assertEqual(TradeOffer.MinimumBuyOfferWithRate(defaultParams, rate=500000000), defaultParams['minimumSwapBillBalance'])
		self.assertEqual(TradeOffer.MinimumSellOfferWithRate(defaultParams, rate=500000000), defaultParams['minimumSwapBillBalance']//2)
		self.assertEqual(TradeOffer.MinimumBuyOfferWithRate(defaultParams, rate=62500000), defaultParams['minimumHostExchangeAmount']*16)
		self.assertEqual(TradeOffer.MinimumSellOfferWithRate(defaultParams, rate=62500000), defaultParams['minimumHostExchangeAmount'])
		# deposit is rounded up
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 500000000, 1*e(7)), 1*e(7)*2//defaultParams['depositDivisor'])
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 250000000, 1*e(7)), 1*e(7)*4//defaultParams['depositDivisor'])
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 62500000, 1*e(7)), 1*e(7)*16//defaultParams['depositDivisor'])
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 500000000, 1*e(7)+1), 1*e(7)*2//defaultParams['depositDivisor']+1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 250000000, 1*e(7)+1), 1*e(7)*4//defaultParams['depositDivisor']+1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 500000000, 1*e(7)-1), 1*e(7)*2//defaultParams['depositDivisor'])
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, 250000000, 1*e(7)-1), 1*e(7)*4//defaultParams['depositDivisor'])
		# (based on current protocol constraints)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=500000000, hostCoinOffered=0), 0)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=500000000, hostCoinOffered=1), 1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=500000000, hostCoinOffered=7), 1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=500000000, hostCoinOffered=8), 1)
		self.assertEqual(TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=500000000, hostCoinOffered=9), 2)

	def test_internal(self):
		self.assertEqual(TradeOffer.swapBillToLTC_RoundedUp(500000000, 122), 61)
		self.assertEqual(TradeOffer.swapBillToLTC_RoundedUp(250000000, 100), 25)
		self.assertEqual(TradeOffer.swapBillToLTC_RoundedUp(250000000, 101), 26)
		self.assertEqual(TradeOffer.swapBillToLTC_RoundedUp(Amounts.percentDivisor // 3, 100000000), 100000000 // 3 + 1)

	def test_offer_creation(self):
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, defaultParams, 5000, 375000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, defaultParams, 2*e(6), 437500000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, defaultParams, 2*e(6), 500000000) # swapbill offered below minimum balance
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.BuyOffer, defaultParams, 1*e(7)-1, 500000000)
		buy = TradeOffer.BuyOffer(defaultParams, 1*e(7), 500000000)
		self.assertDictEqual(buy.__dict__, {'rate': 500000000, '_swapBillOffered': 1*e(7)})
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, defaultParams, 100, defaultParams['minimumHostExchangeAmount']-1, 437500000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, defaultParams, 2*e(6)//16, 1*e(6), 500000000) # swapbill equivalent below minimum balance
		rate = 437500000
		hostCoinOffered = TradeOffer.MinimumSellOfferWithRate(defaultParams, rate)
		deposit = TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=rate, hostCoinOffered=hostCoinOffered)
		sell = TradeOffer.SellOffer(defaultParams, deposit, hostCoinOffered, rate)
		self.assertDictEqual(sell.__dict__, {'_swapBillDeposit': deposit, 'rate': rate, '_hostCoinOffered': hostCoinOffered})
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.SellOffer, defaultParams, deposit, hostCoinOffered-1, rate)

	def test_meet_or_overlap(self):
		buy = TradeOffer.BuyOffer(defaultParams, 1*e(7), 500000000)
		sell = self.MinimumSellOffer(250000000)
		self.assertFalse(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))
		sell = self.MinimumSellOffer(500000000)
		self.assertTrue(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))
		sell = self.MinimumSellOffer(562500000)
		self.assertTrue(TradeOffer.OffersMeetOrOverlap(buy=buy, sell=sell))

	def test_match(self):
		# test assertion about offers meeting or overlapping
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 500000000)
		sell = self.MinimumSellOffer(250000000)
		self.assertRaises(AssertionError, TradeOffer.MatchOffers, defaultParams, buy=buy, sell=sell)
		# offer adjustments and match call
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 500000000)
		sell = self.SellOffer(rate=500000000, hostCoinOffered=1*e(7))
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# offers should match exactly
		self.assertTrue(buy.hasBeenConsumed())
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 2*e(7)//16})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 500000000)
		sell = TradeOffer.SellOffer(defaultParams, 12*e(6)//16, 6*e(6), 500000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, defaultParams, buy=buy, sell=sell)
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(defaultParams, 22*e(6), 500000000)
		sell = TradeOffer.SellOffer(defaultParams, 12*e(6)//16, 6*e(6), 500000000)
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# sell should be consumed, and buy remainder left outstanding
		self.assertDictEqual(buy.__dict__, {'rate': 500000000, '_swapBillOffered': 1*e(7)})
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 12*e(6), 'ltc': 6*e(6), 'swapBillDeposit': 12*e(6)//16})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 500000000)
		sell = TradeOffer.SellOffer(defaultParams, 6*e(7)//16, 3*e(7), 500000000)
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertTrue(buy.hasBeenConsumed())
		self.assertDictEqual(sell.__dict__, {'rate': 500000000, '_swapBillDeposit': 4*e(7)//16, '_hostCoinOffered': 2*e(7)})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 2*e(7)//16})
		# similar set of tests, but with different buy and sell rates
		# offer setup and match call
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 437500000)
		sell = TradeOffer.SellOffer(defaultParams, 1111112, 1*e(7), 562500000)
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# offers should match exactly (at applied rate)
		self.assertTrue(buy.hasBeenConsumed())
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 1111112})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 437500000)
		sell = TradeOffer.SellOffer(defaultParams, 666667, 6*e(6), 562500000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, defaultParams, buy=buy, sell=sell)
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(defaultParams, 22*e(6), 437500000)
		sell = TradeOffer.SellOffer(defaultParams, 666667, 6*e(6), 562500000)
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# sell should be consumed, and buy remainder left outstanding
		self.assertDictEqual(buy.__dict__, {'rate': 437500000, '_swapBillOffered': 1*e(7)})
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 12*e(6), 'ltc': 6*e(6), 'swapBillDeposit': 666667})
		# offer adjustments and next match call
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 437500000)
		sell = TradeOffer.SellOffer(defaultParams, 3333334, 3*e(7), 562500000)
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertTrue(buy.hasBeenConsumed())
		self.assertDictEqual(sell.__dict__, {'rate': 562500000, '_swapBillDeposit': 2222223, '_hostCoinOffered': 2*e(7)})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7), 'ltc': 1*e(7), 'swapBillDeposit': 1111111})

	def test_match_remainder_too_small(self):
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7)-1, 500000000)
		sell = TradeOffer.SellOffer(defaultParams, 2*e(7)//16, 1*e(7), 500000000)
		# the ltc equivalent for this buy offer now gets rounded up
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		self.assertTrue(buy.hasBeenConsumed())
		self.assertTrue(sell.hasBeenConsumed())
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 2*e(7)-1, 'ltc': 1*e(7), 'swapBillDeposit': 2*e(7)//16})
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7)-2, 500000000)
		sell = TradeOffer.SellOffer(defaultParams, 2*e(7)//16, 1*e(7), 500000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, defaultParams, buy=buy, sell=sell)
		buy = TradeOffer.BuyOffer(defaultParams, 2*e(7), 500000000)
		sell = TradeOffer.SellOffer(defaultParams, (2*e(7)-2)//16+1, 1*e(7)-1, 500000000)
		self.assertRaises(OfferIsBelowMinimumExchange, TradeOffer.MatchOffers, defaultParams, buy=buy, sell=sell)

	def test_non_simple_overlap(self):
		buyRate = 250000000
		buy = TradeOffer.BuyOffer(defaultParams, 1*e(7), buyRate)
		sellRate = 0x45 * 3906250
		hostCoinOffered = 2*e(7) * sellRate // Amounts.percentDivisor
		deposit = 2*e(7) // 16
		sell = TradeOffer.SellOffer(defaultParams, deposit, hostCoinOffered, sellRate)
		appliedRate = (buyRate + sellRate) // 2
		ltcInExchange = 1*e(7) * appliedRate // Amounts.percentDivisor
		assert ltcInExchange < hostCoinOffered // 2
		self.assertEqual(ltcInExchange, 2597656)
		n = ltcInExchange
		d = hostCoinOffered
		exchangeFractionAsFloat = float(n)/d
		assert exchangeFractionAsFloat < 0.482 and exchangeFractionAsFloat > 0.481
		depositInExchange = deposit * n // d
		exchange = TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		self.assertTrue(buy.hasBeenConsumed())
		self.assertDictEqual(sell.__dict__, {'rate': sellRate, '_swapBillDeposit': deposit-depositInExchange, '_hostCoinOffered': hostCoinOffered-ltcInExchange})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 1*e(7), 'ltc': ltcInExchange, 'swapBillDeposit': depositInExchange})

	def test_attempt_break_deposit_invariant(self):
		# set up sell which is split exactly in half by partially matching buy
		# the idea being that one half of the split has to lose the rounding up unit
		buy = TradeOffer.BuyOffer(defaultParams, 1*e(7)+2, 500000000)
		deposit = TradeOffer.DepositRequiredForLTCSell(defaultParams, rate=500000000, hostCoinOffered=1*e(7)+2)
		sell = TradeOffer.SellOffer(defaultParams, deposit, 1*e(7)+2, 500000000)
		# attempted to break the invariant for deposit always being the exact required deposit, by division rounded up
		# but it turns out the invariant holds here, because *the exchange* loses the rounding up unit, not the outstanding sell
		exchange= TradeOffer.MatchOffers(defaultParams, buy=buy, sell=sell)
		# buy should be consumed, and sell remainder left outstanding
		self.assertTrue(buy.hasBeenConsumed)
		self.assertDictEqual(sell.__dict__, {'_swapBillDeposit': 625001, 'rate': 500000000, '_hostCoinOffered': 5000001})
		self.assertDictEqual(exchange.__dict__, {'swapBillAmount': 10000002, 'ltc': 5000001, 'swapBillDeposit': 625000})

