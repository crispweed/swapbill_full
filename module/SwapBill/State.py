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

	def addToBalance(self, address, amount):
		assert amount >= 0
		if amount == 0:
			return
		if address in self._balances:
			self._balances[address] += amount
		else:
			self._balances[address] = amount

	def subtractFromBalance(self, address, amount):
		assert amount >= 0
		if amount == 0:
			return
		assert address in self._balances and self._balances[address] >= amount
		if amount == self._balances[address]:
			self._balances.pop(address)
		else:
			self._balances[address] -= amount

	def subtractFromBalance_Capped(self, address, amount):
		assert amount >= 0
		if amount == 0:
			return 0
		if not address in self._balances:
			return 0
		if self._balances[address] <= amount:
			cappedAmount = self._balances[address]
			self._balances.pop(address)
			return cappedAmount
		self._balances[address] -= amount
		return amount

	def forwardToFutureVersion(amount):
		self._totalForwarded += amount

	def requestTransfer(self, source, amount, destination):
		cappedAmount = self.subtractFromBalance_Capped(source, amount)
		self.addToBalance(destination, cappedAmount)

	def requestAddLTCBuyOffer(self, source, swapBillOffered, exchangeRate, expiry, receivingAddress):
		if self._balances.get(source, 0) < swapBillOffered:
			return
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillOffered):
			return
		self.subtractFromBalance(source, swapBillOffered)
		buyDetails = BuyDetails()
		buyDetails.swapBillAddress = source
		buyDetails.swapBillAmount = swapBillOffered
		buyDetails.ltcReceiveAddress = receivingAddress
		self._LTCBuys.addOffer(exchangeRate, expiry, buyDetails)

	def requestAddLTCSellOffer(self, source, swapBillDesired, swapBillDeposit, exchangeRate, expiry):
		if not LTCTrading.SatisfiesMinimumExchange(exchangeRate, swapBillDesired):
			return
		if self._balances.get(source, 0) < swapBillDeposit:
			return
		self.subtractFromBalance(source, swapBillDeposit)
		sellDetails = SellDetails()
		sellDetails.swapBillAddress = source
		sellDetails.swapBillAmount = swapBillDesired
		sellDetails.swapBillDeposit = swapBillDeposit
		self._LTCSells.addOffer(exchangeRate, expiry, sellDetails)

	def addPendingExchange(self, exchange):
		exchange.expiry = self._currentBlockIndex + 50
		key = self._nextExchangeIndex
		self._nextExchangeIndex += 1
		self._pendingExchanges[key] = exchange

	def completeExchange(self, pendingExchangeIndex, destination, destinationAmount):
		if not pendingExchangeIndex in self._pendingExchanges:
			#print('no such pending exchange')
			return
		exchangeDetails = self._pendingExchanges[pendingExchangeIndex]
		if destination != exchangeDetails.ltcReceiveAddress:
			#print('pending exchange receive address mismatch')
			return
		if destinationAmount < exchangeDetails.ltc:
			## bit harsh if you make an error in setting up completion transaction?
			## (e.g. bad exchange rate calculation)
			## could also partially complete the exchange
			return
		## the seller completed his side of the exchange, so credit them the buyers swapbill
		## and the seller is also refunded their deposit here
		## TODO don't reuse seller address, need a separate address for this completion credit!
		#print(exchangeDetails.sellerAddress)
		self.addToBalance(exchangeDetails.sellerAddress, exchangeDetails.swapBillAmount + exchangeDetails.swapBillDeposit)
		self._pendingExchanges.pop(pendingExchangeIndex)

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
