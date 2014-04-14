from __future__ import print_function
import unittest, struct, binascii
from SwapBill import TransactionTypes

class MockState(object):
	def __init__(self):
		self._log = []
## TODO: can the following be replaced by something automatic?
	def create(self, amount):
		self._log.append(('create', amount))
	def addToBalance(self, target, amount):
		self._log.append(('addToBalance', target, amount))
	def subtractFromBalance(self, target, amount):
		self._log.append(('subtractFromBalance', target, amount))
	def requestTransfer(self, source, amount, destination):
		self._log.append(('requestTransfer', source, amount, destination))
	def requestAddLTCBuyOffer(self, address, amount, exchangeRate, expiry, receivingAddress):
		self._log.append(('requestAddLTCBuyOffer', address, amount, exchangeRate, expiry, receivingAddress))
	def requestAddLTCSellOffer(self, address, amount, depositAmount, exchangeRate, expiry):
		self._log.append(('requestAddLTCSellOffer', address, amount, depositAmount, exchangeRate, expiry))

class MockHostTX(object):
	def __init__(self, tx):
		self._inputIDs = []
		self._inputVOuts = []
		self._outputHashes = []
		self._outputAmounts = []
		if hasattr(tx, 'source'):
			self._inputIDs.append('TXID')
			self._inputVOuts.append(0)
			self._source = tx.source
		self._outputHashes.append(b'controlAddressData')
		if hasattr(tx, 'controlAddressAmount'):
			self._outputAmounts.append(tx.controlAddressAmount)
		else:
			self._outputAmounts.append(0)
		if hasattr(tx, 'destination'):
			self._outputHashes.append(tx.destination)
			self._outputAmounts.append(0)
	def numberOfInputs(self):
		return len(self._inputIDs)
	def inputTXID(self, i):
		return self._inputIDs[i]
	def inputVOut(self, i):
		return self._inputVOuts[i]
	def numberOfOutputs(self):
		return len(self._outputHashes)
	def outputPubKeyHash(self, i):
		return self._outputHashes[i]
	def outputAmount(self, i):
		return self._outputAmounts[i]
	## and this also serves as a 'source lookup'
	def getSourceFor(self, txID, vOut):
		assert txID == 'TXID'
		assert vOut == 0
		return self._source

