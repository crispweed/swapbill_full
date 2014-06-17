from __future__ import print_function, division
from SwapBill import Amounts
from SwapBill.HardCodedProtocolConstraints import Constraints

class OfferIsBelowMinimumExchange(Exception):
	pass

def _ltcToSwapBill(rate, ltc):
	swapBill = ltc * Amounts.percentDivisor // rate
	rounded = (swapBill * rate != ltc * Amounts.percentDivisor)
	if rounded:
		# the actual exact converted amount is in between swapbill and swapbill + 1 in this case
		assert (swapBill + 1) * rate > ltc * Amounts.percentDivisor
	return swapBill, rounded
def _swapBillToLTC(rate, swapBill):
	ltc = swapBill * rate // Amounts.percentDivisor
	rounded = (ltc * Amounts.percentDivisor != swapBill * rate)
	if rounded:
		# the actual exact converted amount is in between ltc and ltc + 1 in this case
		assert (ltc + 1) * Amounts.percentDivisor > swapBill * rate
	return ltc, rounded

def ltcToSwapBill_RoundedUp(rate, ltc):
	swapBill, rounded = _ltcToSwapBill(rate, ltc)
	if rounded:
		swapBill += 1
	return swapBill
def swapBillToLTC_RoundedUp(rate, swapBill):
	ltc, rounded = _swapBillToLTC(rate, swapBill)
	if rounded:
		ltc += 1
	return ltc


def MinimumBuyOfferWithRate(rate):
	swapBillForMinLTC = ltcToSwapBill_RoundedUp(rate, Constraints.minimumExchangeLTC)
	return max(swapBillForMinLTC, Constraints.minimumSwapBillBalance)

def MinimumSellOfferWithRate(rate):
	ltcForMinSwapBill = swapBillToLTC_RoundedUp(rate, Constraints.minimumSwapBillBalance)
	return max(ltcForMinSwapBill, Constraints.minimumExchangeLTC)

def DepositRequiredForLTCSell(rate, ltcOffered):
	swapBill = ltcToSwapBill_RoundedUp(rate, ltcOffered)
	deposit = swapBill // Constraints.depositDivisor
	if deposit * Constraints.depositDivisor != swapBill:
		deposit += 1
	return deposit


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
	def swapBillEquivalent(self):
		return self._swapBillOffered * Amounts.percentDivisor // self.rate

class Exchange(object):
	pass

def _ltcWithExchangeRate(exchangeRate, swapBillAmount):
	return swapBillAmount * exchangeRate // Amounts.percentDivisor

def OffersMeetOrOverlap(buy, sell):
	return buy.rate <= sell.rate

def MatchOffers(buy, sell):
	assert OffersMeetOrOverlap(buy, sell)
	appliedRate = (buy.rate + sell.rate) // 2

	ltcToBeExchanged, rounded = _swapBillToLTC(appliedRate, buy._swapBillOffered)
	assert ltcToBeExchanged >= Constraints.minimumExchangeLTC # should be guaranteed by buy and sell both satisfying this minimum requirement

	if rounded and ltcToBeExchanged + 1 == sell._ltcOffered:
		# we round up in this case to ensure that posting matching offers based on the displayed equivalent value actually does match
		ltcToBeExchanged += 1

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
