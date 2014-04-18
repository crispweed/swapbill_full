from __future__ import print_function
import struct, binascii
from SwapBill import ControlAddressEncoding, Address

class UnsupportedTransaction(Exception):
	pass
class NotValidSwapBillTransaction(Exception):
	pass
class DoesntMatch(Exception):
	pass

class Burn(object):
	_typeCode = 0
	def init_FromUserRequirements(self, burnAmount, target):
		assert type(burnAmount) is int
		assert burnAmount > 0
		self.controlAddressAmount = burnAmount
		self.destinations = (target,)
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode != self._typeCode:
			raise DoesntMatch()
		if amount != 0 or maxBlock != 0 or extraData != struct.pack("<B", 0) * 6:
			raise NotValidSwapBillTransaction("invalid burn address")
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destinations = (hostTX.outputPubKeyHash(1),)
		self.controlAddressAmount = hostTX.outputAmount(0)
	def encode(self):
		return self._typeCode, 0, 0, struct.pack("<B", 0) * 6
	def details(self):
		return {'amount':self.controlAddressAmount, 'destinationAccount':self.destinations[0]}

class Transfer(object):
	_typeCode = 1
	def init_FromUserRequirements(self, source, amount, destination, maxBlock=0xffffffff):
		assert type(amount) is int
		assert amount > 0
		self.source = source
		self.destinations = (destination,)
		self.amount = amount
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode != self._typeCode:
			raise DoesntMatch()
		self.amount = amount
		self._maxBlock = maxBlock
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destinations = (hostTX.outputPubKeyHash(1),)
	def encode(self):
		return self._typeCode, self.amount, self._maxBlock, struct.pack("<B", 0) * 6
	def details(self):
		return {'sourceAccount':self.source, 'amount':self.amount, 'destinationAccount':self.destinations[0], 'maxBlock':self._maxBlock}

class LTCBuyOffer(object):
	_typeCode = 2
	_formatStruct = struct.Struct('<LH')
	def init_FromUserRequirements(self, source, change, refund, swapBillAmountOffered, exchangeRate, receivingDestination, offerMaxBlockOffset=0, maxBlock=0xffffffff):
		assert type(swapBillAmountOffered) is int
		assert swapBillAmountOffered >= 0
		assert type(offerMaxBlockOffset) is int
		assert offerMaxBlockOffset >= 0
		self.source = source
		self.destinations = [receivingDestination, change, refund]
		self.amount = swapBillAmountOffered
		self._exchangeRate = exchangeRate
		self._offerMaxBlockOffset = offerMaxBlockOffset
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode != self._typeCode:
			raise DoesntMatch()
		self.amount = amount
		self._maxBlock = maxBlock
		assert type(extraData) == type(b'')
		assert len(extraData) == 6
		self._exchangeRate, self._offerMaxBlockOffset = self._formatStruct.unpack(extraData)
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destinations = [hostTX.outputPubKeyHash(1)]
		if hostTX.numberOfOutputs() >= 3:
			self.destinations.append(hostTX.outputPubKeyHash(2))
		else:
			self.destinations.append(self.source)
		if hostTX.numberOfOutputs() >= 4:
			self.destinations.append(hostTX.outputPubKeyHash(3))
		else:
			self.destinations.append(self.destinations[-1])
	def encode(self):
		return self._typeCode, self.amount, self._maxBlock, self._formatStruct.pack(self._exchangeRate, self._offerMaxBlockOffset)
	def details(self):
		if self._maxBlock >= 0xffffffff - self._offerMaxBlockOffset:
			expiry = 0xffffffff
		else:
			expiry = self._maxBlock + self._offerMaxBlockOffset
		return {'sourceAccount':self.source, 'changeAccount':self.destinations[1], 'refundAccount':self.destinations[2], 'swapBillOffered':self.amount, 'exchangeRate':self._exchangeRate, 'expiry':expiry, 'receivingAccount':self.destinations[0], 'refundAccount':self.destinations[1], 'maxBlock':self._maxBlock}

