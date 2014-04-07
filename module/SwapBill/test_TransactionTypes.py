from __future__ import print_function
import unittest, struct
from SwapBill import TransactionTypes

class MockState(object):
	def __init__(self):
		self._log = []
## TODO: can the following be replaced by something automatic?
	def create(self, amount):
		self._log.append(('create', amount))
	def undoCreate(self, amount):
		self._log.append(('undoCreate', amount))
	def addToBalance(self, target, amount):
		self._log.append(('addToBalance', target, amount))
	def subtractFromBalance(self, target, amount):
		self._log.append(('subtractFromBalance', target, amount))
	def subtractFromBalance_Capped(self, target, amount):
		self._log.append(('subtractFromBalance_Capped', target, amount))
		return 1

class Test(unittest.TestCase):
	def test(self):
		burn = TransactionTypes.Burn()
		burn.init_FromUserRequirements(burnAmount=10, targetAddress='a')
		assert(str(burn) == 'burn 10 with credit to a')
		s = MockState()
		burn.apply(s)
		assert s._log == [('create', 10),('addToBalance', 'a', 10)]
		assert burn.typeCode == 0
		assert burn.controlAddressAmount == 10
		assert burn.destinationAddress == 'a'
		assert not hasattr(burn, 'sourceAddress')
		assert not hasattr(burn, 'destinationAmount')
		assert burn.encode() == (0, 0, struct.pack("<B", 0) * 6)
		burn.rewind(s)
		assert s._log == [('create', 10),('addToBalance', 'a', 10),('subtractFromBalance', 'a', 10),('undoCreate', 10)]

		transfer = TransactionTypes.Transfer()
		transfer.init_FromUserRequirements(fromAddress='bob', amount=10, toAddress='alice')
		assert(str(transfer) == 'transfer 10 from bob to alice')
		s = MockState()
		transfer.apply(s)
		#print(s._log)
		assert s._log == [('subtractFromBalance_Capped', 'bob', 10),('addToBalance', 'alice', 1)]
		assert transfer.typeCode == 1
		assert transfer.sourceAddress == 'bob'
		assert transfer.destinationAddress == 'alice'
		assert transfer._maxBlock == 0xffffffff
		assert not hasattr(transfer, 'controlAddressAmount')
		amount, maxBlock, extraData = transfer.encode()
		assert amount == 10
		assert maxBlock == 0xffffffff
		assert extraData == struct.pack("<B", 0) * 6 ## can be changed
		transfer.rewind(s)
		#print(s._log)
		assert s._log == [('subtractFromBalance_Capped', 'bob', 10),('addToBalance', 'alice', 1),('subtractFromBalance', 'alice', 1),('addToBalance', 'bob', 1)]

		decodedBurn = TransactionTypes.Decode(burn.typeCode, 0, 0, struct.pack("<B", 0) * 6)
		assert decodedBurn.needsSourceAddress == False
		assert decodedBurn.needsDestinationAddress == True
		assert decodedBurn.needsControlAddressAmount == True
		decodedBurn.destinationAddress = 'a'
		decodedBurn.controlAddressAmount = 10
		assert str(decodedBurn) == 'burn 10 with credit to a'
		assert decodedBurn.__dict__ == burn.__dict__

		## different extra data for burn should raise an exception
		try:
			decodedBurn = TransactionTypes.Decode(burn.typeCode, 0, 0, struct.pack("<B", 99) * 6)
		except TransactionTypes.InvalidTransaction:
			pass
		else:
			raise Exception('Failed to throw exception when decoding bad burn')

		decodedTransfer = TransactionTypes.Decode(transfer.typeCode, 10, 0xffffffff, struct.pack("<B", 0) * 6)
		assert decodedTransfer.needsSourceAddress == True
		assert decodedTransfer.needsDestinationAddress == True
		assert decodedTransfer.needsControlAddressAmount == False
		decodedTransfer.sourceAddress = 'bob'
		decodedTransfer.destinationAddress = 'alice'
		assert decodedTransfer._maxBlock == 0xffffffff ## TODO: implement this properly, or move to separate transaction type!
		assert str(decodedTransfer) == 'transfer 10 from bob to alice'
		assert decodedTransfer.__dict__ == transfer.__dict__

		## as before, but different extra data (should be ignored)
		decodedTransfer = TransactionTypes.Decode(transfer.typeCode, 10, 0xffffffff, struct.pack("<B", 99) * 6)
		assert decodedTransfer.needsSourceAddress == True
		assert decodedTransfer.needsDestinationAddress == True
		assert decodedTransfer.needsControlAddressAmount == False
		decodedTransfer.sourceAddress = 'bob'
		decodedTransfer.destinationAddress = 'alice'
		assert decodedTransfer._maxBlock == 0xffffffff ## TODO: implement this properly, or move to separate transaction type!
		assert str(decodedTransfer) == 'transfer 10 from bob to alice'
		assert decodedTransfer.__dict__ == transfer.__dict__