class Test(unittest.TestCase):
	def test(self):
		burn = TransactionTypes.Burn()
		a = binascii.unhexlify(b'0a')
		burn.init_FromUserRequirements(burnAmount=10, target=a)
		self.assertEqual(str(burn), 'burn 10 with credit to 0a')
		s = MockState()
		burn.apply(s)
		self.assertEqual(s._log, [('create', 10),('addToBalance', a, 10)])
		self.assertEqual(burn.typeCode, 0)
		self.assertEqual(burn.controlAddressAmount, 10)
		self.assertEqual(burn.destination, a)
		assert not hasattr(burn, 'source')
		assert not hasattr(burn, 'destinationAmount')
		self.assertEqual(burn.encode(), (0, 0, struct.pack("<B", 0) * 6))

		transfer = TransactionTypes.Transfer()
		bob = binascii.unhexlify(b'0b0b')
		alice = binascii.unhexlify(b'0a11ce')
		transfer.init_FromUserRequirements(source=bob, amount=10, destination=alice)
		self.assertEqual(str(transfer), 'transfer 10 from 0b0b to 0a11ce')
		s = MockState()
		transfer.apply(s)
		#print(s._log)
		self.assertEqual(s._log, [('requestTransfer', bob, 10, alice)])
		self.assertEqual(transfer.typeCode, 1)
		self.assertEqual(transfer.source, bob)
		self.assertEqual(transfer.destination, alice)
		self.assertEqual(transfer._maxBlock, 0xffffffff)
		assert not hasattr(transfer, 'controlAddressAmount')
		amount, maxBlock, extraData = transfer.encode()
		self.assertEqual(amount, 10)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, struct.pack("<B", 0) * 6) ## can be changed

		tx = TransactionTypes.LTCBuyOffer()
		bob2 = binascii.unhexlify(b'b0b2')
		tx.init_FromUserRequirements(source=bob, swapBillAmountOffered=111, exchangeRate=0x7fffffff, receivingDestination=bob2)
		self.assertEqual(str(tx), 'LTC buy offer from 0b0b funded with 111 swapbill, exchange rate 2147483647, receiving LTC at b0b2, maxBlock offset 0')
		s = MockState()
		tx.apply(s)
		#print(s._log)
		self.assertEqual(s._log, [('requestAddLTCBuyOffer', bob, 111, 2147483647, 4294967295, bob2)])
		self.assertEqual(tx.typeCode, 2)
		self.assertEqual(tx.source, bob)
		self.assertEqual(tx.destination, bob2)
		self.assertEqual(tx._maxBlock, 0xffffffff)
		assert not hasattr(tx, 'controlAddressAmount')
		amount, maxBlock, extraData = tx.encode()
		self.assertEqual(amount, 111)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, b'\xff\xff\xff\x7f\x00\x00')

		hostTX = MockHostTX(tx)
		sourceLookup = hostTX
		decodedTX = TransactionTypes._decode(tx.typeCode, amount, maxBlock, extraData, sourceLookup, hostTX)
		self.assertIsInstance(decodedTX, TransactionTypes.LTCBuyOffer)
		self.assertEqual(str(decodedTX), str(tx))
		self.assertEqual(decodedTX.__dict__, tx.__dict__)

		tx = TransactionTypes.LTCSellOffer()
		tx.init_FromUserRequirements(source=bob, swapBillDesired=111, exchangeRate=0x7fffffff)
		self.assertEqual(str(tx), 'LTC sell offer from 0b0b, for 111 swapbill, exchange rate 2147483647, maxBlock offset 0')
		s = MockState()
		tx.apply(s) ## capped to 1 here by mock state!
		self.assertEqual(s._log, [('requestAddLTCSellOffer', bob, 111, 6, 2147483647, 4294967295)])
		self.assertEqual(tx.typeCode, 3)
		self.assertEqual(tx.source, bob)
		assert not hasattr(tx, 'destination')
		self.assertEqual(tx._maxBlock, 0xffffffff)
		assert not hasattr(tx, 'controlAddressAmount')
		amount, maxBlock, extraData = tx.encode()
		self.assertEqual(amount, 111)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, b'\xff\xff\xff\x7f\x00\x00')

		hostTX = MockHostTX(tx)
		sourceLookup = hostTX
		decodedTX = TransactionTypes._decode(tx.typeCode, amount, maxBlock, extraData, sourceLookup, hostTX)
		self.assertIsInstance(decodedTX, TransactionTypes.LTCSellOffer)
		self.assertEqual(str(decodedTX), str(tx))
		self.assertEqual(decodedTX.__dict__, tx.__dict__)

		hostTX = MockHostTX(burn)
		#print(hostTX.__dict__)
		sourceLookup = hostTX
		decodedBurn = TransactionTypes._decode(burn.typeCode, 0, 0, struct.pack("<B", 0) * 6, sourceLookup, hostTX)
		self.assertEqual(str(decodedBurn), 'burn 10 with credit to 0a')
		self.assertEqual(decodedBurn.__dict__, burn.__dict__)

		## different extra data for burn should raise an exception
		self.assertRaises(TransactionTypes.NotValidSwapBillTransaction, TransactionTypes._decode, burn.typeCode, 0, 0, struct.pack("<B", 99) * 6, sourceLookup, hostTX)

		hostTX = MockHostTX(transfer)
		sourceLookup = hostTX
		decodedTransfer = TransactionTypes._decode(transfer.typeCode, 10, 0xffffffff, struct.pack("<B", 0) * 6, sourceLookup, hostTX)
		assert decodedTransfer._maxBlock == 0xffffffff ## TODO: implement this properly, or move to separate transaction type!
		assert str(decodedTransfer) == 'transfer 10 from 0b0b to 0a11ce'
		assert decodedTransfer.__dict__ == transfer.__dict__

		## as before, but different extra data (should be ignored)
		decodedTransfer = TransactionTypes._decode(transfer.typeCode, 10, 0xffffffff, struct.pack("<B", 99) * 6, sourceLookup, hostTX)
		assert decodedTransfer._maxBlock == 0xffffffff ## TODO: implement this properly, or move to separate transaction type!
		assert str(decodedTransfer) == 'transfer 10 from 0b0b to 0a11ce'
		assert decodedTransfer.__dict__ == transfer.__dict__

##TODO test backward compatibility, through ForwardToFutureVersion type