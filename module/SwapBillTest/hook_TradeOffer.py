from __future__ import print_function
from SwapBill import TradeOffer

def MatchOffersWrapper(originalFunction):
	def Wrapper(protocolParams, buy, sell):
		swapBillOffered = buy._swapBillOffered
		swapBillDeposit = sell._swapBillDeposit
		hostCoinOffered = sell._hostCoinOffered
		exchange = originalFunction(protocolParams=protocolParams, buy=buy, sell=sell)
		swapBillOffered -= exchange.swapBillAmount
		swapBillDeposit -= exchange.swapBillDeposit
		hostCoinOffered -= exchange.ltc
		swapBillOffered -= buy._swapBillOffered
		swapBillDeposit -= sell._swapBillDeposit
		hostCoinOffered -= sell._hostCoinOffered
		assert swapBillOffered == 0
		assert swapBillDeposit == 0
		assert hostCoinOffered == 0
		return exchange
	return Wrapper
TradeOffer.MatchOffers = MatchOffersWrapper(TradeOffer.MatchOffers)

