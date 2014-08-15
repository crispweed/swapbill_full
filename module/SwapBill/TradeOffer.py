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

def MinimumBuyOfferWithRate(minimumHostExchangeAmount, rate):
	swapBillForMinLTC = ltcToSwapBill_RoundedUp(rate, minimumHostExchangeAmount)
	return max(swapBillForMinLTC, Constraints.minimumSwapBillBalance)

def MinimumSellOfferWithRate(minimumHostExchangeAmount, rate):
	ltcForMinSwapBill = swapBillToLTC_RoundedUp(rate, Constraints.minimumSwapBillBalance)
	return max(ltcForMinSwapBill, minimumHostExchangeAmount)

def DepositRequiredForLTCSell(rate, ltcOffered):
	swapBill = ltcToSwapBill_RoundedUp(rate, ltcOffered)
	deposit = swapBill // Constraints.depositDivisor
	if deposit * Constraints.depositDivisor != swapBill:
		deposit += 1
	return deposit

class BuyOffer(object):
	def __init__(self, minimumHostExchangeAmount, swapBillOffered, rate):
		if swapBillOffered < MinimumBuyOfferWithRate(minimumHostExchangeAmount, rate):
			raise OfferIsBelowMinimumExchange()
		self._swapBillOffered = swapBillOffered
		self.rate = rate
	def hasBeenConsumed(self):
		return self._swapBillOffered == 0
	def ltcEquivalent(self):
		return swapBillToLTC_RoundedUp(self.rate, self._swapBillOffered)
	def _canSubtract(self, minimumHostExchangeAmount, swapBill):
		if swapBill > self._swapBillOffered:
			return False
		if swapBill == self._swapBillOffered:
			return True
		return self._swapBillOffered - swapBill >= MinimumBuyOfferWithRate(minimumHostExchangeAmount, self.rate)

class SellOffer(object):
	def __init__(self, minimumHostExchangeAmount, swapBillDeposit, ltcOffered, rate):
		if ltcOffered < MinimumSellOfferWithRate(minimumHostExchangeAmount, rate):
			raise OfferIsBelowMinimumExchange()
		self._swapBillDeposit = swapBillDeposit
		self._ltcOffered = ltcOffered
		self.rate = rate
	def hasBeenConsumed(self):
		return self._ltcOffered == 0
	def swapBillEquivalent(self):
		return ltcToSwapBill_RoundedUp(self.rate, self._ltcOffered)
	def _canSubtract(self, minimumHostExchangeAmount, ltc):
		if ltc > self._ltcOffered:
			return False
		if ltc == self._ltcOffered:
			return True
		return self._ltcOffered - ltc >= MinimumSellOfferWithRate(minimumHostExchangeAmount, self.rate)

class Exchange(object):
	pass

def OffersMeetOrOverlap(buy, sell):
	return buy.rate <= sell.rate

def MatchOffers(minimumHostExchangeAmount, buy, sell):
	assert OffersMeetOrOverlap(buy, sell)
	appliedRate = (buy.rate + sell.rate) // 2

	ltc, rounded = _swapBillToLTC(appliedRate, buy._swapBillOffered)
	assert ltc >= minimumHostExchangeAmount # should be guaranteed by buy and sell both satisfying this minimum requirement

	candidates = [(buy._swapBillOffered, ltc)]
	if rounded:
		# added ensure that posting matching offers based on the displayed other currency equivalent results in a match
		candidates.append((buy._swapBillOffered, ltc + 1))

	swapBill, rounded = _ltcToSwapBill(appliedRate, sell._ltcOffered)
	candidates.append((swapBill, sell._ltcOffered))

	ltc = sell._ltcOffered - MinimumSellOfferWithRate(minimumHostExchangeAmount, sell.rate)
	if ltc > 0:
		swapBill, rounded = _ltcToSwapBill(appliedRate, ltc)
		candidates.append((swapBill, ltc))

	swapBill = buy._swapBillOffered - MinimumBuyOfferWithRate(minimumHostExchangeAmount, buy.rate)
	if swapBill > 0:
		ltc, rounded = _swapBillToLTC(appliedRate, swapBill)
		candidates.append((swapBill, ltc))

	for swapBill, ltc in candidates:
		if swapBill < Constraints.minimumSwapBillBalance:
			continue
		if ltc < minimumHostExchangeAmount:
			continue
		if buy._canSubtract(minimumHostExchangeAmount, swapBill) and sell._canSubtract(minimumHostExchangeAmount, ltc):
			exchange = Exchange()
			exchange.swapBillAmount = swapBill
			exchange.ltc = ltc
			exchange.swapBillDeposit = sell._swapBillDeposit * ltc // sell._ltcOffered
			buy._swapBillOffered -= swapBill
			sell._ltcOffered -= ltc
			sell._swapBillDeposit -= exchange.swapBillDeposit
			assert (sell._ltcOffered == 0) == (sell._swapBillDeposit == 0)
			return exchange

	raise OfferIsBelowMinimumExchange()
