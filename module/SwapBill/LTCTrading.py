from __future__ import print_function, division

class Exchange(object):
	pass

minimumExchangeLTC = 1000000
depositDivisor = 16

def LTCWithExchangeRate(exchangeRate, swapBillAmount):
	return swapBillAmount * exchangeRate // 0x100000000

def SatisfiesMinimumExchange(rate, amount):
	return LTCWithExchangeRate(rate, amount) >= minimumExchangeLTC

def Match(state):
	ltcBuys = state._LTCBuys
	ltcSells = state._LTCSells
	if ltcBuys.empty() or ltcSells.empty():
		return None
	if ltcBuys.currentBestExchangeRate() > ltcSells.currentBestExchangeRate():
		return None
	buyRate = ltcBuys.currentBestExchangeRate()
	buyExpiry = ltcBuys.currentBestExpiry()
	buyDetails = ltcBuys.popCurrentBest()
	assert SatisfiesMinimumExchange(buyRate, buyDetails.swapBillAmount) ## should not have been added to buys
	sellRate = ltcSells.currentBestExchangeRate()
	sellExpiry = ltcSells.currentBestExpiry()
	sellDetails = ltcSells.popCurrentBest()
	assert SatisfiesMinimumExchange(sellRate, sellDetails.swapBillAmount) ## should not have been added to sells
	appliedRate = (buyRate + sellRate) // 2
	exchange = Exchange()
	exchange.ltcReceiveAddress = buyDetails.ltcReceiveAddress
	exchange.buyerAddress = buyDetails.swapBillAddress
	exchange.sellerAddress = sellDetails.swapBillAddress
	if buyDetails.swapBillAmount > sellDetails.swapBillAmount:
		exchange.swapBillAmount = sellDetails.swapBillAmount
		exchange.swapBillDeposit = sellDetails.swapBillDeposit
		buyDetails.swapBillAmount -= exchange.swapBillAmount
		if SatisfiesMinimumExchange(buyRate, buyDetails.swapBillAmount):
			ltcBuys.addOffer(buyRate, buyExpiry, buyDetails)
		else:
			## small remaining buy offer is discarded
			## refund swapbill amount left in this buy offer
			state.addToBalance(buyDetails.swapBillAddress, buyDetails.swapBillAmount)
	else:
		exchange.swapBillAmount = buyDetails.swapBillAmount
		if buyDetails.swapBillAmount == sellDetails.swapBillAmount:
			exchange.swapBillDeposit = sellDetails.swapBillDeposit
		else:
			exchange.swapBillDeposit = sellDetails.swapBillDeposit * exchange.swapBillAmount // sellDetails.swapBillAmount
			sellDetails.swapBillAmount -= exchange.swapBillAmount
			sellDetails.swapBillDeposit -= exchange.swapBillDeposit
			if SatisfiesMinimumExchange(sellRate, sellDetails.swapBillAmount):
				ltcSells.addOffer(sellRate, sellExpiry, sellDetails)
			else:
				## small remaining sell offer is discarded
				## refund swapbill amount left in this buy offer
				state.addToBalance(sellDetails.swapBillDeposit, sellDetails.swapBillAmount)

	exchange.ltc = LTCWithExchangeRate(appliedRate, exchange.swapBillAmount)
	assert exchange.ltc >= minimumExchangeLTC ## should be guaranteed by buy and sell both satisfying this minimum requirement
	state.addPendingExchange(exchange)
