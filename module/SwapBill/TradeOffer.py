from __future__ import print_function, division
from SwapBill.HardCodedProtocolConstraints import Constraints

class OfferIsBelowMinimumExchange(Exception):
	pass

def MinimumBuyOfferWithRate(rate):
	swapBillForMinLTC = Constraints.minimumExchangeLTC * 0x100000000 // rate
	if _ltcWithExchangeRate(rate, swapBillForMinLTC) < Constraints.minimumExchangeLTC:
		swapBillForMinLTC += 1
	assert _ltcWithExchangeRate(rate, swapBillForMinLTC) >= Constraints.minimumExchangeLTC
	return max(swapBillForMinLTC, Constraints.minimumSwapBillBalance)

def MinimumSellOfferWithRate(rate):
	ltcForMinSwapBill = _ltcWithExchangeRate(rate, Constraints.minimumSwapBillBalance)
	return max(ltcForMinSwapBill, Constraints.minimumExchangeLTC)

def DepositRequiredForLTCSell(exchangeRate, ltcOffered):
	swapBillAmount = ltcOffered * 0x100000000 // exchangeRate
	deposit = swapBillAmount // Constraints.depositDivisor
	if deposit * Constraints.depositDivisor != swapBillAmount:
		deposit += 1
	return deposit

class BuyOffer(object):
	def __init__(self, swapBillOffered, rate):
		if swapBillOffered < MinimumBuyOfferWithRate(rate):
			raise OfferIsBelowMinimumExchange()
		self._swapBillOffered = swapBillOffered
		self.rate = rate

class SellOffer(object):
	def __init__(self, swapBillDeposit, ltcOffered, rate):
		if ltcOffered < MinimumSellOfferWithRate(rate):
			raise OfferIsBelowMinimumExchange()
		self._swapBillDeposit = swapBillDeposit
		self._ltcOffered = ltcOffered
		self.rate = rate

class Exchange(object):
	pass

def _ltcWithExchangeRate(exchangeRate, swapBillAmount):
	return swapBillAmount * exchangeRate // 0x100000000

def OffersMeetOrOverlap(buy, sell):
	return buy.rate <= sell.rate

def MatchOffers(buy, sell):
	assert OffersMeetOrOverlap(buy, sell)
	appliedRate = (buy.rate + sell.rate) // 2

	ltcToBeExchanged = _ltcWithExchangeRate(appliedRate, buy._swapBillOffered)
	assert ltcToBeExchanged >= Constraints.minimumExchangeLTC # should be guaranteed by buy and sell both satisfying this minimum requirement

	exchange = Exchange()
	outstandingBuy = None
	outstandingSell = None

	if ltcToBeExchanged <= sell._ltcOffered:
		# ltc buy offer is consumed completely
		exchange.swapBillAmount = buy._swapBillOffered
		exchange.ltc = ltcToBeExchanged
		exchange.swapBillDeposit = sell._swapBillDeposit * ltcToBeExchanged // sell._ltcOffered
		if ltcToBeExchanged < sell._ltcOffered:
			outstandingSell = SellOffer(swapBillDeposit=sell._swapBillDeposit - exchange.swapBillDeposit, ltcOffered=sell._ltcOffered - ltcToBeExchanged, rate=sell.rate)
	else:
		# ltc sell offer is consumed completely
		exchange.ltc = sell._ltcOffered
		exchange.swapBillDeposit = sell._swapBillDeposit
		swapBillToBeExchanged =	buy._swapBillOffered * sell._ltcOffered // ltcToBeExchanged
		assert swapBillToBeExchanged >= Constraints.minimumSwapBillBalance # should be guaranteed by the buy and sell offer minimum constraints
		exchange.swapBillAmount = swapBillToBeExchanged
		if swapBillToBeExchanged != buy._swapBillOffered: # TODO check whether this comparison is actually required
			outstandingBuy = BuyOffer(swapBillOffered=buy._swapBillOffered - swapBillToBeExchanged, rate=buy.rate)

	return exchange, outstandingBuy, outstandingSell
