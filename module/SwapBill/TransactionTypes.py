from __future__ import print_function
import struct, binascii
#import sys, inspect
from SwapBill import ControlAddressEncoding, Address

class UnsupportedTransaction(Exception):
	pass
class NotValidSwapBillTransaction(Exception):
	pass

class Transaction(object):
	pass

class Burn(object):
	typeCode = 0
	def init_FromUserRequirements(self, burnAmount, target):
		assert type(burnAmount) is int
		assert burnAmount > 0
		self.controlAddressAmount = burnAmount
		self.destination = target
	def init_DuringDecoding(self, amount, maxBlock, extraData, hostTX, sourceLookup):
		if amount != 0 or maxBlock != 0 or extraData != struct.pack("<B", 0) * 6:
			raise NotValidSwapBillTransaction("invalid burn address")
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destination = hostTX.outputPubKeyHash(1)
		self.controlAddressAmount = hostTX.outputAmount(0)
	def encode(self):
		return 0, 0, struct.pack("<B", 0) * 6
	def apply(self, state):
		state.create(self.controlAddressAmount)
		state.addToBalance(self.destination, self.controlAddressAmount)
	def __str__(self):
		return 'burn {} with credit to {}'.format(self.controlAddressAmount, binascii.hexlify(self.destination).decode())

class Transfer(object):
	typeCode = 1
	def init_FromUserRequirements(self, source, amount, destination, maxBlock=0xffffffff):
		assert type(amount) is int
		assert amount > 0
		self.source = source
		self.destination = destination
		self.amount = amount
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, amount, maxBlock, extraData, hostTX, sourceLookup):
		self.amount = amount
		self._maxBlock = maxBlock
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destination = hostTX.outputPubKeyHash(1)
	def encode(self):
		return self.amount, self._maxBlock, struct.pack("<B", 0) * 6
	def apply(self, state):
		#print('applying transfer, source:', self.source, 'amount:', self.amount)
		#cappedAmount = state.subtractFromBalance_Capped(self.source, self.amount)
		#state.addToBalance(self.destination, cappedAmount)
		state.requestTransfer(self.source, self.amount, self.destination)
	def __str__(self):
		result = 'transfer {} from {} to {}'.format(self.amount, binascii.hexlify(self.source).decode(), binascii.hexlify(self.destination).decode())
		return result

class LTCBuyOffer(object):
	typeCode = 2
	_formatStruct = struct.Struct('<LH')
	def init_FromUserRequirements(self, source, swapBillAmountOffered, exchangeRate, receivingDestination, offerMaxBlockOffset=0, maxBlock=0xffffffff):
		assert type(swapBillAmountOffered) is int
		assert swapBillAmountOffered >= 0
		assert type(offerMaxBlockOffset) is int
		assert offerMaxBlockOffset >= 0
		self.source = source
		self.destination = receivingDestination
		self.amount = swapBillAmountOffered
		self._exchangeRate = exchangeRate
		self._offerMaxBlockOffset = offerMaxBlockOffset
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, amount, maxBlock, extraData, hostTX, sourceLookup):
		self.amount = amount
		self._maxBlock = maxBlock
		assert type(extraData) == type(b'')
		assert len(extraData) == 6
		self._exchangeRate, self._offerMaxBlockOffset = self._formatStruct.unpack(extraData)
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destination = hostTX.outputPubKeyHash(1)
	def encode(self):
		return self.amount, self._maxBlock, self._formatStruct.pack(self._exchangeRate, self._offerMaxBlockOffset)
	def apply(self, state):
		if self._maxBlock >= 0xffffffff - self._offerMaxBlockOffset:
			expiry = 0xffffffff
		else:
			expiry = self._maxBlock + self._offerMaxBlockOffset
		state.requestAddLTCBuyOffer(self.source, self.amount, self._exchangeRate, expiry, self.destination)
	def __str__(self):
		result = 'LTC buy offer from {} funded with {} swapbill, exchange rate {}, receiving LTC at {}, maxBlock offset {}'.format(binascii.hexlify(self.source).decode(), self.amount, self._exchangeRate, binascii.hexlify(self.destination).decode(), self._offerMaxBlockOffset)
		return result

