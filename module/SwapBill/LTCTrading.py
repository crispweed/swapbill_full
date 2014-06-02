from __future__ import print_function, division

class SplitWouldLeaveRemainderBelowMinimum(Exception):
	pass

class Exchange(object):
	pass

minimumExchangeLTC = 1000000
depositDivisor = 16

def LTCWithExchangeRate(exchangeRate, swapBillAmount):
	return swapBillAmount * exchangeRate // 0x100000000

def SatisfiesMinimumExchange(rate, amount):
	return LTCWithExchangeRate(rate, amount) >= minimumExchangeLTC

def Match(buyRate, buyDetails, sellRate, sellDetails):
	assert SatisfiesMinimumExchange(buyRate, buyDetails.swapBillAmount) ## otherwise should not have been added to buys
	assert SatisfiesMinimumExchange(sellRate, sellDetails.swapBillAmount) ## otherwise should not have been added to sells
	appliedRate = (buyRate + sellRate) // 2
	exchange = Exchange()
	exchange.ltcReceiveAddress = buyDetails.receivingAccount
	exchange.buyerAddress = buyDetails.refundAccount
	exchange.sellerReceivingAccount = sellDetails.receivingAccount
	outstandingBuy = None
	outstandingSell = None
	if buyDetails.swapBillAmount > sellDetails.swapBillAmount:
		exchange.swapBillAmount = sellDetails.swapBillAmount
		exchange.swapBillDeposit = sellDetails.swapBillDeposit
		buyDetails.swapBillAmount -= exchange.swapBillAmount
		outstandingBuy = buyDetails
	else:
		exchange.swapBillAmount = buyDetails.swapBillAmount
		if buyDetails.swapBillAmount == sellDetails.swapBillAmount:
			exchange.swapBillDeposit = sellDetails.swapBillDeposit
		else:
			exchange.swapBillDeposit = sellDetails.swapBillDeposit * exchange.swapBillAmount // sellDetails.swapBillAmount
			sellDetails.swapBillAmount -= exchange.swapBillAmount
			sellDetails.swapBillDeposit -= exchange.swapBillDeposit
			outstandingSell = sellDetails
	exchange.ltc = LTCWithExchangeRate(appliedRate, exchange.swapBillAmount)
	assert exchange.ltc >= minimumExchangeLTC ## should be guaranteed by buy and sell both satisfying this minimum requirement
	return exchange, outstandingBuy, outstandingSell

def Match2(buyRate, buyDetails, sellRate, sellDetails):
	assert sellDetails.ltcOffered >= minimumExchangeLTC ## otherwise should not have been added to sells
	ltcDesired = LTCWithExchangeRate(buyRate, buyDetails.swapBillOffered)
	assert ltcDesired >= minimumExchangeLTC ## otherwise should not have been added to buys

	appliedRate = (buyRate + sellRate) // 2

	ltcToBeExchanged = LTCWithExchangeRate(appliedRate, buyDetails.swapBillOffered)
	assert ltcToBeExchanged >= minimumExchangeLTC ## should be guaranteed by buy and sell both satisfying this minimum requirement

	exchange = Exchange()
	exchange.ltcReceiveAddress = buyDetails.receivingAccount
	exchange.buyerAddress = buyDetails.refundAccount
	exchange.sellerReceivingAccount = sellDetails.receivingAccount
	outstandingBuy = None
	outstandingSell = None

	if ltcToBeExchanged <= sellDetails.ltcOffered:
		# ltc buy offer is consumed completely
		exchange.swapBillAmount = buyDetails.swapBillOffered
		exchange.ltc = ltcToBeExchanged
		# check remainder for ltc sell, if any
		ltcRemaining = sellDetails.ltcOffered - ltcToBeExchanged
		if ltcRemaining == 0:
			exchange.swapBillDeposit = sellDetails.swapBillDeposit
		else:
			if ltcRemaining < minimumExchangeLTC:
				raise SplitWouldLeaveRemainderBelowMinimum()
			#print('ltcToBeExchanged:', ltcToBeExchanged)
			#print('sellDetails.ltcOffered:', sellDetails.ltcOffered)
			exchange.swapBillDeposit = sellDetails.swapBillDeposit * ltcToBeExchanged // sellDetails.ltcOffered
			sellDetails.ltcOffered = ltcRemaining
			sellDetails.swapBillDeposit -= exchange.swapBillDeposit
			outstandingSell = sellDetails
	else:
		# ltc sell offer is consumed completely
		exchange.ltc = sellDetails.ltcOffered
		exchange.swapBillDeposit = sellDetails.swapBillDeposit
		swapBillToBeExchanged =	buyDetails.swapBillOffered * sellDetails.ltcOffered // ltcToBeExchanged
		exchange.swapBillAmount = swapBillToBeExchanged
		swapBillRemaining = buyDetails.swapBillOffered - swapBillToBeExchanged
		if swapBillRemaining > 0:
			if LTCWithExchangeRate(buyRate, swapBillRemaining) < minimumExchangeLTC:
				raise SplitWouldLeaveRemainderBelowMinimum()
			buyDetails.swapBillAmount = swapBillRemaining
			outstandingBuy = buyDetails

	#if buyDetails.swapBillAmount > sellDetails.swapBillAmount:
		## sell is consumed completely
		#exchange.swapBillAmount = sellDetails.swapBillAmount
		#exchange.swapBillDeposit = sellDetails.swapBillDeposit
		#buyDetails.swapBillAmount -= exchange.swapBillAmount
		#outstandingBuy = buyDetails
	#else:
		## buy is consumed completely
		#exchange.swapBillAmount = buyDetails.swapBillAmount
		#if buyDetails.swapBillAmount == sellDetails.swapBillAmount:
			#exchange.swapBillDeposit = sellDetails.swapBillDeposit
		#else:
			#exchange.swapBillDeposit = sellDetails.swapBillDeposit * exchange.swapBillAmount // sellDetails.swapBillAmount
			#sellDetails.swapBillAmount -= exchange.swapBillAmount
			#sellDetails.swapBillDeposit -= exchange.swapBillDeposit
			#outstandingSell = sellDetails
	#exchange.ltc = LTCWithExchangeRate(appliedRate, exchange.swapBillAmount)
	#assert exchange.ltc >= minimumExchangeLTC ## should be guaranteed by buy and sell both satisfying this minimum requirement
	return exchange, outstandingBuy, outstandingSell


