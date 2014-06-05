from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, TradeOffer, Balances
from SwapBill.HardCodedProtocolConstraints import Constraints
from SwapBill.Amounts import e

class InvalidTransactionParameters(Exception):
	pass
class InvalidTransactionType(Exception):
	pass
class OutputsSpecDoesntMatch(Exception):
	pass

class LTCSellBacker(object):
	def __init__(self, amount, maximumTransactionAmount, ltcReceiveAddress):
		self.amount = amount
		self.maximumTransactionAmount = maximumTransactionAmount
		self.ltcReceiveAddress = ltcReceiveAddress

class State(object):
	def __init__(self, startBlockIndex, startBlockHash):
		## state is initialised at the start of the block with startBlockIndex
		self._startBlockHash = startBlockHash
		self._currentBlockIndex = startBlockIndex
		self._balances = Balances.Balances()
		self._tradeOfferChangeCounts = {}
		self._totalCreated = 0
		self._totalForwarded = 0
		self._LTCBuys = TradeOfferHeap.Heap(startBlockIndex, False) # lower exchange rate is better offer
		self._LTCSells = TradeOfferHeap.Heap(startBlockIndex, True) # higher exchange rate is better offer
		self._nextExchangeIndex = 0
		self._pendingExchanges = {}
		#self._nextBackerIndex = 0
		#self._ltcSellBackers = {}

	def _addFirstTradeRef(self, account):
		self._balances.addFirstReference(account)
		self._tradeOfferChangeCounts[account] = 0
	def _addTradeRef(self, account):
		self._balances.addReference(account)
	def _removeTradeRef(self, account):
		self._balances.removeReference(account)
		if not self._balances.isReferenced(account):
			self._tradeOfferChangeCounts.pop(account)

	def getSpendableAmount(self, account):
		if self._balances.isReferenced(account):
			return 0
		return self._balances.balanceFor(account)

	def startBlockMatches(self, startBlockHash):
		return self._startBlockHash == startBlockHash

	def advanceToNextBlock(self):
		expired = self._LTCBuys.advanceToNextBlock()
		for buyOffer in expired:
			self._tradeOfferChangeCounts[buyOffer.refundAccount] += 1
			self._balances.addTo(buyOffer.refundAccount, buyOffer._swapBillOffered)
			self._removeTradeRef(buyOffer.refundAccount)

		expired = self._LTCSells.advanceToNextBlock()
		for sellOffer in expired:
			self._tradeOfferChangeCounts[sellOffer.receivingAccount] += 1
			self._balances.addTo(sellOffer.receivingAccount, sellOffer._swapBillDeposit)
			self._removeTradeRef(sellOffer.receivingAccount)
		# ** currently iterates through all pending exchanges each block added
		# are there scaling issues with this?
		toDelete = []
		for key in self._pendingExchanges:
			exchange = self._pendingExchanges[key]
			if exchange.expiry == self._currentBlockIndex:
				# refund buyers funds locked up in the exchange, plus sellers deposit (as penalty for failing to make exchange)
				self._balances.addTo(exchange.buyerAddress, exchange.swapBillAmount + exchange.swapBillDeposit)
				self._tradeOfferChangeCounts[exchange.buyerAddress] += 1
				self._tradeOfferChangeCounts[exchange.sellerReceivingAccount] += 1
				self._removeTradeRef(exchange.buyerAddress)
				self._removeTradeRef(exchange.sellerReceivingAccount)
				toDelete.append(key)
		for key in toDelete:
			self._pendingExchanges.pop(key)
		self._currentBlockIndex += 1

	def _matchOffersAndAddExchange(self, buy, sell):
		assert self._balances.isReferenced(buy.refundAccount)
		assert self._balances.isReferenced(sell.receivingAccount)
		exchange, buyRemainder, sellRemainder = TradeOffer.MatchOffers(buy=buy, sell=sell)
		self._tradeOfferChangeCounts[sell.receivingAccount] += 1
		self._tradeOfferChangeCounts[buy.refundAccount] += 1
		exchange.expiry = self._currentBlockIndex + Constraints.blocksForExchangeCompletion
		exchange.ltcReceiveAddress = buy.receivingAccount
		exchange.buyerAddress = buy.refundAccount
		exchange.sellerReceivingAccount = sell.receivingAccount
		key = self._nextExchangeIndex
		self._nextExchangeIndex += 1
		# the existing account refs from buy and sell details transfer into the exchange object
		# and then we add new refs for offer remainders as necessary
		self._pendingExchanges[key] = exchange
		if buyRemainder is not None:
			self._addTradeRef(buyRemainder.refundAccount)
		if sellRemainder is not None:
			self._addTradeRef(sellRemainder.receivingAccount)
		return buyRemainder, sellRemainder

	def _check_Burn(self, swapBillInput, outputs, amount):
		if outputs != ('destination',):
			raise OutputsSpecDoesntMatch()
		if swapBillInput + amount < Constraints.minimumSwapBillBalance:
			return False, 'burn output is below minimum balance'
		return True, ''
	def _apply_Burn(self, txID, swapBillInput, amount):
		self._totalCreated += amount
		self._balances.add((txID, 1), swapBillInput + amount)
		return 0

	def _check_Pay(self, swapBillInput, outputs, amount, maxBlock):
		if outputs != ('change', 'destination'):
			raise OutputsSpecDoesntMatch()
		if amount < Constraints.minimumSwapBillBalance:
			return False, 'amount is below minimum balance'
		if swapBillInput < amount:
			return False, 'insufficient swapbill input'
		if swapBillInput > amount and swapBillInput < amount + Constraints.minimumSwapBillBalance:
			return False, 'transaction would generate change output with change amount below minimum balance'
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_Pay(self, txID, swapBillInput, amount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return swapBillInput
		self._balances.add((txID, 2), amount)
		return swapBillInput - amount

	def _check_LTCBuyOffer(self, swapBillInput, outputs, swapBillOffered, exchangeRate, receivingAddress, maxBlock):
		if outputs != ('change', 'ltcBuy'):
			raise OutputsSpecDoesntMatch()
		assert exchangeRate < 0x100000000
		if swapBillOffered == 0:
			return False, 'zero amount not permitted'
		if swapBillInput < swapBillOffered + Constraints.minimumSwapBillBalance:
			return False, 'insufficient swapbill input'
		try:
			buy = TradeOffer.BuyOffer(swapBillOffered=swapBillOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			return False, 'does not satisfy minimum exchange amount'
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_LTCBuyOffer(self, txID, swapBillInput, swapBillOffered, exchangeRate, receivingAddress, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return swapBillInput
		refundAccount = (txID, 2)
		swapBillChange = swapBillInput - swapBillOffered - Constraints.minimumSwapBillBalance
		assert swapBillChange >= 0
		self._balances.add(refundAccount, Constraints.minimumSwapBillBalance)
		if swapBillChange < Constraints.minimumSwapBillBalance:
			self._balances.addTo(refundAccount, swapBillChange)
			swapBillChange = 0
		self._addFirstTradeRef(refundAccount)
		buy = TradeOffer.BuyOffer(swapBillOffered=swapBillOffered, rate=exchangeRate)
		buy.receivingAccount = receivingAddress
		buy.refundAccount = refundAccount
		buy.expiry = maxBlock
		toReAdd = []
		while True:
			if self._LTCSells.empty() or not TradeOffer.OffersMeetOrOverlap(buy=buy, sell=self._LTCSells.peekCurrentBest()):
				# no more matchable sell offers
				self._LTCBuys.addOffer(buy)
				break
			sell = self._LTCSells.popCurrentBest()
			try:
				buyRemainder, sellRemainder = self._matchOffersAndAddExchange(buy=buy, sell=sell)
			except TradeOffer.RemainderIsBelowMinimumExchange:
				toReAdd.append(sell)
				continue
			if buyRemainder is not None:
				buy = buyRemainder
				continue # (remainder can match against another offer)
			# new offer is fully matched
			if sellRemainder is not None:
				toReAdd.append(sellRemainder)
			break
		for entry in toReAdd:
			self._LTCSells.addOffer(entry)
		return swapBillChange

	def _check_LTCSellOffer(self, swapBillInput, outputs, ltcOffered, exchangeRate, maxBlock):
		if outputs != ('change', 'ltcSell'):
			raise OutputsSpecDoesntMatch()
		assert exchangeRate < 0x100000000
		if ltcOffered == 0:
			return False, 'zero amount not permitted'
		swapBillDeposit = TradeOffer.DepositRequiredForLTCSell(exchangeRate=exchangeRate, ltcOffered=ltcOffered)
		if swapBillInput < swapBillDeposit + Constraints.minimumSwapBillBalance:
			return False, 'insufficient swapbill input'
		try:
			sell = TradeOffer.SellOffer(swapBillDeposit=swapBillDeposit, ltcOffered=ltcOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			return False, 'does not satisfy minimum exchange amount'
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_LTCSellOffer(self, txID, swapBillInput, ltcOffered, exchangeRate, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return swapBillInput
		receivingAccount = (txID, 2)
		swapBillDeposit = TradeOffer.DepositRequiredForLTCSell(exchangeRate=exchangeRate, ltcOffered=ltcOffered)
		swapBillChange = swapBillInput - swapBillDeposit - Constraints.minimumSwapBillBalance
		assert swapBillChange >= 0
		self._balances.add(receivingAccount, Constraints.minimumSwapBillBalance)
		if swapBillChange < Constraints.minimumSwapBillBalance:
			self._balances.addTo(receivingAccount, swapBillChange)
			swapBillChange = 0
		self._addFirstTradeRef(receivingAccount)
		sell = TradeOffer.SellOffer(swapBillDeposit=swapBillDeposit, ltcOffered=ltcOffered, rate=exchangeRate)
		sell.receivingAccount = receivingAccount
		sell.expiry = maxBlock
		toReAdd = []
		while True:
			if self._LTCBuys.empty() or not TradeOffer.OffersMeetOrOverlap(buy=self._LTCBuys.peekCurrentBest(), sell=sell):
				# no more matchable buy offers
				self._LTCSells.addOffer(sell)
				break
			buy = self._LTCBuys.popCurrentBest()
			try:
				buyRemainder, sellRemainder = self._matchOffersAndAddExchange(buy=buy, sell=sell)
			except TradeOffer.RemainderIsBelowMinimumExchange:
				toReAdd.append(buy)
				continue
			if sellRemainder is not None:
				sell = sellRemainder
				continue # (remainder can match against another offer)
			# new offer is fully matched
			if buyRemainder is not None:
				toReAdd.append(buyRemainder)
			break
		for entry in toReAdd:
			self._LTCBuys.addOffer(entry)
		return swapBillChange

	#def _check_BackLTCSells(self, outputs, sourceAccount, backingAmount, transactionMax, receivingAddress, maxBlock):
		#if outputs != ('change', 'refund'):
			#raise OutputsSpecDoesntMatch()
		#assert type(backingAmount) is int
		#assert backingAmount >= 0
		#assert type(transactionMax) is int
		#assert transactionMax >= 0
		#if backingAmount < Constraints.minimumSwapBillBalance:
			#return False, 'amount is below minimum balance'
		#if backingAmount < transactionMax * 100:
			#return False, 'not enough transactions covered'
		#if not sourceAccount in self._balances:
			#return False, 'source account does not exist'
		#if self._balances[sourceAccount] < backingAmount:
			#return False, 'insufficient swapbill input'
		#if self._balances[sourceAccount] > backingAmount and self._balances[sourceAccount] < backingAmount + Constraints.minimumSwapBillBalance:
			#return False, 'transaction would generate change output with change amount below minimum balance'
		#if sourceAccount in self._balanceRefCounts:
			#return False, "source account is not currently spendable (e.g. this may be locked until a trade completes)"
		#if maxBlock < self._currentBlockIndex:
			#return True, 'max block for transaction has been exceeded'
		#return True, ''
	#def _apply_BackLTCSells(self, txID, sourceAccount, backingAmount, transactionMax, receivingAddress, maxBlock):
		#available = self._balances.consume(sourceAccount)
		#if maxBlock < self._currentBlockIndex:
			#self._balances.add((txID, 1), available)
			#return
		#self._totalForwarded += amount
		#if available > amount:
			#self._balances.add((txID, 1), available - amount)

	def _check_ForwardToFutureNetworkVersion(self, swapBillInput, outputs, amount, maxBlock):
		if outputs != ('change',):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount < Constraints.minimumSwapBillBalance:
			return False, 'amount is below minimum balance'
		if swapBillInput < amount:
			return False, 'insufficient swapbill input'
		if swapBillInput > amount and swapBillInput < amount + Constraints.minimumSwapBillBalance:
			return False, 'transaction would generate change output with change amount below minimum balance'
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_ForwardToFutureNetworkVersion(self, txID, swapBillInput, amount, maxBlock):
		if maxBlock < self._currentBlockIndex:
			return swapBillInput
		self._totalForwarded += amount
		return swapBillInput - amount

	def _check_unfunded_LTCExchangeCompletion(self, outputs, pendingExchangeIndex, destinationAddress, destinationAmount):
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
	def _apply_unfunded_LTCExchangeCompletion(self, txID, pendingExchangeIndex, destinationAddress, destinationAmount):
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		## the seller completed their side of the exchange, so credit them the buyers swapbill
		## and the seller is also refunded their deposit here
		self._balances.addTo(exchangeDetails.sellerReceivingAccount, exchangeDetails.swapBillAmount + exchangeDetails.swapBillDeposit)
		self._tradeOfferChangeCounts[exchangeDetails.buyerAddress] += 1
		self._tradeOfferChangeCounts[exchangeDetails.sellerReceivingAccount] += 1
		self._removeTradeRef(exchangeDetails.buyerAddress)
		self._removeTradeRef(exchangeDetails.sellerReceivingAccount)
		self._pendingExchanges.pop(pendingExchangeIndex)

	def checkTransaction(self, transactionType, outputs, transactionDetails, sourceAccounts=None):
		methodName = '_check_'
		if sourceAccounts is None:
			methodName += 'unfunded_'
		methodName += transactionType
		try:
			method = getattr(self, methodName)
		except AttributeError as e:
			raise InvalidTransactionType(e)
		if sourceAccounts is not None:
			usesLocked = False
			swapBillInput = 0
			for sourceAccount in sourceAccounts:
				if not self._balances.accountHasBalance(sourceAccount):
					continue
				if self._balances.isReferenced(sourceAccount):
					usesLocked = True
					continue
				swapBillInput += self._balances.balanceFor(sourceAccount)
			try:
				canApply, reason = method(swapBillInput=swapBillInput, outputs=outputs, **transactionDetails)
			except TypeError as e:
				raise InvalidTransactionParameters(e)
			if canApply and usesLocked:
				return True, "at least one source account is not currently spendable (e.g. this may be locked until a trade completes)"
			return canApply, reason
		else:
			try:
				return method(outputs=outputs, **transactionDetails)
			except TypeError as e:
				raise InvalidTransactionParameters(e)
	def applyTransaction(self, transactionType, txID, outputs, transactionDetails, sourceAccounts=None):
		assert self.checkTransaction(transactionType, outputs, transactionDetails, sourceAccounts)[0] == True
		methodName = '_apply_'
		if sourceAccounts is None:
			methodName += 'unfunded_'
		methodName += transactionType
		method = getattr(self, methodName)
		if sourceAccounts is not None:
			swapBillInput = 0
			for sourceAccount in sourceAccounts:
				if not self._balances.accountHasBalance(sourceAccount):
					continue
				if self._balances.isReferenced(sourceAccount):
					# TODO consume this account also?
					continue
				swapBillInput += self._balances.consume(sourceAccount)
			change = method(txID, swapBillInput, **transactionDetails)
			if change > 0:
				assert change >= Constraints.minimumSwapBillBalance
				self._balances.add((txID, 1), change)
		else:
			change = method(txID, **transactionDetails)