class LTCSellOffer(object):
	typeCode = 3
	depositMultiplier = 16
	_formatStruct = struct.Struct('<LH')
	def init_FromUserRequirements(self, source, swapBillDesired, exchangeRate, offerMaxBlockOffset=0, maxBlock=0xffffffff):
		assert type(swapBillDesired) is int
		assert swapBillDesired > 0
		assert type(offerMaxBlockOffset) is int
		assert offerMaxBlockOffset >= 0
		self.source = source
		self.amount = swapBillDesired
		self._exchangeRate = exchangeRate
		self._offerMaxBlockOffset = offerMaxBlockOffset
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, amount, maxBlock, extraData, hostTX, sourceLookup):
		self.amount = amount
		self._maxBlock = maxBlock
		assert type(extraData) == type(b'')
		assert len(extraData) == 6
		self._exchangeRate, self._offerMaxBlockOffset = self._formatStruct.unpack(extraData)
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
	def consumedAmount(self):
		return self.amount // self.depositMultiplier
	def encode(self):
		return self.amount, self._maxBlock, self._formatStruct.pack(self._exchangeRate, self._offerMaxBlockOffset)
	def apply(self, state):
		if self._maxBlock >= 0xffffffff - self._offerMaxBlockOffset:
			expiry = 0xffffffff
		else:
			expiry = self._maxBlock + self._offerMaxBlockOffset
		deposit = self.consumedAmount()
		state.requestAddLTCSellOffer(self.source, self.amount, deposit, self._exchangeRate, expiry)
	def __str__(self):
		result = 'LTC sell offer from {}, for {} swapbill, exchange rate {}, maxBlock offset {}'.format(binascii.hexlify(self.source).decode(), self.amount, self._exchangeRate, self._offerMaxBlockOffset)
		return result

class LTCExchangeCompletion(object):
	typeCode = 4
	_formatStruct = struct.Struct('<HL')
	def init_FromUserRequirements(self, ltcAmount, destination, pendingExchangeIndex, maxBlock=0xffffffff):
		self.amount = 0
		self.destination = destination
		self.destinationAmount = ltcAmount
		self._maxBlock = maxBlock
		self._pendingExchangeIndex = pendingExchangeIndex
	def init_DuringDecoding(self, amount, maxBlock, extraData, hostTX, sourceLookup):
		#print('LTCExchangeCompletion being decoded')
		self.amount = amount
		self._maxBlock = maxBlock
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() >= 2:
			self.destination = hostTX.outputPubKeyHash(1)
			self.destinationAmount = hostTX.outputAmount(1)
		else:
			## we have to accept this
			## since clients before this transaction type would have accepted the amount and accounted as 'forwarded'
			self.destination = b'0' * 20
			self.destinationAmount = 0
		low, high = self._formatStruct.unpack(extraData)
		self._pendingExchangeIndex = (high << 16) + low
	def encode(self):
		low = (self._pendingExchangeIndex & 0xffff)
		high = (self._pendingExchangeIndex >> 16)
		return self.amount, self._maxBlock, self._formatStruct.pack(low, high)
	def apply(self, state):
		#print('LTCExchangeCompletion being applied')
		#print(self)
		state.completeExchange(self._pendingExchangeIndex, self.destination, self.destinationAmount)
	def __str__(self):
		result = 'LTC exchange completion payment for pending exchange index {} of {} LTC to {}'.format(self._pendingExchangeIndex, self.destinationAmount, binascii.hexlify(self.destination).decode())
		return result

class ForwardToFutureVersion(object):
	## this transaction is designed to be created only during decoding
	## (and so omits some stuff found in other transaction types)
	def init_DuringDecoding(self, amount, maxBlock, extraData, hostTX, sourceLookup):
		self.amount = amount
		self._maxBlock = maxBlock
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
	def apply(self, state):
		cappedAmount = state.subtractFromBalance_Capped(self.source, self.amount)
		state.forwardToFutureVersion(cappedAmount)
	def __str__(self):
		result = '{} forwarded from {} to future network version (no longer accessible from this network version)'.format(self.amount, self.source.__repr__())
		return result

def _decode(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
	assert typeCode >= 0
	#for transactionClass in (Burn, Transfer):
		#if typeCode == transactionClass.typeCode:
			#result = transactionClass
	if typeCode == Burn.typeCode:
		result = Burn()
	elif typeCode == Transfer.typeCode:
		result = Transfer()
	elif typeCode == LTCBuyOffer.typeCode:
		result = LTCBuyOffer()
	elif typeCode == LTCSellOffer.typeCode:
		result = LTCSellOffer()
	elif typeCode == LTCExchangeCompletion.typeCode:
		result = LTCExchangeCompletion()
	elif typeCode < 128:
		return ForwardToFutureVersion()
	else:
		raise UnsupportedTransaction()
	result.init_DuringDecoding(amount, maxBlock, extraData, hostTX, sourceLookup)
	return result

## TODO get rid of the needsXXX stuff now and replace this with queries from directly within the swap bill tx type init
def Decode(sourceLookup, hostTX):
	typeCode, amount, maxBlock, extraData = ControlAddressEncoding.Decode(hostTX.outputPubKeyHash(0))
	return _decode(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup)
