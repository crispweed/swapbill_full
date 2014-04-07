import heapq

class Heap(object):
	def __init__(self, startBlockCount, higherExchangeRateIsBetterOffer):
		self._blockCount = startBlockCount
		self._higherExchangeRateIsBetterOffer = higherExchangeRateIsBetterOffer
		self._offerByExchangeRate = []
		self._entryCount = 0 # used to avoid priority ties

	def _hasExpired(self, expiry):
		return self._blockCount >= expiry
	def _hasExpiredOffers(self):
		for offer in self._offerByExchangeRate:
			if self._hasExpired(offer[4]):
				return True
		return False

	def addOffer(self, address, amount, exchangeRate, expiry):
		assert amount >= 0
		if amount == 0 or self._hasExpired(expiry):
			return
		if self._higherExchangeRateIsBetterOffer:
			exchangeRate = -exchangeRate
		entry = (exchangeRate, self._entryCount, address, amount, expiry)
		self._entryCount += 1
		heapq.heappush(self._offerByExchangeRate, entry)

	def advanceToBlock(self, advanceTo):
		assert advanceTo >= self._blockCount
		self._blockCount = advanceTo
		if not self._hasExpiredOffers():
			return
		expired = []
		unexpired = []
		for offer in self._offerByExchangeRate:
			if self._hasExpired(offer[4]):
				expired.append(offer)
			else:
				unexpired.append(offer)
		heapq.heapify(unexpired)
		self._offerByExchangeRate = unexpired
	def advanceToNextBlock(self):
		self.advanceToBlock(self._blockCount + 1)

	def size(self):
		return len(self._offerByExchangeRate)
	def empty(self):
		return len(self._offerByExchangeRate) == 0

	def currentBestExchangeRate(self):
		assert not self.empty()
		if self._higherExchangeRateIsBetterOffer:
			return -self._offerByExchangeRate[0][0]
		return self._offerByExchangeRate[0][0]
	def currentBestAmount(self):
		assert not self.empty()
		return self._offerByExchangeRate[0][3]

	def popCurrentBest(self):
		assert not self.empty()
		return heapq.heappop(self._offerByExchangeRate)

	def partiallyUseCurrentBest(self, amount):
		assert not self.empty()
		assert self.currentBestAmount() > amount
		e = self._offerByExchangeRate[0]
		self._offerByExchangeRate[0] = (e[0], e[1], e[2], e[3] - amount, e[4])
