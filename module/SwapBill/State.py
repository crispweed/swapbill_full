from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, LTCTrading

class InvalidTransactionParameters(Exception):
	pass
class InvalidTransactionType(Exception):
	pass
class OutputsSpecDoesntMatch(Exception):
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
					self._addToBalance(buyDetails.refundAccount, buyDetails.swapBillAmount)
			if not sellDetails is None:
				if LTCTrading.SatisfiesMinimumExchange(sellRate, sellDetails.swapBillAmount):
					self._LTCSells.addOffer(sellRate, sellExpiry, sellDetails)
					continue
				else:
					## small remaining sell offer is discarded
					## refund swapbill amount left in this buy offer
					self._addToBalance(sellDetails.receivingAccount, sellDetails.swapBillDeposit)
			return # break out of while loop

	def _check_Burn(self, outputs, amount):
		if outputs != ('destination',):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount == 0:
			return False, 'zero amount not permitted'
		return True, ''
	def _apply_Burn(self, txID, amount):
		self._totalCreated += amount
		assert not (txID, 1) in self._balances
		self._balances[(txID, 1)] = amount

	## TODO - split transaction details into inputs and outputs?

	def _check_Pay(self, outputs, sourceAccount, amount, maxBlock):
		if outputs != ('change', 'destination'):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount == 0:
			return False, 'zero amount not permitted'
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		available = self._balances.get(sourceAccount, 0)
		if available < amount:
			return False, 'insufficient balance in source account (transaction ignored)'
		return True, ''
	def _apply_Pay(self, txID, sourceAccount, amount, maxBlock):
		available = self._balances.get(sourceAccount, 0)
		self._subtractFromBalance(sourceAccount, available)
		self._addToBalance((txID, 2), amount)
		if available > amount:
			self._addToBalance((txID, 1), available - amount)

	def _check_LTCBuyOffer(self, outputs, sourceAccount, swapBillOffered, exchangeRate, maxBlockOffset, receivingAddress, maxBlock):
		if outputs != ('change', 'refund'):
			raise OutputsSpecDoesntMatch()
		assert type(swapBillOffered) is int
		assert swapBillOffered >= 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(maxBlockOffset) is int
		assert maxBlockOffset >= 0
		if swapBillOffered == 0:
			return False, 'zero amount not permitted'
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		if self._balances.get(sourceAccount, 0) < swapBillOffered:
			return False, 'insufficient balance in source account (offer not posted)'
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillOffered):
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		return True, ''
	def _apply_LTCBuyOffer(self, txID, sourceAccount, swapBillOffered, exchangeRate, maxBlockOffset, receivingAddress, maxBlock):
		available = self._balances.get(sourceAccount, 0)
		self._subtractFromBalance(sourceAccount, available)
		if available > swapBillOffered:
			self._addToBalance((txID, 1), available - swapBillOffered)
		buyDetails = BuyDetails()
		buyDetails.swapBillAmount = swapBillOffered
		buyDetails.receivingAccount = receivingAddress
		buyDetails.refundAccount = (txID, 2) ## TODO - warn or fail if we try to spend this account before exchange completed
		expiry = maxBlock + maxBlockOffset
		if expiry > 0xffffffff:
			expiry = 0xffffffff
		self._LTCBuys.addOffer(exchangeRate, expiry, buyDetails)
		self._matchLTC()

	def _check_LTCSellOffer(self, outputs, sourceAccount, swapBillDesired, exchangeRate, maxBlockOffset, maxBlock):
		if outputs != ('change', 'receiving'):
			raise OutputsSpecDoesntMatch()
		assert type(swapBillDesired) is int
		assert swapBillDesired >= 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(maxBlockOffset) is int
		assert maxBlockOffset >= 0
		if swapBillDesired == 0:
			return False, 'zero amount not permitted'
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		swapBillDeposit = swapBillDesired // LTCTrading.depositDivisor
		if self._balances.get(sourceAccount, 0) < swapBillDeposit:
			return False, 'insufficient balance for deposit in source account (offer not posted)'
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillDesired):
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		return True, ''
	def _apply_LTCSellOffer(self, txID, sourceAccount, swapBillDesired, exchangeRate, maxBlockOffset, maxBlock):
		swapBillDeposit = swapBillDesired // LTCTrading.depositDivisor
		available = self._balances.get(sourceAccount, 0)
		self._subtractFromBalance(sourceAccount, available)
		if available > swapBillDeposit:
			self._addToBalance((txID, 1), available - swapBillDeposit)
		sellDetails = SellDetails()
		sellDetails.swapBillAmount = swapBillDesired
		sellDetails.swapBillDeposit = swapBillDeposit
		sellDetails.receivingAccount = (txID, 2) ## TODO - warn or fail if we try to spend this account before exchange completed
		expiry = maxBlock + maxBlockOffset
		if expiry > 0xffffffff:
			expiry = 0xffffffff
		self._LTCSells.addOffer(exchangeRate, expiry, sellDetails)
		self._matchLTC()

	def _check_LTCExchangeCompletion(self, outputs, pendingExchangeIndex, destinationAddress, destinationAmount):
		if outputs != ():
			raise OutputsSpecDoesntMatch()
		assert type(destinationAmount) is int
		if not pendingExchangeIndex in self._pendingExchanges:
			return False, 'no pending exchange with the specified index (transaction ignored)'
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		if destinationAddress != exchangeDetails.ltcReceiveAddress:
			return False, 'destination account does not match destination for pending exchange with the specified index (transaction ignored)'
		if destinationAmount < exchangeDetails.ltc:
			return False, 'amount is less than required payment amount (transaction ignored)'
		if destinationAmount > exchangeDetails.ltc:
			return True, 'amount is greater than required payment amount (exchange completes, but with ltc overpay)'
		return True, ''
	def _apply_LTCExchangeCompletion(self, txID, pendingExchangeIndex, destinationAddress, destinationAmount):
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		## the seller completed his side of the exchange, so credit them the buyers swapbill
		## and the seller is also refunded their deposit here
		self._addToBalance(exchangeDetails.sellerReceivingAccount, exchangeDetails.swapBillAmount + exchangeDetails.swapBillDeposit)
		self._pendingExchanges.pop(pendingExchangeIndex)

	def _check_ForwardToFutureNetworkVersion(self, outputs, sourceAccount, amount, maxBlock):
		if outputs != ('change',):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount == 0:
			return False, 'zero amount not permitted'
		if maxBlock < self._currentBlockIndex:
			return False, 'max block for transaction has been exceeded'
		available = self._balances.get(sourceAccount, 0)
		if available < amount:
			return False, 'insufficient balance in source account (transaction ignored)'
		return True, ''
	def _apply_ForwardToFutureNetworkVersion(self, txID, sourceAccount, amount, maxBlock):
		available = self._balances.get(sourceAccount, 0)
		self._subtractFromBalance(sourceAccount, available)
		self._totalForwarded += amount
		if available > amount:
			self._addToBalance((txID, 1), available - amount)

	def checkTransaction(self, transactionType, outputs, transactionDetails):
		methodName = '_check_' + transactionType
		try:
			method = getattr(self, methodName)
		except AttributeError as e:
			raise InvalidTransactionType(e)
		try:
			return method(outputs, **transactionDetails)
		except TypeError as e:
			raise InvalidTransactionParameters(e)
	def applyTransaction(self, transactionType, txID, outputs, transactionDetails):
		assert self.checkTransaction(transactionType, outputs, transactionDetails)[0] == True
		methodName = '_apply_' + transactionType
		method = getattr(self, methodName)
		method(txID, **transactionDetails)
		assert self.totalAccountedFor() == self._totalCreated

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


