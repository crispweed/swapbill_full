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
	def ltcEquivalent(self):
		return swapBillToLTC_RoundedUp(self.rate, self._swapBillOffered)

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
		return ltcToSwapBill_RoundedUp(self.rate, self._ltcOffered)

class Exchange(object):
	pass

def _ltcWithExchangeRate(exchangeRate, swapBillAmount):
	return swapBillAmount * exchangeRate // Amounts.percentDivisor

def OffersMeetOrOverlap(buy, sell):
	return buy.rate <= sell.rate

def _tryMatch(buy, sell, swapBill, ltc):
	assert ltc >= Constraints.minimumExchangeLTC
	assert swapBill >= Constraints.minimumSwapBillBalance
	swapBillRemaining = buy._swapBillOffered - swapBill
	assert swapBillRemaining >= 0
	if swapBillRemaining > 0 and swapBillRemaining < MinimumBuyOfferWithRate(buy.rate):
		# ** offers must not be modified at this point
		raise OfferIsBelowMinimumExchange()
	ltcRemaining = sell._ltcOffered - ltc
	assert ltcRemaining >= 0
	if ltcRemaining > 0 and ltcRemaining < MinimumSellOfferWithRate(sell.rate):
		# ** offers must not be modified at this point
		raise OfferIsBelowMinimumExchange()
	# going ahead with exchange, ok to go ahead and subtract the exchanged amounts from the offers
	exchange = Exchange()
	exchange.swapBillAmount = swapBill
	exchange.ltc = ltc
	exchange.swapBillDeposit = sell._swapBillDeposit * ltc // sell._ltcOffered
	buy._swapBillOffered = swapBillRemaining
	sell._ltcOffered = ltcRemaining
	sell._swapBillDeposit -= exchange.swapBillDeposit
	return exchange

def MatchOffers(buy, sell):
	assert OffersMeetOrOverlap(buy, sell)
	appliedRate = (buy.rate + sell.rate) // 2

	ltc, rounded = _swapBillToLTC(appliedRate, buy._swapBillOffered)
	assert ltc >= Constraints.minimumExchangeLTC # should be guaranteed by buy and sell both satisfying this minimum requirement

	if rounded and ltc + 1 == sell._ltcOffered:
		# we round up in this case to ensure that posting matching offers based on the displayed equivalent value results in an exact match
		ltc += 1

	if ltc <= sell._ltcOffered:
		try:
			return _tryMatch(buy, sell, buy._swapBillOffered, ltc)
		except OfferIsBelowMinimumExchange:
			pass

	swapBill, rounded = _ltcToSwapBill(appliedRate, sell._ltcOffered)
	assert swapBill >= Constraints.minimumSwapBillBalance # should be guaranteed by buy and sell both satisfying this minimum requirement

	if swapBill <= buy._swapBillOffered:
		try:
			return _tryMatch(buy, sell, swapBill, sell._ltcOffered)
		except OfferIsBelowMinimumExchange:
			pass

	raise OfferIsBelowMinimumExchange()
