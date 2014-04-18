from __future__ import print_function
import struct, binascii
from SwapBill import ControlAddressEncoding, Address, HostTransaction

class UnsupportedTransaction(Exception):
	pass
class NotValidSwapBillTransaction(Exception):
	pass

def ToStateTransaction(sourceLookup, tx):
	typeCode, amount, maxBlock, extraData = ControlAddressEncoding.Decode(tx.outputPubKeyHash(0))
	exchangeRate, maxBlockOffset = struct.unpack('<LH', extraData)
	try:
		if typeCode == 0:
			return 'Burn', {'amount':tx.outputAmount(0), 'destinationAccount':tx.outputPubKeyHash(1)}
		if typeCode == 1:
			return 'Pay', {
			    'sourceAccount':sourceLookup.first(tx), 'amount':amount,
			    'destinationAccount':tx.outputPubKeyHash(1), 'changeAccount':tx.outputPubKeyHash(2),
			    'maxBlock':maxBlock
				}
		if typeCode == 2: # reuses source address
			return 'Pay', {
			    'sourceAccount':sourceLookup.first(tx), 'amount':amount,
			    'destinationAccount':tx.outputPubKeyHash(1), 'changeAccount':sourceLookup.first(tx),
			    'maxBlock':maxBlock
				}
		if typeCode == 3:
			return 'LTCBuyOffer', {
			    'sourceAccount':sourceLookup.first(tx), 'swapBillOffered':amount,
			    'receivingAccount':tx.outputPubKeyHash(1), 'changeAccount':tx.outputPubKeyHash(2), 'refundAccount':tx.outputPubKeyHash(3),
			    'exchangeRate':exchangeRate, 'maxBlockOffset':maxBlockOffset, 'maxBlock':maxBlock
				}
		if typeCode == 4: # reuses source address
			return 'LTCBuyOffer', {
			    'sourceAccount':sourceLookup.first(tx), 'swapBillOffered':amount,
			    'receivingAccount':tx.outputPubKeyHash(1), 'changeAccount':sourceLookup.first(tx), 'refundAccount':sourceLookup.first(tx),
			    'exchangeRate':exchangeRate, 'maxBlockOffset':maxBlockOffset, 'maxBlock':maxBlock
				}
		if typeCode == 5:
			return 'LTCSellOffer', {
			    'sourceAccount':sourceLookup.first(tx), 'swapBillDesired':amount,
			    'receivingAccount':tx.outputPubKeyHash(1), 'changeAccount':tx.outputPubKeyHash(2),
			    'exchangeRate':exchangeRate, 'maxBlockOffset':maxBlockOffset, 'maxBlock':maxBlock
				}
		if typeCode == 6: # reuses source address
			return 'LTCSellOffer', {
			    'sourceAccount':sourceLookup.first(tx), 'swapBillDesired':amount,
			    'receivingAccount':tx.outputPubKeyHash(1), 'changeAccount':sourceLookup.first(tx),
			    'exchangeRate':exchangeRate, 'maxBlockOffset':maxBlockOffset, 'maxBlock':maxBlock
				}
		if typeCode == 7:
			low, high = struct.unpack('<HL', extraData)
			pendingExchangeIndex = (high << 16) + low
			return 'LTCExchangeCompletion', {'pendingExchangeIndex':pendingExchangeIndex, 'destinationAccount':tx.outputPubKeyHash(1), 'destinationAmount':tx.outputAmount(1)}
		if typeCode < 128:
			return 'ForwardToFutureNetworkVersion', {'sourceAccount':sourceLookup.first(tx), 'amount':amount, 'maxBlock':maxBlock}
	except IndexError:
		raise NotValidSwapBillTransaction()
	else:
		raise UnsupportedTransaction()

def _addInput(tx, inputProvider, sourceAccount):
	txID, vout = inputProvider.lookupUnspentFor(sourceAccount)
	tx.addInput(txID, vout)