class LTCSellOffer(object):
	_typeCode = 3
	depositMultiplier = 16
	_formatStruct = struct.Struct('<LH')
	def init_FromUserRequirements(self, source, change, swapBillDesired, exchangeRate, receivingDestination, offerMaxBlockOffset=0, maxBlock=0xffffffff):
		assert type(swapBillDesired) is int
		assert swapBillDesired > 0
		assert type(offerMaxBlockOffset) is int
		assert offerMaxBlockOffset >= 0
		self.source = source
		self.destinations = [receivingDestination, change]
		self.amount = swapBillDesired
		self._exchangeRate = exchangeRate
		self._offerMaxBlockOffset = offerMaxBlockOffset
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode != self._typeCode:
			raise DoesntMatch()
		self.amount = amount
		self._maxBlock = maxBlock
		assert type(extraData) == type(b'')
		assert len(extraData) == 6
		self._exchangeRate, self._offerMaxBlockOffset = self._formatStruct.unpack(extraData)
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() >= 2:
			self.destinations = [hostTX.outputPubKeyHash(2)]
		else:
			self.destinations = [self.source]
		if hostTX.numberOfOutputs() >= 3:
			self.destinations.append(hostTX.outputPubKeyHash(2))
		else:
			self.destinations.append(self.destinations[-1])
	def encode(self):
		return self._typeCode, self.amount, self._maxBlock, self._formatStruct.pack(self._exchangeRate, self._offerMaxBlockOffset)
	def details(self):
		if self._maxBlock >= 0xffffffff - self._offerMaxBlockOffset:
			expiry = 0xffffffff
		else:
			expiry = self._maxBlock + self._offerMaxBlockOffset
		return {'sourceAccount':self.source, 'changeAccount':self.destinations[1], 'receivingAccount':self.destinations[0], 'swapBillDesired':self.amount, 'exchangeRate':self._exchangeRate, 'expiry':expiry, 'maxBlock':self._maxBlock}

class LTCExchangeCompletion(object):
	_typeCode = 4
	_formatStruct = struct.Struct('<HL')
	def init_FromUserRequirements(self, ltcAmount, destination, pendingExchangeIndex):
		self.amount = 0
		self.destinations = (destination,)
		self.destinationAmounts = (ltcAmount,)
		self._pendingExchangeIndex = pendingExchangeIndex
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode != self._typeCode:
			raise DoesntMatch()
		self.amount = amount
		## note that maxBlock is currently ignored here
		## (could be required to be a specific value)
		if hostTX.numberOfOutputs() < 2:
			raise NotValidSwapBillTransaction()
		self.destinations = (hostTX.outputPubKeyHash(1),)
		self.destinationAmounts = (hostTX.outputAmount(1),)
		low, high = self._formatStruct.unpack(extraData)
		self._pendingExchangeIndex = (high << 16) + low
	def encode(self):
		low = (self._pendingExchangeIndex & 0xffff)
		high = (self._pendingExchangeIndex >> 16)
		return self._typeCode, self.amount, 0xffffffff, self._formatStruct.pack(low, high)
	def details(self):
		return {'pendingExchangeIndex':self._pendingExchangeIndex, 'destinationAccount':self.destinations[0], 'destinationAmount':self.destinationAmounts[0]}

class Pay(object):
	_typeCode = 5
	def init_FromUserRequirements(self, source, amount, destination, change, maxBlock=0xffffffff):
		assert type(amount) is int
		assert amount > 0
		self.source = source
		self.destinations = (destination, change)
		self.amount = amount
		self._maxBlock = maxBlock
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode != self._typeCode:
			raise DoesntMatch()
		self.amount = amount
		self._maxBlock = maxBlock
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		if hostTX.numberOfOutputs() < 3:
			raise NotValidSwapBillTransaction()
		self.destinations = (hostTX.outputPubKeyHash(1), hostTX.outputPubKeyHash(2))
	def encode(self):
		return self._typeCode, self.amount, self._maxBlock, struct.pack("<B", 0) * 6
	def details(self):
		return {'sourceAccount':self.source, 'amount':self.amount, 'destinationAccount':self.destinations[0], 'changeAccount':self.destinations[1], 'maxBlock':self._maxBlock}


class ForwardToFutureNetworkVersion(object):
	## this transaction is designed to be created only during decoding
	## (and so omits some stuff found in other transaction types)
	def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		if typeCode >= 128:
			raise DoesntMatch()
		self.amount = amount
		self._maxBlock = maxBlock
		i = hostTX.numberOfInputs() - 1
		self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
	def details(self):
		return {'sourceAccount':self.source, 'amount':self.amount, 'maxBlock':self._maxBlock}

def _decode(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
	for c in (Burn, Transfer, LTCBuyOffer, LTCSellOffer, LTCExchangeCompletion, Pay, ForwardToFutureNetworkVersion):
		result = c()
		try:
			result.init_DuringDecoding(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup)
			return result
		except DoesntMatch:
			pass
	raise UnsupportedTransaction()

def Decode(sourceLookup, hostTX):
	typeCode, amount, maxBlock, extraData = ControlAddressEncoding.Decode(hostTX.outputPubKeyHash(0))
	return _decode(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup)
