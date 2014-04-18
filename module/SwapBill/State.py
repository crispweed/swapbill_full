from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, LTCTrading

class InvalidTransactionParameters(Exception):
	pass
class InvalidTransactionType(Exception):
	pass

class BuyDetails(object):
	pass
class SellDetails(object):
	pass

class State(object):
	def __init__(self, startBlockIndex, startBlockHash):
		## state is initialised at the start of the block with startBlockIndex
		self._startBlockHash = startBlockHash
		self._currentBlockIndex = startBlockIndex
		self._balances = {}
		self._totalCreated = 0
		self._totalForwarded = 0
		self._LTCBuys = TradeOfferHeap.Heap(startBlockIndex, False) # lower exchange rate is better offer
		self._LTCSells = TradeOfferHeap.Heap(startBlockIndex, True) # higher exchange rate is better offer
		self._nextExchangeIndex = 0
		self._pendingExchanges = {}

	def startBlockMatches(self, startBlockHash):
		return self._startBlockHash == startBlockHash

	def advanceToNextBlock(self):
		self._LTCBuys.advanceToNextBlock()
		self._LTCSells.advanceToNextBlock()
		## TODO currently iterates through all pending exchanges each block added
		## (sort out scaling issues with this!)
		toDelete = []
		for key in self._pendingExchanges:
			exchange = self._pendingExchanges[key]
			if exchange.expiry == self._currentBlockIndex:
				#print("pending exchange expired")
				## refund buyers funds locked up in the exchange, plus sellers deposit (as penalty for failing to make exchange)
				self._addToBalance(exchange.buyerAddress, exchange.swapBillAmount + exchange.swapBillDeposit)
				toDelete.append(key)
		for key in toDelete:
			self._pendingExchanges.pop(key)
		self._currentBlockIndex += 1


	def _addToBalance(self, address, amount):
		assert amount >= 0
		if amount == 0:
			return
		if address in self._balances:
			self._balances[address] += amount
		else:
			self._balances[address] = amount

	def _subtractFromBalance(self, address, amount):
		if amount == 0:
			return
		assert address in self._balances and self._balances[address] >= amount
		if amount == self._balances[address]:
			self._balances.pop(address)
		else:
			self._balances[address] -= amount

	def _matchLTC(self):
		while True:
			if self._LTCBuys.empty() or self._LTCSells.empty():
				return
			if self._LTCBuys.currentBestExchangeRate() > self._LTCSells.currentBestExchangeRate():
				return
			buyRate = self._LTCBuys.currentBestExchangeRate()
			buyExpiry = self._LTCBuys.currentBestExpiry()
			buyDetails = self._LTCBuys.popCurrentBest()
			sellRate = self._LTCSells.currentBestExchangeRate()
			sellExpiry = self._LTCSells.currentBestExpiry()
			sellDetails = self._LTCSells.popCurrentBest()
			exchange, buyDetails, sellDetails = LTCTrading.Match(buyRate, buyExpiry, buyDetails, sellRate, sellExpiry, sellDetails)
			exchange.expiry = self._currentBlockIndex + 50
			key = self._nextExchangeIndex
			self._nextExchangeIndex += 1
			self._pendingExchanges[key] = exchange
			if not buyDetails is None:
				if LTCTrading.SatisfiesMinimumExchange(buyRate, buyDetails.swapBillAmount):
					self._LTCBuys.addOffer(buyRate, buyExpiry, buyDetails)
					continue # may need to match against a second offer
				else:
					## small remaining buy offer is discarded
					## refund swapbill amount left in this buy offer
					self._addToBalance(buyDetails.swapBillAddress, buyDetails.swapBillAmount)
			if not sellDetails is None:
				if LTCTrading.SatisfiesMinimumExchange(sellRate, sellDetails.swapBillAmount):
					self._LTCSells.addOffer(sellRate, sellExpiry, sellDetails)
					continue
				else:
					## small remaining sell offer is discarded
					## refund swapbill amount left in this buy offer
					self._addToBalance(sellDetails.swapBillAddress, sellDetails.swapBillDeposit)
			return # break out of while loop

	def checkWouldApplySuccessfully_Burn(self, amount, destinationAccount):
		assert type(amount) is int
		assert amount > 0
		return True, ''
	def apply_Burn(self, amount, destinationAccount):
		self._totalCreated += amount
		if destinationAccount in self._balances:
			self._balances[destinationAccount] += amount
		else:
			self._balances[destinationAccount] = amount

	def checkWouldApplySuccessfully_Transfer(self, sourceAccount, amount, destinationAccount, maxBlock):
		assert type(amount) is int
		assert amount > 0
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		available = self._balances.get(sourceAccount, 0)
		if available >= amount:
			return True, ''
		if available > 0:
			return False, 'insufficient balance in source account (transfer capped)'
		return False, 'source account balance is 0'
	def apply_Transfer(self, sourceAccount, amount, destinationAccount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return
		available = self._balances.get(sourceAccount, 0)
		if amount > available:
			amount = available
		self._subtractFromBalance(sourceAccount, amount)
		self._addToBalance(destinationAccount, amount)

	def checkWouldApplySuccessfully_Pay(self, sourceAccount, changeAccount, amount, destinationAccount, maxBlock):
		assert type(amount) is int
		assert amount > 0
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		available = self._balances.get(sourceAccount, 0)
		if available < amount:
			return False, 'insufficient balance in source account (transaction ignored)'
		return True, ''
	def apply_Pay(self, sourceAccount, changeAccount, amount, destinationAccount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return
		available = self._balances.get(sourceAccount, 0)
		if available < amount:
			return
		self._subtractFromBalance(sourceAccount, available)
		self._addToBalance(destinationAccount, amount)
		if available > amount:
			self._addToBalance(changeAccount, available - amount)

	def checkWouldApplySuccessfully_LTCBuyOffer(self, sourceAccount, changeAccount, swapBillOffered, exchangeRate, expiry, receivingAccount, refundAccount, maxBlock):
		assert type(swapBillOffered) is int
		assert swapBillOffered > 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(expiry) is int
		assert expiry > 0
		if self._balances.get(sourceAccount, 0) < swapBillOffered:
			return False, 'insufficient balance in source account (offer not posted)'
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillOffered):
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		return True, ''
	def apply_LTCBuyOffer(self, sourceAccount, changeAccount, swapBillOffered, exchangeRate, expiry, receivingAccount, refundAccount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return
		available = self._balances.get(sourceAccount, 0)
		if available < swapBillOffered:
			return
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillOffered):
			return
		self._subtractFromBalance(sourceAccount, available)
		if available > swapBillOffered:
			self._addToBalance(changeAccount, available - swapBillOffered)
		buyDetails = BuyDetails()
		buyDetails.swapBillAddress = sourceAccount
		buyDetails.swapBillAmount = swapBillOffered
		buyDetails.ltcReceiveAddress = receivingAccount
		buyDetails.refundAccount = refundAccount
		self._LTCBuys.addOffer(exchangeRate, expiry, buyDetails)
		self._matchLTC()

	def checkWouldApplySuccessfully_LTCSellOffer(self, sourceAccount, changeAccount, swapBillDesired, exchangeRate, expiry, receivingAccount, maxBlock):
		assert type(swapBillDesired) is int
		assert swapBillDesired > 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(expiry) is int
		assert expiry > 0
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		swapBillDeposit = swapBillDesired // LTCTrading.depositDivisor
		if self._balances.get(sourceAccount, 0) < swapBillDeposit:
			return False, 'insufficient balance for deposit in source account (offer not posted)'
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillDesired):
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		return True, ''
	def apply_LTCSellOffer(self, sourceAccount, changeAccount, swapBillDesired, exchangeRate, expiry, receivingAccount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return
		swapBillDeposit = swapBillDesired // LTCTrading.depositDivisor
		available = self._balances.get(sourceAccount, 0)
		if available < swapBillDeposit:
			return
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillDesired):
			return
		self._subtractFromBalance(sourceAccount, available)
		if available > swapBillDeposit:
			self._addToBalance(changeAccount, available - swapBillDeposit)
		sellDetails = SellDetails()
		sellDetails.swapBillAddress = sourceAccount
		sellDetails.swapBillAmount = swapBillDesired
		sellDetails.swapBillDeposit = swapBillDeposit
		sellDetails.refundAccount = receivingAccount
		self._LTCSells.addOffer(exchangeRate, expiry, sellDetails)
		self._matchLTC()

	def checkWouldApplySuccessfully_LTCExchangeCompletion(self, pendingExchangeIndex, destinationAccount, destinationAmount):
		assert type(destinationAmount) is int
		if not pendingExchangeIndex in self._pendingExchanges:
			return False, 'no pending exchange with the specified index (transaction ignored)'
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		if destinationAccount != exchangeDetails.ltcReceiveAddress:
			return False, 'destination account does not match destination for pending exchange with the specified index (transaction ignored)'
		if destinationAmount < exchangeDetails.ltc:
			return False, 'amount is less than required payment amount (transaction ignored)'
		if destinationAmount > exchangeDetails.ltc:
			return False, 'amount is greater than required payment amount (exchange completes, but with ltc overpay)'
		## the seller completed his side of the exchange, so credit them the buyers swapbill
		## and the seller is also refunded their deposit here
		## TODO don't reuse seller address, need a separate address for this completion credit!
		return True, ''
	def apply_LTCExchangeCompletion(self, pendingExchangeIndex, destinationAccount, destinationAmount):
		if not pendingExchangeIndex in self._pendingExchanges:
			return
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		if destinationAccount != exchangeDetails.ltcReceiveAddress:
			return
		if destinationAmount < exchangeDetails.ltc:
			return
		## the seller completed his side of the exchange, so credit them the buyers swapbill
		## and the seller is also refunded their deposit here
		## TODO don't reuse seller address, need a separate address for this completion credit!
		self._addToBalance(exchangeDetails.sellerAddress, exchangeDetails.swapBillAmount + exchangeDetails.swapBillDeposit)
		self._pendingExchanges.pop(pendingExchangeIndex)

	def checkWouldApplySuccessfully_ForwardToFutureNetworkVersion(self, sourceAccount, amount, maxBlock):
		assert type(amount) is int
		assert amount > 0
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		available = self._balances.get(sourceAccount, 0)
		if available >= amount:
			return True, ''
		if available > 0:
			return False, 'insufficient balance in source account (amount capped)'
		return False, 'source account balance is 0'
	def apply_ForwardToFutureNetworkVersion(self, sourceAccount, amount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return
		available = self._balances.get(sourceAccount, 0)
		if amount > available:
			amount = available
		self._subtractFromBalance(sourceAccount, amount)
		self._totalForwarded += amount

	def checkTransactionWouldApplySuccessfully(self, transactionType, transactionDetails):
		methodName = 'checkWouldApplySuccessfully_' + transactionType
		try:
			method = getattr(self, methodName)
		except AttributeError as e:
			raise InvalidTransactionType(e)
		try:
			return method(**transactionDetails)
		except TypeError as e:
			raise InvalidTransactionParameters(e)
	def applyTransaction(self, transactionType, transactionDetails):
		#assert self.checkTransactionWouldApplySuccessfully(transactionType, transactionDetails) == (True, '')
		## note that transfer currently needs to be able to complete 'unsuccessfully', if amount is capped
		## following is then still used for exceptions and assertions
		self.checkTransactionWouldApplySuccessfully(transactionType, transactionDetails)
		methodName = 'apply_' + transactionType
		method = getattr(self, methodName)
		return method(**transactionDetails)

	def totalAccountedFor(self):
		result = 0
		#print()
		for key in self._balances:
			result += self._balances[key]
		#print('balances:  ', result)
		for exchangeRate, details in self._LTCBuys.getSortedExchangeRateAndDetails():
			result += details.swapBillAmount
		#print('+buys:     ', result)
		for exchangeRate, details in self._LTCSells.getSortedExchangeRateAndDetails():
			result += details.swapBillDeposit
		#print('+sells:    ', result)
		for key in self._pendingExchanges:
			exchange = self._pendingExchanges[key]
			#print(exchange.__dict__)
			result += exchange.swapBillAmount
			result += exchange.swapBillDeposit
		#print('+exchanges:', result)
		result += self._totalForwarded
		return result


