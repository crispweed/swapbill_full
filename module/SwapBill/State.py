from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, TradeOffer, Balances
from SwapBill.HardCodedProtocolConstraints import Constraints
from SwapBill.Amounts import e

class InvalidTransactionParameters(Exception):
	pass
class InvalidTransactionType(Exception):
	pass

class BadlyFormedTransaction(Exception):
	pass
class TransactionFailsAgainstCurrentState(Exception):
	pass
class InsufficientFundsForTransaction(Exception):
	pass

class LTCSellBacker(object):
	pass

class State(object):
	def __init__(self, startBlockIndex, startBlockHash):
		## state is initialised at the start of the block with startBlockIndex
		self._startBlockHash = startBlockHash
		self._currentBlockIndex = startBlockIndex
		self._balances = Balances.Balances()
		self._totalCreated = 0
		self._totalForwarded = 0
		self._LTCBuys = TradeOfferHeap.Heap(startBlockIndex, False) # lower exchange rate is better offer
		self._LTCSells = TradeOfferHeap.Heap(startBlockIndex, True) # higher exchange rate is better offer
		self._nextExchangeIndex = 0
		self._pendingExchanges = {}
		self._nextBackerIndex = 0
		self._ltcSellBackers = {}

	def startBlockMatches(self, startBlockHash):
		return self._startBlockHash == startBlockHash

	def advanceToNextBlock(self):
		expired = self._LTCBuys.advanceToNextBlock()
		for buyOffer in expired:
			self._balances.addStateChange(buyOffer.refundAccount)
			self._balances.addTo_Forwarded(buyOffer.refundAccount, buyOffer._swapBillOffered)
			self._balances.removeRef(buyOffer.refundAccount)
		expired = self._LTCSells.advanceToNextBlock()
		for sellOffer in expired:
			self._balances.addStateChange(sellOffer.receivingAccount)
			self._balances.addTo_Forwarded(sellOffer.receivingAccount, sellOffer._swapBillDeposit)
			self._balances.removeRef(sellOffer.receivingAccount)
		# ** currently iterates through all pending exchanges each block added
		# are there scaling issues with this?
		toDelete = []
		for key in self._pendingExchanges:
			exchange = self._pendingExchanges[key]
			if exchange.expiry == self._currentBlockIndex:
				# refund buyers funds locked up in the exchange, plus sellers deposit (as penalty for failing to make exchange)
				self._balances.addTo_Forwarded(exchange.buyerAddress, exchange.swapBillAmount + exchange.swapBillDeposit)
				self._balances.addStateChange(exchange.buyerAddress)
				self._balances.addStateChange(exchange.sellerReceivingAccount)
				self._balances.removeRef(exchange.buyerAddress)
				self._balances.removeRef(exchange.sellerReceivingAccount)
				toDelete.append(key)
		for key in toDelete:
			self._pendingExchanges.pop(key)
		# ** currently iterates through all entries each block added
		# are there scaling issues with this?
		toDelete = []
		for key in self._ltcSellBackers:
			backer = self._ltcSellBackers[key]
			if backer.expiry == self._currentBlockIndex:
				# refund remaining amount
				self._balances.addTo_Forwarded(backer.refundAccount, backer.backingAmount)
				self._balances.addStateChange(backer.refundAccount)
				self._balances.removeRef(backer.refundAccount)
				toDelete.append(key)
		for key in toDelete:
				self._ltcSellBackers.pop(key)
		self._currentBlockIndex += 1

	def _matchOffersAndAddExchange(self, buy, sell):
		assert buy.refundAccount in self._balances.changeCounts
		assert sell.receivingAccount in self._balances.changeCounts
		exchange, buyRemainder, sellRemainder = TradeOffer.MatchOffers(buy=buy, sell=sell)
		self._balances.addStateChange(sell.receivingAccount)
		self._balances.addStateChange(buy.refundAccount)
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
			self._balances.addRef(buyRemainder.refundAccount)
		if sellRemainder is not None:
			sellRemainder.receivingAccount = sell.receivingAccount
			sellRemainder.expiry = sell.expiry
			self._balances.addRef(sellRemainder.receivingAccount)
		return buyRemainder, sellRemainder

	def _fundedTransaction_Burn(self, txID, swapBillInput, changeRequired, amount, outputs):
		assert outputs == ('destination',)
		if swapBillInput + amount < Constraints.minimumSwapBillBalance:
			raise BadlyFormedTransaction('burn output is below minimum balance')
		if txID is None:
			return
		self._totalCreated += amount
		return swapBillInput + amount

	def _fundedTransaction_Pay(self, txID, swapBillInput, changeRequired, amount, maxBlock, outputs):
		assert outputs == ('change', 'destination')
		if amount < Constraints.minimumSwapBillBalance:
			raise BadlyFormedTransaction('amount is below minimum balance')
		if maxBlock < self._currentBlockIndex:
			raise TransactionFailsAgainstCurrentState('max block for transaction has been exceeded')
		if swapBillInput < amount:
			raise InsufficientFundsForTransaction()
		change = swapBillInput - amount
		if changeRequired and change == 0:
			raise InsufficientFundsForTransaction()
		if change > 0 and change < Constraints.minimumSwapBillBalance:
			raise InsufficientFundsForTransaction()
		if txID is None:
			return
		self._balances.add((txID, 2), amount)
		return change

	def _fundedTransaction_LTCBuyOffer(self, txID, swapBillInput, changeRequired, swapBillOffered, exchangeRate, receivingAddress, maxBlock, outputs):
		assert outputs == ('ltcBuy',)
		assert exchangeRate < 0x100000000
		try:
			buy = TradeOffer.BuyOffer(swapBillOffered=swapBillOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			raise BadlyFormedTransaction('does not satisfy minimum exchange amount')
		if maxBlock < self._currentBlockIndex:
			raise TransactionFailsAgainstCurrentState('max block for transaction has been exceeded')
		change = swapBillInput - swapBillOffered
		# change is always required here, since we will add a trade ref
		if change < Constraints.minimumSwapBillBalance:
			raise InsufficientFundsForTransaction()
		if txID is None:
			return
		refundAccount = (txID, 1) # (now same as change account)
		self._balances.add(refundAccount, 0) # temporarily empty, but change will be paid in to this after return
		self._balances.addFirstRef(refundAccount)
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

	def _fundedTransaction_LTCSellOffer(self, txID, swapBillInput, changeRequired, ltcOffered, exchangeRate, maxBlock, outputs):
		assert outputs == ('ltcSell',)
		assert exchangeRate < 0x100000000
		swapBillDeposit = TradeOffer.DepositRequiredForLTCSell(exchangeRate=exchangeRate, ltcOffered=ltcOffered)
		try:
			sell = TradeOffer.SellOffer(swapBillDeposit=swapBillDeposit, ltcOffered=ltcOffered, rate=exchangeRate)
		except TradeOffer.OfferIsBelowMinimumExchange:
			raise BadlyFormedTransaction('does not satisfy minimum exchange amount')
		if maxBlock < self._currentBlockIndex:
			raise TransactionFailsAgainstCurrentState('max block for transaction has been exceeded')
		change = swapBillInput - swapBillDeposit
		# change is always required here, since we will add a trade ref
		if change < Constraints.minimumSwapBillBalance:
			raise InsufficientFundsForTransaction()
		if txID is None:
			return
		receivingAccount = (txID, 1) # (now same as change account)
		self._balances.add(receivingAccount, 0) # temporarily empty, but change will be paid in to this after return
		self._balances.addFirstRef(receivingAccount)
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

	def _fundedTransaction_BackLTCSells(self, txID, swapBillInput, changeRequired, backingAmount, transactionsBacked, commission, ltcReceiveAddress, maxBlock, outputs):
		assert outputs == ('ltcSellBacker',)
		if maxBlock < self._currentBlockIndex:
			raise TransactionFailsAgainstCurrentState('max block for transaction has been exceeded')
		change = swapBillInput - backingAmount
		# change is always required here, since we will add a ref
		if change < Constraints.minimumSwapBillBalance:
			raise InsufficientFundsForTransaction()
		if txID is None:
			return
		refundAccount = (txID, 1) # (now same as change account)
		self._balances.add(refundAccount, 0) # temporarily empty, but change will be paid in to this after return
		self._balances.addFirstRef(refundAccount)
		backer = LTCSellBacker()
		backer.backingAmount = backingAmount
		backer.transactionMax = backingAmount // transactionsBacked
		backer.commission = commission
		backer.ltcReceiveAddress = ltcReceiveAddress
		backer.refundAccount = refundAccount
		backer.expiry = maxBlock
		key = self._nextBackerIndex
		self._nextBackerIndex += 1
		self._ltcSellBackers[key] = backer
		return change

	def _fundedTransaction_ForwardToFutureNetworkVersion(self, txID, swapBillInput, changeRequired, amount, maxBlock, outputs):
		assert outputs == ('change',)
		if amount < Constraints.minimumSwapBillBalance:
			raise BadlyFormedTransaction('amount is below minimum balance')
		if maxBlock < self._currentBlockIndex:
			raise TransactionFailsAgainstCurrentState('max block for transaction has been exceeded')
		if swapBillInput < amount:
			raise InsufficientFundsForTransaction()
		change = swapBillInput - amount
		if changeRequired and change == 0:
			raise InsufficientFundsForTransaction()
		if change > 0 and change < Constraints.minimumSwapBillBalance:
			raise InsufficientFundsForTransaction()
		if txID is None:
			return
		self._totalForwarded += amount
		return change

	def _unfundedTransaction_LTCExchangeCompletion(self, txID, pendingExchangeIndex, destinationAddress, destinationAmount, outputs):
		assert outputs == ()
		if not pendingExchangeIndex in self._pendingExchanges:
			raise BadlyFormedTransaction('no pending exchange with the specified index')
		exchange = self._pendingExchanges[pendingExchangeIndex]
		if destinationAddress != exchange.ltcReceiveAddress:
			raise BadlyFormedTransaction('destination account does not match destination for pending exchange with the specified index')
		if destinationAmount < exchange.ltc:
			raise BadlyFormedTransaction('amount is less than required payment amount')
		if txID is None:
			if destinationAmount > exchange.ltc:
				raise TransactionFailsAgainstCurrentState('amount is greater than required payment amount')
			return
		# the seller completed their side of the exchange, so credit them the buyers swapbill
		# and the seller is also refunded their deposit here
		self._balances.addTo_Forwarded(exchange.sellerReceivingAccount, exchange.swapBillAmount + exchange.swapBillDeposit)
		self._balances.addStateChange(exchange.buyerAddress)
		self._balances.addStateChange(exchange.sellerReceivingAccount)
		self._balances.removeRef(exchange.buyerAddress)
		self._balances.removeRef(exchange.sellerReceivingAccount)
		self._pendingExchanges.pop(pendingExchangeIndex)


	def checkFundedTransaction(self, transactionType, sourceAccounts, transactionDetails, outputs):
		try:
			method = getattr(self, '_fundedTransaction_' + transactionType)
		except AttributeError as e:
			raise InvalidTransactionType(e)
		changeRequired = False
		swapBillInput = 0
		for sourceAccount in sourceAccounts:
			if not self._balances.accountHasBalance(sourceAccount):
				continue
			swapBillInput += self._balances.balanceFor(sourceAccount)
			if self._balances.isReferenced(sourceAccount):
				changeRequired = True
		try:
			method(swapBillInput=swapBillInput, changeRequired=changeRequired, txID=None, outputs=outputs, **transactionDetails)
		except TypeError as e:
			raise InvalidTransactionParameters(e)
		except BadlyFormedTransaction as e:
			return False, str(e)
		except TransactionFailsAgainstCurrentState as e:
			return True, str(e)
		return True, ''
	def applyFundedTransaction(self, transactionType, txID, sourceAccounts, transactionDetails, outputs):
		try:
			method = getattr(self, '_fundedTransaction_' + transactionType)
		except AttributeError as e:
			return
		swapBillInput = 0
		consumeAndForward = []
		changeRequired = False
		for sourceAccount in sourceAccounts:
			if not self._balances.accountHasBalance(sourceAccount):
				continue
			swapBillInput += self._balances.balanceFor(sourceAccount)
			consumeAndForward.append(sourceAccount)
			if self._balances.isReferenced(sourceAccount):
				changeRequired = True
		wasSuccessful = True
		try:
			change = method(txID=txID, swapBillInput=swapBillInput, changeRequired=changeRequired, outputs=outputs, **transactionDetails)
		except (TypeError, BadlyFormedTransaction):
			return False, False
		except (TransactionFailsAgainstCurrentState, InsufficientFundsForTransaction):
			change = swapBillInput
			wasSuccessful = False
		if changeRequired:
			assert change > 0
		if change > 0:
			assert change >= Constraints.minimumSwapBillBalance
			self._balances.addOrAddTo((txID, 1), change)
			self._balances.consumeAndForwardRefs(consumeAndForward, (txID, 1))
		else:
			for account in consumeAndForward:
				self._balances.consume(account)
		return wasSuccessful, True

	def checkUnfundedTransaction(self, transactionType, transactionDetails, outputs):
		try:
			method = getattr(self, '_unfundedTransaction_' + transactionType)
		except AttributeError as e:
			raise InvalidTransactionType(e)
		try:
			method(txID=None, outputs=outputs, **transactionDetails)
		except TypeError as e:
			raise InvalidTransactionParameters(e)
		except BadlyFormedTransaction as e:
			return False, str(e)
		except TransactionFailsAgainstCurrentState as e:
			return True, str(e)
		return True, ''
	def applyUnfundedTransaction(self, transactionType, txID, transactionDetails, outputs):
		try:
			method = getattr(self, '_unfundedTransaction_' + transactionType)
		except AttributeError as e:
			return
		try:
			method(txID=txID, outputs=outputs, **transactionDetails)
		except (TypeError, BadlyFormedTransaction, TransactionFailsAgainstCurrentState):
			return False, False
		return True, True

	def checkTransaction(self, transactionType, sourceAccounts, transactionDetails, outputs):
		if sourceAccounts is None:
			return self.checkUnfundedTransaction(transactionType, transactionDetails, outputs)
		return self.checkFundedTransaction(transactionType, sourceAccounts, transactionDetails, outputs)
	def applyTransaction(self, transactionType, txID, sourceAccounts, transactionDetails, outputs):
		if sourceAccounts is None:
			return self.applyUnfundedTransaction(transactionType, txID, transactionDetails, outputs)
		return self.applyFundedTransaction(transactionType, txID, sourceAccounts, transactionDetails, outputs)