def FromStateTransaction(transactionType, details, inputProvider):
	tx = HostTransaction.InMemoryTransaction()
	if transactionType == 'Burn':
		controlAddress = ControlAddressEncoding.Encode(0, 0, 0, struct.pack("<B", 0) * 6)
		tx.addOutput(controlAddress, details['amount'])
		tx.addOutput(details['destinationAccount'])
	elif transactionType == 'Pay':
		source = details['sourceAccount']
		change = details['changeAccount']
		typeCode = 1
		if change == source:
			typeCode += 1
		controlAddress = ControlAddressEncoding.Encode(typeCode, details['amount'], details['maxBlock'], struct.pack("<B", 0) * 6)
		tx.addOutput(controlAddress)
		tx.addOutput(details['destinationAccount'])
		if change != source:
			tx.addOutput(change)
		_addInput(tx, inputProvider, source)
	elif transactionType == 'LTCBuyOffer':
		source = details['sourceAccount']
		change = details['changeAccount']
		refund = details['refundAccount']
		typeCode = 3
		if change == source and refund == source:
			typeCode += 1
		extraData = struct.pack('<LH', details['exchangeRate'], details['maxBlockOffset'])
		controlAddress = ControlAddressEncoding.Encode(typeCode, details['swapBillOffered'], details['maxBlock'], extraData)
		tx.addOutput(controlAddress)
		tx.addOutput(details['receivingAccount'])
		if typeCode == 3:
			tx.addOutput(change)
			tx.addOutput(refund)
		_addInput(tx, inputProvider, source)
	elif transactionType == 'LTCSellOffer':
		source = details['sourceAccount']
		change = details['changeAccount']
		typeCode = 5
		if change == source:
			typeCode += 1
		extraData = struct.pack('<LH', details['exchangeRate'], details['maxBlockOffset'])
		controlAddress = ControlAddressEncoding.Encode(typeCode, details['swapBillDesired'], details['maxBlock'], extraData)
		tx.addOutput(controlAddress)
		tx.addOutput(details['receivingAccount'])
		if typeCode == 5:
			tx.addOutput(change)
		_addInput(tx, inputProvider, source)
	elif transactionType == 'LTCExchangeCompletion':
		low = (details['pendingExchangeIndex'] & 0xffff)
		high = (details['pendingExchangeIndex'] >> 16)
		extraData = struct.pack('<HL', low, high)
		controlAddress = ControlAddressEncoding.Encode(7, 0, 0xffffffff, extraData)
		tx.addOutput(controlAddress)
		tx.addOutput(details['destinationAccount'])
	else:
		raise Exception('Unexpected state transaction.')
	return tx

#class Burn(object):
	#_typeCode = 0
	#def init_FromUserRequirements(self, burnAmount, target):
		#assert type(burnAmount) is int
		#assert burnAmount > 0
		#self.controlAddressAmount = burnAmount
		#self.destinations = (target,)
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode != self._typeCode:
			#raise DoesntMatch()
		#if amount != 0 or maxBlock != 0 or extraData != struct.pack("<B", 0) * 6:
			#raise NotValidSwapBillTransaction("invalid burn address")
		#if hostTX.numberOfOutputs() < 2:
			#raise NotValidSwapBillTransaction()
		#self.destinations = (hostTX.outputPubKeyHash(1),)
		#self.controlAddressAmount = hostTX.outputAmount(0)
	#def encode(self):
		#return self._typeCode, 0, 0, struct.pack("<B", 0) * 6
	#def details(self):
		#return {'amount':self.controlAddressAmount, 'destinationAccount':self.destinations[0]}

#class Pay(object):
	#_typeCode = 5
	#def init_FromUserRequirements(self, source, amount, destination, change, maxBlock=0xffffffff):
		#assert type(amount) is int
		#assert amount > 0
		#self.source = source
		#self.destinations = (destination, change)
		#self.amount = amount
		#self._maxBlock = maxBlock
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode != self._typeCode:
			#raise DoesntMatch()
		#self.amount = amount
		#self._maxBlock = maxBlock
		#i = hostTX.numberOfInputs() - 1
		#self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		#if hostTX.numberOfOutputs() < 3:
			#raise NotValidSwapBillTransaction()
		#self.destinations = (hostTX.outputPubKeyHash(1), hostTX.outputPubKeyHash(2))
	#def encode(self):
		#return self._typeCode, self.amount, self._maxBlock, struct.pack("<B", 0) * 6
	#def details(self):
		#return {'sourceAccount':self.source, 'amount':self.amount, 'destinationAccount':self.destinations[0], 'changeAccount':self.destinations[1], 'maxBlock':self._maxBlock}


