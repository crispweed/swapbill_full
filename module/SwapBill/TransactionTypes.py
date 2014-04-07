from __future__ import print_function
import struct
#import sys, inspect

class InvalidTransaction(Exception):
	pass
class UnsupportedTransaction(Exception):
	pass
class CannotRewind(Exception):
	pass
class Transaction(object):
	pass

class Burn(object):
	typeCode = 0
	needsSourceAddress = False
	needsDestinationAddress = True
	needsControlAddressAmount = True
	def init_FromUserRequirements(self, burnAmount, targetAddress):
		assert type(burnAmount) is int
		assert burnAmount > 0
		self.controlAddressAmount = burnAmount
		self.destinationAddress = targetAddress
	def init_DuringDecoding(self, amount, maxBlock, extraData):
		if amount != 0 or maxBlock != 0 or extraData != struct.pack("<B", 0) * 6:
			raise InvalidTransaction("invalid burn address")
	def encode(self):
		return 0, 0, struct.pack("<B", 0) * 6
	def apply(self, state):
		state.create(self.controlAddressAmount)
		state.addToBalance(self.destinationAddress, self.controlAddressAmount)
	def rewind(self, state):
		state.subtractFromBalance(self.destinationAddress, self.controlAddressAmount)
		state.undoCreate(self.controlAddressAmount)
	def __str__(self):
		return 'burn {} with credit to {}'.format(self.controlAddressAmount, self.destinationAddress)

class Transfer(object):
	typeCode = 1
	needsSourceAddress = True
	needsDestinationAddress = True
	needsControlAddressAmount = False
	def init_FromUserRequirements(self, fromAddress, amount, toAddress, maxBlock=0xffffffff):
		assert type(amount) is int
		assert amount > 0
		self.sourceAddress = fromAddress
		self.destinationAddress = toAddress
		self._amount = amount
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, amount, maxBlock, extraData):
		self._amount = amount
		self._maxBlock = maxBlock
	def encode(self):
		return self._amount, self._maxBlock, struct.pack("<B", 0) * 6
	def apply(self, state):
		self._cappedAmount = state.subtractFromBalance_Capped(self.sourceAddress, self._amount)
		state.addToBalance(self.destinationAddress, self._cappedAmount)
	def rewind(self, state):
		if hasattr(self, '_cappedAmount'):
			state.subtractFromBalance(self.destinationAddress, self._cappedAmount)
			state.addToBalance(self.sourceAddress, self._cappedAmount)
			delattr(self, '_cappedAmount')
		elif state.hasNonZeroBalance(self.sourceAddress):
			# don't need undo info in this case
			state.subtractFromBalance(self.destinationAddress, self._amount)
			state.addToBalance(self.sourceAddress, self._amount)
		else:
			raise CannotRewind()
	def __str__(self):
		result = 'transfer {} from {} to {}'.format(self._amount, self.sourceAddress, self.destinationAddress)
		if hasattr(self, '_cappedAmount'):
			result += ' (capped at {})'.format(self._cappedAmount)
		return result

class ForwardToFutureVersion(object):
	## this transaction is designed to be created only during decoding
	## (and so omits some stuff found in other transaction types)
	needsSourceAddress = True
	needsDestinationAddress = False
	needsControlAddressAmount = False
	def init_DuringDecoding(self, amount, maxBlock, extraData):
		self._amount = amount
		self._maxBlock = maxBlock
	def apply(self, state):
		self._cappedAmount = state.subtractFromBalance_Capped(self.sourceAddress, self._amount)
		state.forwardToFutureVersion(self._cappedAmount)
	def rewind(self, state):
		if hasattr(self, '_cappedAmount'):
			state.undoForwardToFutureVersion(self._cappedAmount)
			state.addToBalance(self.sourceAddress, self._cappedAmount)
			delattr(self, '_cappedAmount')
		elif state.hasNonZeroBalance(self.sourceAddress):
			# don't need undo info in this case
			state.undoForwardToFutureVersion(self._amount)
			state.addToBalance(self.sourceAddress, self._amount)
		else:
			raise CannotRewind()
	def __str__(self):
		result = '{} forwarded from {} to future network version (no longer accessible from this network version)'.format(self._amount, self.sourceAddress)
		if hasattr(self, '_cappedAmount'):
			result += ' (capped at {})'.format(self._cappedAmount)
		return result

def Decode(typeCode, amount, maxBlock, extraData):
	assert typeCode >= 0
	#for transactionClass in (Burn, Transfer):
		#if typeCode == transactionClass.typeCode:
			#result = transactionClass
	if typeCode == Burn.typeCode:
		result = Burn()
	elif typeCode == Transfer.typeCode:
		result = Transfer()
	elif typeCode < 128:
		return ForwardToFutureVersion()
	else:
		raise UnsupportedTransaction()
	result.init_DuringDecoding(amount, maxBlock, extraData)
	return result
