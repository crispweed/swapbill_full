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

def GetSwapBillAmountRequiredToBackSell(exchangeRate, ltcOffered):
	swapBillAmount = ltcOffered * 0x100000000 // exchangeRate
	if _ltcWithExchangeRate(rate, swapBillAmount) < ltcOffered:
		swapBillAmount += 1
	assert _ltcWithExchangeRate(rate, swapBillAmount) >= ltcOffered.minimumExchangeLTC
	return swapBillAmount

class BuyOffer(object):
	def __init__(self, swapBillOffered, rate):
		if swapBillOffered < MinimumBuyOfferWithRate(rate):
			raise OfferIsBelowMinimumExchange()
		self._swapBillOffered = swapBillOffered
		self.rate = rate
	def hasBeenConsumed(self):
		return self._swapBillOffered == 0

class SellOffer(object):
	def __init__(self, swapBillDeposit, ltcOffered, rate):
		if ltcOffered < MinimumSellOfferWithRate(rate):
			raise OfferIsBelowMinimumExchange()
		self._swapBillDeposit = swapBillDeposit
		self._ltcOffered = ltcOffered
		self.rate = rate
	def hasBeenConsumed(self):
		return self._ltcOffered == 0

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

	if ltcToBeExchanged <= sell._ltcOffered:
		# ltc buy offer is consumed completely
		exchange.swapBillAmount = buy._swapBillOffered
		exchange.ltc = ltcToBeExchanged
		exchange.swapBillDeposit = sell._swapBillDeposit * ltcToBeExchanged // sell._ltcOffered
		ltcRemaining = sell._ltcOffered - ltcToBeExchanged
		if ltcRemaining > 0 and ltcRemaining < MinimumSellOfferWithRate(sell.rate):
			# ** offers must not be modified at this point
			raise OfferIsBelowMinimumExchange()
		buy._swapBillOffered = 0
		sell._ltcOffered = ltcRemaining
		sell._swapBillDeposit -= exchange.swapBillDeposit
	else:
		# ltc sell offer is consumed completely
		exchange.ltc = sell._ltcOffered
		exchange.swapBillDeposit = sell._swapBillDeposit
		swapBillToBeExchanged =	buy._swapBillOffered * sell._ltcOffered // ltcToBeExchanged
		assert swapBillToBeExchanged >= Constraints.minimumSwapBillBalance # should be guaranteed by the buy and sell offer minimum constraints
		exchange.swapBillAmount = swapBillToBeExchanged
		swapBillRemaining = buy._swapBillOffered - swapBillToBeExchanged
		if swapBillRemaining > 0 and swapBillRemaining < MinimumBuyOfferWithRate(buy.rate):
			# ** offers must not be modified at this point
			raise OfferIsBelowMinimumExchange()
		sell._ltcOffered = 0
		sell._swapBillDeposit = 0
		buy._swapBillOffered = swapBillRemaining

	return exchange