#class Transfer(object):
	#_typeCode = 1
	#def init_FromUserRequirements(self, source, amount, destination, maxBlock=0xffffffff):
		#assert type(amount) is int
		#assert amount > 0
		#self.source = source
		#self.destinations = (destination,)
		#self.amount = amount
		#self._maxBlock = maxBlock
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode != self._typeCode:
			#raise DoesntMatch()
		#self.amount = amount
		#self._maxBlock = maxBlock
		#i = hostTX.numberOfInputs() - 1
		#self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		#if hostTX.numberOfOutputs() < 2:
			#raise NotValidSwapBillTransaction()
		#self.destinations = (hostTX.outputPubKeyHash(1),)
	#def encode(self):
		#return self._typeCode, self.amount, self._maxBlock, struct.pack("<B", 0) * 6
	#def details(self):
		#return {'sourceAccount':self.source, 'amount':self.amount, 'destinationAccount':self.destinations[0], 'maxBlock':self._maxBlock}

#class LTCBuyOffer(object):
	#_typeCode = 2
	#_formatStruct = struct.Struct('<LH')
	#def init_FromUserRequirements(self, source, change, refund, swapBillAmountOffered, exchangeRate, receivingDestination, offerMaxBlockOffset=0, maxBlock=0xffffffff):
		#assert type(swapBillAmountOffered) is int
		#assert swapBillAmountOffered >= 0
		#assert type(offerMaxBlockOffset) is int
		#assert offerMaxBlockOffset >= 0
		#self.source = source
		#self.destinations = [receivingDestination, change, refund]
		#self.amount = swapBillAmountOffered
		#self._exchangeRate = exchangeRate
		#self._offerMaxBlockOffset = offerMaxBlockOffset
		#self._maxBlock = maxBlock
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode != self._typeCode:
			#raise DoesntMatch()
		#self.amount = amount
		#self._maxBlock = maxBlock
		#assert type(extraData) == type(b'')
		#assert len(extraData) == 6
		#self._exchangeRate, self._offerMaxBlockOffset = self._formatStruct.unpack(extraData)
		#i = hostTX.numberOfInputs() - 1
		#self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		#if hostTX.numberOfOutputs() < 2:
			#raise NotValidSwapBillTransaction()
		#self.destinations = [hostTX.outputPubKeyHash(1)]
		#if hostTX.numberOfOutputs() >= 3:
			#self.destinations.append(hostTX.outputPubKeyHash(2))
		#else:
			#self.destinations.append(self.source)
		#if hostTX.numberOfOutputs() >= 4:
			#self.destinations.append(hostTX.outputPubKeyHash(3))
		#else:
			#self.destinations.append(self.destinations[-1])
	#def encode(self):
		#return self._typeCode, self.amount, self._maxBlock, self._formatStruct.pack(self._exchangeRate, self._offerMaxBlockOffset)
	#def details(self):
		#if self._maxBlock >= 0xffffffff - self._offerMaxBlockOffset:
			#expiry = 0xffffffff
		#else:
			#expiry = self._maxBlock + self._offerMaxBlockOffset
		#return {'sourceAccount':self.source, 'changeAccount':self.destinations[1], 'refundAccount':self.destinations[2], 'swapBillOffered':self.amount, 'exchangeRate':self._exchangeRate, 'expiry':expiry, 'receivingAccount':self.destinations[0], 'refundAccount':self.destinations[1], 'maxBlock':self._maxBlock}

