from __future__ import print_function
import binascii
from SwapBill import TradeOfferHeap, LTCTrading

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
				self.addToBalance(exchange.buyerAddress, exchange.swapBillAmount + exchange.swapBillDeposit)
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

	def checkWouldApplySuccessfully_Transfer(self, sourceAccount, amount, destinationAccount):
		assert type(amount) is int
		assert amount > 0
		available = self._balances.get(sourceAccount, 0)
		if available >= amount:
			return True, ''
		if available > 0:
			return False, 'insufficient balance in source account (transfer capped)'
		return False, 'source account balance is 0'
	def apply_Transfer(self, sourceAccount, amount, destinationAccount):
		available = self._balances.get(sourceAccount, 0)
		if amount > available:
			amount = available
		self._subtractFromBalance(sourceAccount, amount)
		self._addToBalance(destinationAccount, amount)

	def checkWouldApplySuccessfully_AddLTCBuyOffer(self, sourceAccount, swapBillOffered, exchangeRate, expiry, receivingAccount):
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
	def apply_AddLTCBuyOffer(self, sourceAccount, swapBillOffered, exchangeRate, expiry, receivingAccount):
		if self._balances.get(sourceAccount, 0) < swapBillOffered:
			return
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillOffered):
			return
		self._subtractFromBalance(sourceAccount, swapBillOffered)
		buyDetails = BuyDetails()
		buyDetails.swapBillAddress = sourceAccount
		buyDetails.swapBillAmount = swapBillOffered
		buyDetails.ltcReceiveAddress = receivingAccount
		self._LTCBuys.addOffer(exchangeRate, expiry, buyDetails)
		LTCTrading.Match(self)

	def checkWouldApplySuccessfully_AddLTCSellOffer(self, sourceAccount, swapBillDesired, exchangeRate, expiry):
		assert type(swapBillDesired) is int
		assert swapBillDesired > 0
		assert type(exchangeRate) is int
		assert exchangeRate > 0
		assert exchangeRate < 0x100000000
		assert type(expiry) is int
		assert expiry > 0
		swapBillDeposit = swapBillDesired // LTCTrading.depositDivisor
		if self._balances.get(sourceAccount, 0) < swapBillDeposit:
			return False, 'insufficient balance for deposit in source account (offer not posted)'
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillDesired):
			return False, 'does not satisfy minimum exchange amount (offer not posted)'
		return True, ''
	def apply_AddLTCSellOffer(self, sourceAccount, swapBillDesired, exchangeRate, expiry):
		swapBillDeposit = swapBillDesired // LTCTrading.depositDivisor
		if self._balances.get(sourceAccount, 0) < swapBillDeposit:
			return
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillDesired):
			return
		self._subtractFromBalance(sourceAccount, swapBillDeposit)
		sellDetails = SellDetails()
		sellDetails.swapBillAddress = sourceAccount
		sellDetails.swapBillAmount = swapBillDesired
		sellDetails.swapBillDeposit = swapBillDeposit
		self._LTCSells.addOffer(exchangeRate, expiry, sellDetails)
		LTCTrading.Match(self)

	def checkWouldApplySuccessfully_CompleteLTCExchange(self, pendingExchangeIndex, destinationAccount, destinationAmount):
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
	def apply_CompleteLTCExchange(self, pendingExchangeIndex, destinationAccount, destinationAmount):
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

	def checkWouldApplySuccessfully_ForwardToFutureNetworkVersion(self, sourceAccount, amount):
		assert type(amount) is int
		assert amount > 0
		available = self._balances.get(sourceAccount, 0)
		if available >= amount:
			return True, ''
		if available > 0:
			return False, 'insufficient balance in source account (amount capped)'
		return False, 'source account balance is 0'
	def apply_ForwardToFutureNetworkVersion(self, pendingExchangeIndex, destinationAccount, destinationAmount):
		available = self._balances.get(sourceAccount, 0)
		if amount > available:
			amount = available
		self._subtractFromBalance(sourceAccount, amount)
		self._totalForwarded += amount


	def create(self, amount):
		assert amount >= 0
		if amount == 0:
			return
		self._totalCreated += amount
	def undoCreate(self, amount):
		assert amount >= 0
		if amount == 0:
			return
		self._totalCreated -= amount


	#def subtractFromBalance_Capped(self, address, amount):
		#assert amount >= 0
		#if amount == 0:
			#return 0
		#if not address in self._balances:
			#return 0
		#if self._balances[address] <= amount:
			#cappedAmount = self._balances[address]
			#self._balances.pop(address)
			#return cappedAmount
		#self._balances[address] -= amount
		#return amount

	def forwardToFutureVersion(amount):
		self._totalForwarded += amount


	def addPendingExchange(self, exchange):
		exchange.expiry = self._currentBlockIndex + 50
		key = self._nextExchangeIndex
		self._nextExchangeIndex += 1
		self._pendingExchanges[key] = exchange


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
		return result

	def printOffers(self):
		print('Buy offers:')
		offers = self._LTCBuys.getSortedExchangeRateAndDetails()
		if len(offers) == 0:
			print('  (no buy offers)')
		for exchangeRate, buyDetails in offers:
			address = buyDetails.swapBillAddress
			exchangeAmount = buyDetails.swapBillAmount
			rate_Double = float(exchangeRate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			print('  rate:{:.7f}, swapbill offered:{}, ltc equivalent:{}'.format(rate_Double, exchangeAmount, ltc))
		print('Sell offers:')
		offers = self._LTCSells.getSortedExchangeRateAndDetails()
		if len(offers) == 0:
			print('  (no sell offers)')
		for exchangeRate, sellDetails in offers:
			address = sellDetails.swapBillAddress
			exchangeAmount = sellDetails.swapBillAmount
			depositAmount = sellDetails.swapBillDeposit
			rate_Double = float(exchangeRate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			print('  rate:{:.7f}, swapbill desired:{}, ltc equivalent:{}'.format(rate_Double, exchangeAmount, ltc))

	def printPendingExchanges(self):
		print('Pending exchange completion payments:')
		if len(self._pendingExchanges) == 0:
			print('  (no pending completion payments)')
		for key in self._pendingExchanges:
			exchange = self._pendingExchanges[key]
			print(' key =', key, ':')
			print('  buyer =', binascii.hexlify(exchange.buyerAddress).decode('ascii'))
			print('  seller =', binascii.hexlify(exchange.sellerAddress).decode('ascii'))
			print('  swapBillAmount =', exchange.swapBillAmount)
			print('  swapBillDeposit =', exchange.swapBillDeposit)
			print('  ltc amount to pay =', exchange.ltc)
			print('  pay ltc to =', binascii.hexlify(exchange.ltcReceiveAddress))
