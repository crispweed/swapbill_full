from SwapBill import TradeOfferHeap

class State(object):
	def __init__(self, startBlockCount):
		self._balances = {}
		self._totalCreated = 0
		self._totalForwarded = 0
		self._LTCBuys = TradeOfferHeap.Heap(startBlockCount, False) # lower exchange rate is better offer
		self._LTCSells = TradeOfferHeap.Heap(startBlockCount, True) # higher exchange rate is better offer

	def advanceToNextBlock(self):
		self._LTCBuys.advanceToNextBlock()
		self._LTCSells.advanceToNextBlock()

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

	def matchLTCOffers():
		pass

	def addLTCBuyOffer(self, address, amount, exchangeRate, expiry):
		self._LTCBuys.addOffer(address, amount, exchangeRate, expiry)
		#matchLTCOffers()

	def addLTCSellOffer(self, address, amount, exchangeRate, expiry):
		self._LTCSells.addOffer(address, amount, exchangeRate, expiry)
		#matchLTCOffers()
