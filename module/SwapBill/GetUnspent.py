from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

class AddressNotSeeded(ExceptionReportedToUser):
	pass

class SourceLookup(object):
	def __init__(self):
		self._d = {}
	def add(self, address, amount, asInput):
		self._d[address] = (amount, asInput)
	def getTXInputForAddress(self, address):
		assert not hasattr(self, '_asInput')
		if not address in self._d:
			raise AddressNotSeeded(address)
		amount, asInput = self._d[address]
		self._asInput = asInput
		self._amount = amount
		self._address = address
		return asInput
	def lookupAmountForTXInput(self, txID, vOut):
		assert self._asInput == (txID, vOut)
		return self._amount
	def getSourceFor(self, txID, vOut):
		assert self._asInput == (txID, vOut)
		return self._address	
	#def lookupAddressForTXInput(self, address):
	def addressIsSeeded(self, address):
		return address in self._d

def GetUnspent(buildLayer, swapBillBalances):
	addresses, amounts, asInputs = buildLayer.getUnspent()
	amountsResult = []
	asInputsResult = []
	sourceLookup = SourceLookup()
	for i in range(len(addresses)):
		if addresses[i] in swapBillBalances:
			sourceLookup.add(addresses[i], amounts[i], asInputs[i])
		else:
			amountsResult.append(amounts[i])
			asInputsResult.append(asInputs[i])
	return (amountsResult, asInputsResult), sourceLookup

