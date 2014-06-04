from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, TradeOffer
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
	def __init__(self, startBlockIndex, startBlockHash, minimumBalance=1*e(7)):
		## state is initialised at the start of the block with startBlockIndex
		assert minimumBalance > 0
		self._startBlockHash = startBlockHash
		self._currentBlockIndex = startBlockIndex
		self._minimumBalance = minimumBalance
		self._balances = {}
		self._balanceRefCounts = {}
		self._tradeOfferChangeCounts = {}
		self._totalCreated = 0
		self._totalForwarded = 0
		self._LTCBuys = TradeOfferHeap.Heap(startBlockIndex, False) # lower exchange rate is better offer
		self._LTCSells = TradeOfferHeap.Heap(startBlockIndex, True) # higher exchange rate is better offer
		self._nextExchangeIndex = 0
		self._pendingExchanges = {}
		#self._nextBackerIndex = 0
		#self._ltcSellBackers = {}

	def getSpendableAmount(self, account):
		if account in self._balanceRefCounts:
			return 0
		return self._balances.get(account, 0)

	def startBlockMatches(self, startBlockHash):
		return self._startBlockHash == startBlockHash

	def advanceToNextBlock(self):
		expired = self._LTCBuys.advanceToNextBlock()
		for buyOffer in expired:
			self._tradeOfferChangeCounts[buyOffer.refundAccount] += 1
			self._addToAccount(buyOffer.refundAccount, buyOffer._swapBillOffered)
			self._removeAccountRef(buyOffer.refundAccount)
		expired = self._LTCSells.advanceToNextBlock()
		for sellOffer in expired:
			self._tradeOfferChangeCounts[sellOffer.receivingAccount] += 1
			self._addToAccount(sellOffer.receivingAccount, sellOffer._swapBillDeposit)
			self._removeAccountRef(sellOffer.receivingAccount)
		# ** currently iterates through all pending exchanges each block added
		# are there scaling issues with this?
		toDelete = []
		for key in self._pendingExchanges:
			exchange = self._pendingExchanges[key]
			if exchange.expiry == self._currentBlockIndex:
				# refund buyers funds locked up in the exchange, plus sellers deposit (as penalty for failing to make exchange)
				self._addToAccount(exchange.buyerAddress, exchange.swapBillAmount + exchange.swapBillDeposit)
				self._tradeOfferChangeCounts[exchange.buyerAddress] += 1
				self._tradeOfferChangeCounts[exchange.sellerReceivingAccount] += 1
				self._removeAccountRef(exchange.buyerAddress)
				self._removeAccountRef(exchange.sellerReceivingAccount)
				toDelete.append(key)
		for key in toDelete:
			self._pendingExchanges.pop(key)
		self._currentBlockIndex += 1

	def _addAccount(self, account, amount):
		assert type(amount) is int
		assert amount >= 0
		assert not account in self._balances
		self._balances[account] = amount
	def _addToAccount(self, account, amount):
		assert type(amount) is int
		assert amount >= 0
		self._balances[account] += amount
	def _consumeAccount(self, account):
		amount = self._balances[account]
		self._balances.pop(account)
		return amount

	def _removeAccountRef(self, account):
		assert self._balanceRefCounts[account] > 0
		assert self._balances[account] > 0
		if self._balanceRefCounts[account] == 1:
			self._tradeOfferChangeCounts.pop(account)
			self._balanceRefCounts.pop(account)
		else:
			self._balanceRefCounts[account] -= 1

	def _matchOffersAndAddExchange(self, buy, sell):
		assert self._balanceRefCounts[buy.refundAccount] > 0
		assert self._balanceRefCounts[sell.receivingAccount] > 0
		exchange, buyRemainder, sellRemainder = TradeOffer.MatchOffers(buy=buy, sell=sell)
		self._tradeOfferChangeCounts[sell.receivingAccount] += 1
		self._tradeOfferChangeCounts[buy.refundAccount] += 1
		exchange.expiry = self._currentBlockIndex + 50
		exchange.ltcReceiveAddress = buy.receivingAccount
		exchange.buyerAddress = buy.refundAccount
		exchange.sellerReceivingAccount = sell.receivingAccount
		key = self._nextExchangeIndex
		self._nextExchangeIndex += 1
		# note that the account refs from buy and sell details effectively transfer into this exchange object, by default
		self._pendingExchanges[key] = exchange
		if buyRemainder is not None:
			self._balanceRefCounts[buyRemainder.refundAccount] += 1
		if sellRemainder is not None:
			self._balanceRefCounts[sellRemainder.receivingAccount] += 1
		return buyRemainder, sellRemainder

	def _check_Burn(self, outputs, amount):
		if outputs != ('destination',):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount < self._minimumBalance:
			return False, 'burn amount is below minimum balance'
		return True, ''
	def _apply_Burn(self, txID, amount):
		self._totalCreated += amount
		self._addAccount((txID, 1), amount)

	def _check_Pay(self, outputs, sourceAccount, amount, maxBlock):
		if outputs != ('change', 'destination'):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount < self._minimumBalance:
			return False, 'amount is below minimum balance'
		if not sourceAccount in self._balances:
			return False, 'source account does not exist'
		if self._balances[sourceAccount] < amount:
			return False, 'insufficient balance in source account (transaction ignored)'
		if self._balances[sourceAccount] > amount and self._balances[sourceAccount] < amount + self._minimumBalance:
			return False, 'transaction includes change output, with change amount below minimum balance'
		if sourceAccount in self._balanceRefCounts:
			return False, "source account is not currently spendable (e.g. this may be locked until a trade completes)"
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_Pay(self, txID, sourceAccount, amount, maxBlock):
		available = self._consumeAccount(sourceAccount)
		if maxBlock < self._currentBlockIndex:
			amount = 0
		else:
			self._addAccount((txID, 2), amount)
		if available > amount:
			self._addAccount((txID, 1), available - amount)

	def _check_Collect(self, outputs, sourceAccounts):
		if outputs != ('destination',):
			raise OutputsSpecDoesntMatch()
		for sourceAccount in sourceAccounts:
			if not sourceAccount in self._balances:
				return False, 'at least one source account does not exist'
			if sourceAccount in self._balanceRefCounts:
				return False, "at least one source account is not currently spendable (e.g. this may be locked until a trade completes)"
		return True, ''
	def _apply_Collect(self, txID, sourceAccounts):
		amount = 0
		for sourceAccount in sourceAccounts:
			amount += self._consumeAccount(sourceAccount)
		if amount > 0:
			self._addAccount((txID, 1), amount)

	def _check_LTCBuyOffer(self, outputs, sourceAccount, swapBillOffered, exchangeRate, receivingAddress, maxBlock):
		if outputs != ('change', 'ltcBuy'):
			raise OutputsSpecDoesntMatch()
		assert type(swapBillOffered) is int
		assert swapBillOffered >= 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(maxBlock) is int
		assert maxBlock >= 0
		if swapBillOffered == 0:
			return False, 'zero amount not permitted'
		if not sourceAccount in self._balances:
			return False, 'source account does not exist'
		if self._balances[sourceAccount] < swapBillOffered + self._minimumBalance:
			return False, 'insufficient balance in source account (offer not posted)'
		if sourceAccount in self._balanceRefCounts:
			return False, "source account is not currently spendable (e.g. this may be locked until a trade completes)"
		try:
			buy = TradeOffer.BuyOffer(swapBillOffered=swapBillOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_LTCBuyOffer(self, txID, sourceAccount, swapBillOffered, exchangeRate, receivingAddress, maxBlock):
		available = self._consumeAccount(sourceAccount)
		if maxBlock < self._currentBlockIndex:
			self._addAccount((txID, 1), available)
			return
		changeAccount = (txID, 1)
		refundAccount = (txID, 2)
		assert available >= swapBillOffered + self._minimumBalance
		available -= swapBillOffered
		self._addAccount(refundAccount, self._minimumBalance)
		available -= self._minimumBalance
		if available >= self._minimumBalance:
			self._addAccount(changeAccount, available)
		else:
			self._addToAccount(refundAccount, available)
		assert not refundAccount in self._balanceRefCounts
		self._balanceRefCounts[refundAccount] = 1
		self._tradeOfferChangeCounts[refundAccount] = 0
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

	def _check_LTCSellOffer(self, outputs, sourceAccount, ltcOffered, exchangeRate, maxBlock):
		if outputs != ('change', 'ltcSell'):
			raise OutputsSpecDoesntMatch()
		assert type(ltcOffered) is int
		assert ltcOffered >= 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(maxBlock) is int
		assert maxBlock >= 0
		if ltcOffered == 0:
			return False, 'zero amount not permitted'
		if not sourceAccount in self._balances:
			return False, 'source account does not exist'
		swapBillDeposit = TradeOffer.DepositRequiredForLTCSell(exchangeRate=exchangeRate, ltcOffered=ltcOffered)
		if self._balances[sourceAccount] < swapBillDeposit + self._minimumBalance:
			return False, 'insufficient balance in source account (offer not posted)'
		if sourceAccount in self._balanceRefCounts:
			return False, "source account is not currently spendable (e.g. this may be locked until a trade completes)"
		try:
			sell = TradeOffer.SellOffer(swapBillDeposit=swapBillDeposit, ltcOffered=ltcOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_LTCSellOffer(self, txID, sourceAccount, ltcOffered, exchangeRate, maxBlock):
		swapBillDeposit = TradeOffer.DepositRequiredForLTCSell(exchangeRate=exchangeRate, ltcOffered=ltcOffered)
		available = self._consumeAccount(sourceAccount)
		if maxBlock < self._currentBlockIndex:
			self._addAccount((txID, 1), available)
			return
		changeAccount = (txID, 1)
		receivingAccount = (txID, 2)
		assert available >= swapBillDeposit + self._minimumBalance
		available -= swapBillDeposit
		self._addAccount(receivingAccount, self._minimumBalance)
		available -= self._minimumBalance
		if available >= self._minimumBalance:
			self._addAccount(changeAccount, available)
		else:
			self._addToAccount(receivingAccount, available)
		assert not receivingAccount in self._balanceRefCounts
		self._balanceRefCounts[receivingAccount] = 1
		self._tradeOfferChangeCounts[receivingAccount] = 0
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
		## the seller completed their side of the exchange, so credit them the buyers swapbill
		## and the seller is also refunded their deposit here
		self._addToAccount(exchangeDetails.sellerReceivingAccount, exchangeDetails.swapBillAmount + exchangeDetails.swapBillDeposit)
		self._tradeOfferChangeCounts[exchangeDetails.buyerAddress] += 1
		self._tradeOfferChangeCounts[exchangeDetails.sellerReceivingAccount] += 1
		self._removeAccountRef(exchangeDetails.buyerAddress)
		self._removeAccountRef(exchangeDetails.sellerReceivingAccount)
		self._pendingExchanges.pop(pendingExchangeIndex)

	#def _check_BackLTCSells(self, outputs, sourceAccount, backingAmount, transactionMax, receivingAddress, maxBlock):
		#if outputs != ('change', 'refund'):
			#raise OutputsSpecDoesntMatch()
		#assert type(backingAmount) is int
		#assert backingAmount >= 0
		#assert type(transactionMax) is int
		#assert transactionMax >= 0
		#if backingAmount < self._minimumBalance:
			#return False, 'amount is below minimum balance'
		#if backingAmount < transactionMax * 100:
			#return False, 'not enough transactions covered'
		#if maxBlock < self._currentBlockIndex:
			#return False, 'max block for transaction has been exceeded'
		#if not sourceAccount in self._balances:
			#return False, 'source account does not exist'
		#if self._balances[sourceAccount] < backingAmount:
			#return False, 'insufficient balance in source account (transaction ignored)'
		#if self._balances[sourceAccount] > backingAmount and self._balances[sourceAccount] < backingAmount + self._minimumBalance:
			#return False, 'transaction includes change output, with change amount below minimum balance'
		#if sourceAccount in self._balanceRefCounts:
			#return False, "source account is not currently spendable (e.g. this may be locked until a trade completes)"
		#return True, ''
	#def _apply_BackLTCSells(self, txID, sourceAccount, backingAmount, transactionMax, receivingAddress, maxBlock):
		#available = self._consumeAccount(sourceAccount)
		#self._totalForwarded += amount
		#if available > amount:
			#self._addAccount((txID, 1), available - amount)

	def _check_ForwardToFutureNetworkVersion(self, outputs, sourceAccount, amount, maxBlock):
		if outputs != ('change',):
			raise OutputsSpecDoesntMatch()
		assert type(amount) is int
		assert amount >= 0
		if amount < self._minimumBalance:
			return False, 'amount is below minimum balance'
		if not sourceAccount in self._balances:
			return False, 'source account does not exist'
		if self._balances[sourceAccount] < amount:
			return False, 'insufficient balance in source account (transaction ignored)'
		if self._balances[sourceAccount] > amount and self._balances[sourceAccount] < amount + self._minimumBalance:
			return False, 'transaction includes change output, with change amount below minimum balance'
		if sourceAccount in self._balanceRefCounts:
			return False, "source account is not currently spendable (e.g. this may be locked until a trade completes)"
		if maxBlock < self._currentBlockIndex:
			return True, 'max block for transaction has been exceeded'
		return True, ''
	def _apply_ForwardToFutureNetworkVersion(self, txID, sourceAccount, amount, maxBlock):
		available = self._consumeAccount(sourceAccount)
		if maxBlock < self._currentBlockIndex:
			self._addAccount((txID, 1), available)
			return
		self._totalForwarded += amount
		if available > amount:
			self._addAccount((txID, 1), available - amount)

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

