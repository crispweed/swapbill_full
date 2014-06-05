from __future__ import print_function

class Balances(object):
	def __init__(self):
		self._balances = {}
		self._balanceRefCounts = {}

	def accountHasBalance(self, account):
		return account in self._balances
	def balanceFor(self, account):
		return self._balances[account]

	def add(self, account, amount):
		assert type(amount) is int
		assert amount >= 0
		assert not account in self._balances
		self._balances[account] = amount
	def addTo(self, account, amount):
		assert type(amount) is int
		assert amount >= 0
		self._balances[account] += amount
	def consume(self, account):
		assert not account in self._balanceRefCounts
		amount = self._balances[account]
		self._balances.pop(account)
		return amount

	def addFirstReference(self, account):
		assert not account in self._balanceRefCounts
		self._balanceRefCounts[account] = 1
	def addReference(self, account):
		self._balanceRefCounts[account] += 1
	def removeReference(self, account):
		assert self._balanceRefCounts[account] > 0
		assert self._balances[account] > 0
		if self._balanceRefCounts[account] == 1:
			self._balanceRefCounts.pop(account)
		else:
			self._balanceRefCounts[account] -= 1

	def isReferenced(self, account):
		return account in self._balanceRefCounts
