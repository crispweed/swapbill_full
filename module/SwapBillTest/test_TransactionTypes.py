from __future__ import print_function
import unittest, struct, binascii
from SwapBill import TransactionTypes

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
		if hasattr(tx, 'destinations'):
			if hasattr(tx, 'destinationAmounts'):
				assert(len(tx.destinationAmounts) == len(tx.destinations))
			for i in range(len(tx.destinations)):
				self._outputHashes.append(tx.destinations[i])
				if hasattr(tx, 'destinationAmounts'):
					self._outputAmounts.append(tx.destinationAmounts[i])
				else:
					self._outputAmounts.append(0);
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

	def CheckDecode(self, tx, suppliedExtraData=None):
		typeCode, amount, maxBlock, extraData = tx.encode()
		if suppliedExtraData is not None:
			extraData = suppliedExtraData
		hostTX = MockHostTX(tx)
		sourceLookup = hostTX
		decodedTX = TransactionTypes._decode(typeCode, amount, maxBlock, extraData, sourceLookup, hostTX)
		self.assertDictEqual(decodedTX.details(), tx.details())
		self.assertDictEqual(decodedTX.__dict__, tx.__dict__)

	def test(self):
		a = binascii.unhexlify(b'0a')
		bob = binascii.unhexlify(b'0b0b')
		bob2 = binascii.unhexlify(b'b0b2')
		alice = binascii.unhexlify(b'0a11ce')

		burn = TransactionTypes.Burn()
		burn.init_FromUserRequirements(burnAmount=10, target=a)
		self.assertDictEqual(burn.details(), {'amount': 10, 'destinationAccount': a})
		self.assertEqual(burn.controlAddressAmount, 10)
		self.assertSequenceEqual(burn.destinations, [a])
		assert not hasattr(burn, 'source')
		assert not hasattr(burn, 'destinationAmounts')
		# burn encoding is set up so that control address is obviously unspendable
		self.assertEqual(burn.encode(), (0, 0, 0, struct.pack("<B", 0) * 6))
		self.CheckDecode(burn)
		self.assertRaises(TransactionTypes.NotValidSwapBillTransaction, self.CheckDecode, tx=burn, suppliedExtraData=struct.pack("<B", 99) * 6)

		transfer = TransactionTypes.Transfer()
		transfer.init_FromUserRequirements(source=bob, amount=10, destination=alice)
		self.assertDictEqual(transfer.details(),  {'sourceAccount': b'\x0b\x0b', 'destinationAccount': b'\n\x11\xce', 'amount': 10, 'maxBlock':4294967295})
		self.assertEqual(transfer.source, bob)
		self.assertSequenceEqual(transfer.destinations, [alice])
		assert not hasattr(transfer, 'controlAddressAmount')
		assert not hasattr(transfer, 'destinationAmounts')
		typeCode, amount, maxBlock, extraData = transfer.encode()
		self.assertEqual(typeCode, 1)
		self.assertEqual(amount, 10)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, struct.pack("<B", 0) * 6) ## can be changed
		self.CheckDecode(transfer)
		## different extra data should be ignored
		self.CheckDecode(transfer, suppliedExtraData=struct.pack("<B", 99) * 6)

		# as above, but with max block limit
		transfer = TransactionTypes.Transfer()
		transfer.init_FromUserRequirements(source=bob, amount=10, destination=alice, maxBlock=200)
		self.assertDictEqual(transfer.details(),  {'sourceAccount': b'\x0b\x0b', 'destinationAccount': b'\n\x11\xce', 'amount': 10, 'maxBlock':200})
		self.assertEqual(transfer.source, bob)
		self.assertSequenceEqual(transfer.destinations, [alice])
		assert not hasattr(transfer, 'controlAddressAmount')
		assert not hasattr(transfer, 'destinationAmounts')
		typeCode, amount, maxBlock, extraData = transfer.encode()
		self.assertEqual(typeCode, 1)
		self.assertEqual(amount, 10)
		self.assertEqual(maxBlock, 200)
		self.assertEqual(extraData, struct.pack("<B", 0) * 6) ## can be changed
		self.CheckDecode(transfer)
		## different extra data should be ignored
		self.CheckDecode(transfer, suppliedExtraData=struct.pack("<B", 99) * 6)

		tx = TransactionTypes.Pay()
		tx.init_FromUserRequirements(source=bob, amount=123, destination=alice, change=bob2)
		self.assertDictEqual(tx.details(),  {'sourceAccount': b'\x0b\x0b', 'changeAccount': b'\xb0\xb2', 'destinationAccount': b'\n\x11\xce', 'amount': 123, 'maxBlock':4294967295})
		self.assertEqual(tx.source, bob)
		self.assertSequenceEqual(tx.destinations, [alice, bob2])
		assert not hasattr(tx, 'controlAddressAmount')
		assert not hasattr(tx, 'destinationAmounts')
		typeCode, amount, maxBlock, extraData = tx.encode()
		self.assertEqual(typeCode, 5)
		self.assertEqual(amount, 123)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, struct.pack("<B", 0) * 6) ## can be changed
		self.CheckDecode(tx)
		## different extra data should be ignored
		self.CheckDecode(tx, suppliedExtraData=struct.pack("<B", 99) * 6)

		# as above, but with max block limit
		tx.init_FromUserRequirements(source=bob, amount=123, destination=alice, change=bob2, maxBlock=1)
		self.assertDictEqual(tx.details(),  {'sourceAccount': b'\x0b\x0b', 'changeAccount': b'\xb0\xb2', 'destinationAccount': b'\n\x11\xce', 'amount': 123, 'maxBlock':1})
		self.assertEqual(tx.source, bob)
		self.assertSequenceEqual(tx.destinations, [alice, bob2])
		assert not hasattr(tx, 'controlAddressAmount')
		assert not hasattr(tx, 'destinationAmounts')
		typeCode, amount, maxBlock, extraData = tx.encode()
		self.assertEqual(typeCode, 5)
		self.assertEqual(amount, 123)
		self.assertEqual(maxBlock, 1)
		self.assertEqual(extraData, struct.pack("<B", 0) * 6) ## can be changed
		self.CheckDecode(tx)
		## different extra data should be ignored
		self.CheckDecode(tx, suppliedExtraData=struct.pack("<B", 99) * 6)

		tx = TransactionTypes.LTCBuyOffer()
		tx.init_FromUserRequirements(source=bob, change=bob, refund=bob, swapBillAmountOffered=111, exchangeRate=0x7fffffff, receivingDestination=bob2)
		self.assertDictEqual(tx.details(), {'swapBillOffered': 111, 'expiry': 4294967295, 'sourceAccount': b'\x0b\x0b', 'changeAccount': b'\x0b\x0b', 'refundAccount': b'\x0b\x0b', 'receivingAccount': b'\xb0\xb2', 'exchangeRate': 2147483647, 'maxBlock':4294967295})
		self.assertEqual(tx.source, bob)
		self.assertSequenceEqual(tx.destinations, [bob2, bob, bob])
		self.assertEqual(tx._maxBlock, 0xffffffff)
		assert not hasattr(tx, 'controlAddressAmount')
		assert not hasattr(tx, 'destinationAmounts')
		typeCode, amount, maxBlock, extraData = tx.encode()
		self.assertEqual(typeCode, 2)
		self.assertEqual(amount, 111)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, b'\xff\xff\xff\x7f\x00\x00')
		self.CheckDecode(tx)
		# test backward compatibility, through ForwardToFutureVersion type
		hostTX = MockHostTX(tx)
		sourceLookup = hostTX
		decodedTX = TransactionTypes._decode(127, amount, maxBlock, extraData, sourceLookup, hostTX)
		self.assertIsInstance(decodedTX, TransactionTypes.ForwardToFutureNetworkVersion)
		self.assertDictEqual(decodedTX.details(), {'sourceAccount': b'\x0b\x0b', 'amount': 111, 'maxBlock': 4294967295})
		self.assertDictEqual(decodedTX.__dict__, {'source': b'\x0b\x0b', 'amount': 111, '_maxBlock': 4294967295})
		# transaction types below 128 will be decoded like this
		self.assertRaises(TransactionTypes.UnsupportedTransaction, TransactionTypes._decode, 128, amount, maxBlock, extraData, sourceLookup, hostTX)

		tx = TransactionTypes.LTCSellOffer()
		tx.init_FromUserRequirements(source=bob, change=bob, receivingDestination=bob, swapBillDesired=111, exchangeRate=0x7fffffff)
		self.assertDictEqual(tx.details(), {'swapBillDesired': 111, 'sourceAccount': b'\x0b\x0b', 'changeAccount': b'\x0b\x0b', 'receivingAccount': b'\x0b\x0b', 'exchangeRate': 2147483647, 'expiry': 4294967295, 'maxBlock':4294967295})
		self.assertEqual(tx.source, bob)
		self.assertSequenceEqual(tx.destinations, [bob, bob])
		assert not hasattr(tx, 'controlAddressAmount')
		assert not hasattr(tx, 'destinationAmounts')
		typeCode, amount, maxBlock, extraData = tx.encode()
		self.assertEqual(typeCode, 3)
		self.assertEqual(amount, 111)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, b'\xff\xff\xff\x7f\x00\x00')
		self.CheckDecode(tx)
		# test backward compatibility, through ForwardToFutureVersion type
		hostTX = MockHostTX(tx)
		sourceLookup = hostTX
		decodedTX = TransactionTypes._decode(20, amount, maxBlock, extraData, sourceLookup, hostTX)
		self.assertIsInstance(decodedTX, TransactionTypes.ForwardToFutureNetworkVersion)
		self.assertDictEqual(decodedTX.details(), {'sourceAccount': b'\x0b\x0b', 'amount': 111, 'maxBlock': 4294967295})
		self.assertDictEqual(decodedTX.__dict__, {'source': b'\x0b\x0b', 'amount': 111, '_maxBlock': 4294967295})
		# with different maxBlock
		decodedTX = TransactionTypes._decode(25, amount, 1, extraData, sourceLookup, hostTX)
		self.assertIsInstance(decodedTX, TransactionTypes.ForwardToFutureNetworkVersion)
		self.assertDictEqual(decodedTX.details(), {'sourceAccount': b'\x0b\x0b', 'amount': 111, 'maxBlock': 1})
		self.assertDictEqual(decodedTX.__dict__, {'source': b'\x0b\x0b', 'amount': 111, '_maxBlock': 1})

		tx = TransactionTypes.LTCExchangeCompletion()
		tx.init_FromUserRequirements(ltcAmount=10000000, destination=bob, pendingExchangeIndex=7)
		self.assertDictEqual(tx.details(), {'pendingExchangeIndex': 7, 'destinationAccount': b'\x0b\x0b', 'destinationAmount': 10000000})
		self.assertSequenceEqual(tx.destinations, [bob])
		self.assertSequenceEqual(tx.destinationAmounts, [10000000])
		assert not hasattr(tx, 'controlAddressAmount')
		typeCode, amount, maxBlock, extraData = tx.encode()
		self.assertEqual(typeCode, 4)
		self.assertEqual(amount, 0)
		self.assertEqual(maxBlock, 0xffffffff)
		self.assertEqual(extraData, b'\x07\x00\x00\x00\x00\x00')
		self.CheckDecode(tx)

