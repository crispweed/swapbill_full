from __future__ import print_function, division

class RemainderIsBelowMinimumExchange(Exception):
	pass
class OfferIsBelowMinimumExchange(Exception):
	pass

class BuyOffer(object):
	def __init__(self, swapBillOffered, rate):
		if _ltcWithExchangeRate(rate, swapBillOffered) < _minimumExchangeLTC:
			raise OfferIsBelowMinimumExchange()
		self._swapBillOffered = swapBillOffered
		self.rate = rate
	def _subtractExchanged(self, exchangeSwapBill):
		assert exchangeSwapBill < self._swapBillOffered
		remainder = self._swapBillOffered - exchangeSwapBill
		if _ltcWithExchangeRate(self.rate, remainder) < _minimumExchangeLTC:
			# ** offer must not be modified at this point
			raise RemainderIsBelowMinimumExchange()
		self._swapBillOffered = remainder

class SellOffer(object):
	def __init__(self, swapBillDeposit, ltcOffered, rate):
		if ltcOffered < _minimumExchangeLTC:
			raise OfferIsBelowMinimumExchange()
		self._swapBillDeposit = swapBillDeposit
		self._ltcOffered = ltcOffered
		self.rate = rate
	def _subtractExchanged(self, exchangeLTC, exchangeSwapBillDeposit):
		assert exchangeLTC < self._ltcOffered
		assert exchangeSwapBillDeposit < self._swapBillDeposit # otherwise deposit could go to zero, minimum exchange amount should prevent this
		remainder = self._ltcOffered - exchangeLTC
		if remainder < _minimumExchangeLTC:
			# ** offer must not be modified at this point
			raise RemainderIsBelowMinimumExchange()
		self._ltcOffered = remainder
		self._swapBillDeposit -= exchangeSwapBillDeposit

class Exchange(object):
	pass

_minimumExchangeLTC = 1000000

def _ltcWithExchangeRate(exchangeRate, swapBillAmount):
	return swapBillAmount * exchangeRate // 0x100000000

def OffersMeetOrOverlap(buy, sell):
	return buy.rate <= sell.rate

def MatchOffers(buy, sell):
	assert OffersMeetOrOverlap(buy, sell)
	appliedRate = (buy.rate + sell.rate) // 2

	ltcToBeExchanged = _ltcWithExchangeRate(appliedRate, buy._swapBillOffered)
	assert ltcToBeExchanged >= _minimumExchangeLTC ## should be guaranteed by buy and sell both satisfying this minimum requirement

	exchange = Exchange()
	outstandingBuy = None
	outstandingSell = None

	if ltcToBeExchanged <= sell._ltcOffered:
		# ltc buy offer is consumed completely
		exchange.swapBillAmount = buy._swapBillOffered
		exchange.ltc = ltcToBeExchanged
		exchange.swapBillDeposit = sell._swapBillDeposit * ltcToBeExchanged // sell._ltcOffered
		if ltcToBeExchanged < sell._ltcOffered:
			sell._subtractExchanged(ltcToBeExchanged, exchange.swapBillDeposit)
			outstandingSell = sell
	else:
		# ltc sell offer is consumed completely
		exchange.ltc = sell._ltcOffered
		exchange.swapBillDeposit = sell._swapBillDeposit
		swapBillToBeExchanged =	buy._swapBillOffered * sell._ltcOffered // ltcToBeExchanged
		exchange.swapBillAmount = swapBillToBeExchanged
		if swapBillToBeExchanged < buy._swapBillOffered: # TODO check whether this comparison is actually required
			buy._subtractExchanged(swapBillToBeExchanged)
			outstandingBuy = buy

	return exchange, outstandingBuy, outstandingSell
