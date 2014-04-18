from __future__ import print_function
import unittest, binascii
from SwapBill import TransactionTypes

class MockInputProvider(object):
	def __init__(self):
		self._count = 0
	def lookupUnspentFor(self, sourceAccount):
		sourceAccountAscii = binascii.hexlify(sourceAccount).decode('ascii')
		self._count += 1
		txID = 'txID_' + str(self._count) + '_' + sourceAccountAscii
		vOut = self._count
		return txID, vOut

class MockSourceLookup(object):
	def first(self, tx):
		txID = tx.inputTXID(0)
		vOut = tx.inputVOut(0)
		prefix = 'txID_' + str(vOut) + '_'
		assert txID.startswith(prefix)
		sourceAccountAscii = txID[len(prefix):]
		sourceAccount = binascii.unhexlify(sourceAccountAscii.encode('ascii'))
		return sourceAccount

class Test(unittest.TestCase):

	def EncodeAndCheck(self, transactionType, details):
		inputProvider = MockInputProvider()
		tx = TransactionTypes.FromStateTransaction(transactionType, details, inputProvider)
		sourceLookup = MockSourceLookup()
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(sourceLookup, tx)
		self.assertEqual(transactionType, decodedType)
		self.assertDictEqual(details, decodedDetails)
		return tx

	def test(self):
		bob = binascii.unhexlify(b'0b0b')
		bob2 = binascii.unhexlify(b'b0b2')
		bob3 = binascii.unhexlify(b'b0b3')
		bob4 = binascii.unhexlify(b'b0b4')
		alice = binascii.unhexlify(b'0a11ce')

		tx = self.EncodeAndCheck('Burn', {'amount':10, 'destinationAccount': bob})
		self.assertEqual(tx.numberOfInputs(), 0)
		self.assertEqual(tx.numberOfOutputs(), 2)
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SWB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10), (b'\x0b\x0b', 100000)]})

		tx = self.EncodeAndCheck('Pay', {'sourceAccount':bob, 'amount':10, 'destinationAccount':alice, 'changeAccount':bob2, 'maxBlock':100})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 3)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWB\x01\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 100000), (b'\n\x11\xce', 100000), (b'\xb0\xb2', 100000)], '_inputs': [('txID_1_0b0b', 1)]})
		# and then reusing source address
		tx = self.EncodeAndCheck('Pay', {'sourceAccount':bob, 'amount':10, 'destinationAccount':alice, 'changeAccount':bob, 'maxBlock':100})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 2)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('txID_1_0b0b', 1)], '_outputs': [(b'SWB\x02\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 100000), (b'\n\x11\xce', 100000)]})

		tx = self.EncodeAndCheck('LTCBuyOffer', {
		    'sourceAccount':bob, 'changeAccount':bob2, 'refundAccount':bob3, 'receivingAccount':bob4,
		    'swapBillOffered':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 4)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('txID_1_0b0b', 1)], '_outputs': [(b'SWB\x03d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 100000), (b'\xb0\xb4', 100000), (b'\xb0\xb2', 100000), (b'\xb0\xb3', 100000)]})
		# and then reusing source address
		tx = self.EncodeAndCheck('LTCBuyOffer', {
		    'sourceAccount':bob, 'changeAccount':bob, 'refundAccount':bob, 'receivingAccount':bob2,
		    'swapBillOffered':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 2)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('txID_1_0b0b', 1)], '_outputs': [(b'SWB\x04d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 100000), (b'\xb0\xb2', 100000)]})


				#'sourceAccount':sourceLookup.first(tx), 'swapBillDesired':amount,
				#'receivingAccount':tx.outputPubKeyHash(1), 'changeAccount':tx.outputPubKeyHash(2),
				#'exchangeRate':exchangeRate, 'maxBlockOffset':maxBlockOffset, 'maxBlock':maxBlock


		tx = self.EncodeAndCheck('LTCSellOffer', {
		    'sourceAccount':bob, 'changeAccount':bob2, 'receivingAccount':bob3,
		    'swapBillDesired':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 3)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('txID_1_0b0b', 1)], '_outputs': [(b'SWB\x05d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 100000), (b'\xb0\xb3', 100000), (b'\xb0\xb2', 100000)]})
		# and then reusing source address
		tx = self.EncodeAndCheck('LTCSellOffer', {
		    'sourceAccount':bob, 'changeAccount':bob, 'receivingAccount':bob,
		    'swapBillDesired':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 2)
		#print(tx.__dict__)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWB\x06d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 100000), (b'\x0b\x0b', 100000)], '_inputs': [('txID_1_0b0b', 1)]})


		return

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