#class LTCSellOffer(object):
	#_typeCode = 3
	#depositMultiplier = 16
	#_formatStruct = struct.Struct('<LH')
	#def init_FromUserRequirements(self, source, change, swapBillDesired, exchangeRate, receivingDestination, offerMaxBlockOffset=0, maxBlock=0xffffffff):
		#assert type(swapBillDesired) is int
		#assert swapBillDesired > 0
		#assert type(offerMaxBlockOffset) is int
		#assert offerMaxBlockOffset >= 0
		#self.source = source
		#self.destinations = [receivingDestination, change]
		#self.amount = swapBillDesired
		#self._exchangeRate = exchangeRate
		#self._offerMaxBlockOffset = offerMaxBlockOffset
		#self._maxBlock = maxBlock
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode != self._typeCode:
			#raise DoesntMatch()
		#self.amount = amount
		#self._maxBlock = maxBlock
		#assert type(extraData) == type(b'')
		#assert len(extraData) == 6
		#self._exchangeRate, self._offerMaxBlockOffset = self._formatStruct.unpack(extraData)
		#i = hostTX.numberOfInputs() - 1
		#self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
		#if hostTX.numberOfOutputs() >= 2:
			#self.destinations = [hostTX.outputPubKeyHash(2)]
		#else:
			#self.destinations = [self.source]
		#if hostTX.numberOfOutputs() >= 3:
			#self.destinations.append(hostTX.outputPubKeyHash(2))
		#else:
			#self.destinations.append(self.destinations[-1])
	#def encode(self):
		#return self._typeCode, self.amount, self._maxBlock, self._formatStruct.pack(self._exchangeRate, self._offerMaxBlockOffset)
	#def details(self):
		#if self._maxBlock >= 0xffffffff - self._offerMaxBlockOffset:
			#expiry = 0xffffffff
		#else:
			#expiry = self._maxBlock + self._offerMaxBlockOffset
		#return {'sourceAccount':self.source, 'changeAccount':self.destinations[1], 'receivingAccount':self.destinations[0], 'swapBillDesired':self.amount, 'exchangeRate':self._exchangeRate, 'expiry':expiry, 'maxBlock':self._maxBlock}

#class LTCExchangeCompletion(object):
	#_typeCode = 4
	#_formatStruct = struct.Struct('<HL')
	#def init_FromUserRequirements(self, ltcAmount, destination, pendingExchangeIndex):
		#self.amount = 0
		#self.destinations = (destination,)
		#self.destinationAmounts = (ltcAmount,)
		#self._pendingExchangeIndex = pendingExchangeIndex
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode != self._typeCode:
			#raise DoesntMatch()
		#self.amount = amount
		### note that maxBlock is currently ignored here
		### (could be required to be a specific value)
		#if hostTX.numberOfOutputs() < 2:
			#raise NotValidSwapBillTransaction()
		#self.destinations = (hostTX.outputPubKeyHash(1),)
		#self.destinationAmounts = (hostTX.outputAmount(1),)
		#low, high = self._formatStruct.unpack(extraData)
		#self._pendingExchangeIndex = (high << 16) + low
	#def encode(self):
		#low = (self._pendingExchangeIndex & 0xffff)
		#high = (self._pendingExchangeIndex >> 16)
		#return self._typeCode, self.amount, 0xffffffff, self._formatStruct.pack(low, high)
	#def details(self):
		#return {'pendingExchangeIndex':self._pendingExchangeIndex, 'destinationAccount':self.destinations[0], 'destinationAmount':self.destinationAmounts[0]}



#class ForwardToFutureNetworkVersion(object):
	### this transaction is designed to be created only during decoding
	### (and so omits some stuff found in other transaction types)
	#def init_DuringDecoding(self, typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
		#if typeCode >= 128:
			#raise DoesntMatch()
		#self.amount = amount
		#self._maxBlock = maxBlock
		#i = hostTX.numberOfInputs() - 1
		#self.source = sourceLookup.getSourceFor(hostTX.inputTXID(i), hostTX.inputVOut(i))
	#def details(self):
		#return {'sourceAccount':self.source, 'amount':self.amount, 'maxBlock':self._maxBlock}

#def _decode(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup):
	#for c in (Burn, Transfer, LTCBuyOffer, LTCSellOffer, LTCExchangeCompletion, Pay, ForwardToFutureNetworkVersion):
		#result = c()
		#try:
			#result.init_DuringDecoding(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup)
			#return result
		#except DoesntMatch:
			#pass
	#raise UnsupportedTransaction()

#def Decode(sourceLookup, hostTX):
	#typeCode, amount, maxBlock, extraData = ControlAddressEncoding.Decode(hostTX.outputPubKeyHash(0))
	#return _decode(typeCode, amount, maxBlock, extraData, hostTX, sourceLookup)