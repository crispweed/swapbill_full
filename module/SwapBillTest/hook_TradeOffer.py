from __future__ import print_function
from SwapBill import TradeOffer

def MatchOffersWrapper(originalFunction):
	def Wrapper(minimumHostExchangeAmount, buy, sell):
		swapBillOffered = buy._swapBillOffered
		swapBillDeposit = sell._swapBillDeposit
		ltcOffered = sell._ltcOffered
		exchange = originalFunction(minimumHostExchangeAmount=minimumHostExchangeAmount, buy=buy, sell=sell)
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

