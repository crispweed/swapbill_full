from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, TradeOffer, Balances
from SwapBill.HardCodedProtocolConstraints import Constraints
from SwapBill.Amounts import e

class InvalidTransactionParameters(Exception):
	pass
class InvalidTransactionType(Exception):
	pass
class TransactionNotAllowed(Exception):
	pass
class TransactionWouldntHaveIntendedEffect(Exception):
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
			buyRemainder.receivingAccount = buy.receivingAccount
			buyRemainder.refundAccount = buy.refundAccount
			buyRemainder.expiry = buy.expiry
			self._addTradeRef(buyRemainder.refundAccount)
		if sellRemainder is not None:
			sellRemainder.receivingAccount = sell.receivingAccount
			sellRemainder.expiry = sell.expiry
			self._addTradeRef(sellRemainder.receivingAccount)
		return buyRemainder, sellRemainder

	def _fundedTransaction_Burn(self, txID, swapBillInput, amount, outputs):
		assert outputs == ('destination',)
		if swapBillInput + amount < Constraints.minimumSwapBillBalance:
			raise TransactionNotAllowed('burn output is below minimum balance')
		if txID is None:
			return
		self._totalCreated += amount
		self._balances.add((txID, 1), swapBillInput + amount)
		return 0

	def _fundedTransaction_Pay(self, txID, swapBillInput, amount, maxBlock, outputs):
		assert outputs == ('change', 'destination')
		if maxBlock < self._currentBlockIndex:
			if txID is None:
				raise TransactionWouldntHaveIntendedEffect('max block for transaction has been exceeded')
			return swapBillInput
		if amount < Constraints.minimumSwapBillBalance:
			raise TransactionNotAllowed('amount is below minimum balance')
		if swapBillInput < amount:
			raise TransactionNotAllowed('insufficient swapbill input')
		change = swapBillInput - amount
		if change > 0 and change < Constraints.minimumSwapBillBalance:
			raise TransactionNotAllowed('transaction would generate change output with change amount below minimum balance')
		if txID is None:
			return
		self._balances.add((txID, 2), amount)
		return change

	def _fundedTransaction_LTCBuyOffer(self, txID, swapBillInput, swapBillOffered, exchangeRate, receivingAddress, maxBlock, outputs):
		assert outputs == ('change', 'ltcBuy')
		assert exchangeRate < 0x100000000
		if maxBlock < self._currentBlockIndex:
			if txID is None:
				raise TransactionWouldntHaveIntendedEffect('max block for transaction has been exceeded')
			return swapBillInput
		change = swapBillInput - swapBillOffered - Constraints.minimumSwapBillBalance
		if change < 0:
			raise TransactionNotAllowed('insufficient swapbill input')
		try:
			buy = TradeOffer.BuyOffer(swapBillOffered=swapBillOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			raise TransactionNotAllowed('does not satisfy minimum exchange amount')
		if txID is None:
			return
		refundAccount = (txID, 2)
		self._balances.add(refundAccount, Constraints.minimumSwapBillBalance)
		if change < Constraints.minimumSwapBillBalance:
			self._balances.addTo(refundAccount, change)
			change = 0
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
			except TradeOffer.OfferIsBelowMinimumExchange:
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
		return change

	def _fundedTransaction_LTCSellOffer(self, txID, swapBillInput, ltcOffered, exchangeRate, maxBlock, outputs):
		assert outputs == ('change', 'ltcSell')
		assert exchangeRate < 0x100000000
		if maxBlock < self._currentBlockIndex:
			if txID is None:
				raise TransactionWouldntHaveIntendedEffect('max block for transaction has been exceeded')
			return swapBillInput
		swapBillDeposit = TradeOffer.DepositRequiredForLTCSell(exchangeRate=exchangeRate, ltcOffered=ltcOffered)
		change = swapBillInput - swapBillDeposit - Constraints.minimumSwapBillBalance
		if change < 0:
			raise TransactionNotAllowed('insufficient swapbill input')
		try:
			sell = TradeOffer.SellOffer(swapBillDeposit=swapBillDeposit, ltcOffered=ltcOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			raise TransactionNotAllowed('does not satisfy minimum exchange amount')
		if txID is None:
			return
		receivingAccount = (txID, 2)
		self._balances.add(receivingAccount, Constraints.minimumSwapBillBalance)
		if change < Constraints.minimumSwapBillBalance:
			self._balances.addTo(receivingAccount, change)
			change = 0
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
			except TradeOffer.OfferIsBelowMinimumExchange:
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
		return change

	def _fundedTransaction_ForwardToFutureNetworkVersion(self, txID, swapBillInput, amount, maxBlock, outputs):
		assert outputs == ('change',)
		if maxBlock < self._currentBlockIndex:
			if txID is None:
				raise TransactionWouldntHaveIntendedEffect('max block for transaction has been exceeded')
			return swapBillInput
		if amount < Constraints.minimumSwapBillBalance:
			raise TransactionNotAllowed('amount is below minimum balance')
		if swapBillInput < amount:
			raise TransactionNotAllowed('insufficient swapbill input')
		change = swapBillInput - amount
		if change > 0 and change < Constraints.minimumSwapBillBalance:
			raise TransactionNotAllowed('transaction would generate change output with change amount below minimum balance')
		if txID is None:
			return
		self._totalForwarded += amount
		return change

	def _unfundedTransaction_LTCExchangeCompletion(self, txID, pendingExchangeIndex, destinationAddress, destinationAmount, outputs):
		assert outputs == ()
		if not pendingExchangeIndex in self._pendingExchanges:
			raise TransactionNotAllowed('no pending exchange with the specified index')
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		if destinationAddress != exchangeDetails.ltcReceiveAddress:
			raise TransactionNotAllowed('destination account does not match destination for pending exchange with the specified index')
		if destinationAmount < exchangeDetails.ltc:
			raise TransactionNotAllowed('amount is less than required payment amount')
		if destinationAmount > exchangeDetails.ltc and txID is None:
			raise TransactionWouldntHaveIntendedEffect('amount is greater than required payment amount')
		if txID is None:
			return
		# the seller completed their side of the exchange, so credit them the buyers swapbill
		# and the seller is also refunded their deposit here
		self._balances.addTo(exchangeDetails.sellerReceivingAccount, exchangeDetails.swapBillAmount + exchangeDetails.swapBillDeposit)
		self._tradeOfferChangeCounts[exchangeDetails.buyerAddress] += 1
		self._tradeOfferChangeCounts[exchangeDetails.sellerReceivingAccount] += 1
		self._removeTradeRef(exchangeDetails.buyerAddress)
		self._removeTradeRef(exchangeDetails.sellerReceivingAccount)
		self._pendingExchanges.pop(pendingExchangeIndex)

	def checkTransaction(self, transactionType, outputs, transactionDetails, sourceAccounts=None):
		if sourceAccounts is None:
			methodPrefix = '_unfundedTransaction_'
		else:
			methodPrefix = '_fundedTransaction_'
		try:
			method = getattr(self, methodPrefix + transactionType)
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
			if sourceAccounts is None:
				method(outputs=outputs, txID=None, **transactionDetails)
			else:
				method(swapBillInput=swapBillInput, txID=None, outputs=outputs, **transactionDetails)
		except TypeError as e:
			raise InvalidTransactionParameters(e)
		except TransactionNotAllowed as e:
			return False, e.message
		except TransactionWouldntHaveIntendedEffect as e:
			return True, e.message
		return True, ''
	def applyTransaction(self, transactionType, txID, outputs, transactionDetails, sourceAccounts=None):
		assert self.checkTransaction(transactionType, outputs, transactionDetails, sourceAccounts)[0] == True
		if sourceAccounts is None:
			methodPrefix = '_unfundedTransaction_'
		else:
			methodPrefix = '_fundedTransaction_'
		method = getattr(self, methodPrefix + transactionType)
		if sourceAccounts is not None:
			swapBillInput = 0
			for sourceAccount in sourceAccounts:
				if not self._balances.accountHasBalance(sourceAccount):
					continue
				if self._balances.isReferenced(sourceAccount):
					# TODO consume this account also?
					continue
				swapBillInput += self._balances.consume(sourceAccount)
			change = method(txID, swapBillInput, outputs=outputs, **transactionDetails)
			if change > 0:
				assert change >= Constraints.minimumSwapBillBalance
				self._balances.add((txID, 1), change)
		else:
			method(txID=txID, outputs=outputs, **transactionDetails)
