from __future__ import print_function
import unittest, binascii
from SwapBill import TransactionTypes
from SwapBill.TransactionTypes import FromStateTransaction, ToStateTransaction

class MockInputProvider(object):
	def __init__(self):
		self._count = 0
	def getTXInputForAddress(self, sourceAccount):
		sourceAccountAscii = binascii.hexlify(sourceAccount).decode('ascii')
		self._count += 1
		txID = 'txID_' + str(self._count) + '_' + sourceAccountAscii
		vOut = self._count
		return txID, vOut

class MockSourceLookup(object):
	def getSourceFor(self, txID, vOut):
		prefix = 'txID_' + str(vOut) + '_'
		assert txID.startswith(prefix)
		sourceAccountAscii = txID[len(prefix):]
		sourceAccount = binascii.unhexlify(sourceAccountAscii.encode('ascii'))
		return sourceAccount

class Test(unittest.TestCase):

	def EncodeAndCheck(self, transactionType, details, ignoredBytesAtEnd=0):
		#inputProvider = MockInputProvider()
		#tx = TransactionTypes.FromStateTransaction(transactionType, details, inputProvider)
		tx = TransactionTypes.FromStateTransaction(transactionType, details)
		sourceLookup = MockSourceLookup()
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(sourceLookup, tx)
		self.assertEqual(transactionType, decodedType)
		self.assertDictEqual(details, decodedDetails)
		if ignoredBytesAtEnd > 0:
			tx._outputs[0] = (tx._outputs[0][0][:-ignoredBytesAtEnd] + b'\xff' * ignoredBytesAtEnd, tx._outputs[0][1])
			decodedType, decodedDetails = TransactionTypes.ToStateTransaction(sourceLookup, tx)
			self.assertEqual(transactionType, decodedType)
			self.assertDictEqual(details, decodedDetails)
		return tx

	def EncodeInt_CheckDecode(self, value, numberOfBytes):
		result = TransactionTypes._encodeInt(value, numberOfBytes)
		self.assertTrue(type(result) is type(b''))
		self.assertEqual(len(result), numberOfBytes)
		decoded = TransactionTypes._decodeInt(result)
		self.assertEqual(decoded, value)
		return result

	def test_internal(self):
		self.assertEqual(self.EncodeInt_CheckDecode(0, 1), b'\x00')
		self.assertEqual(self.EncodeInt_CheckDecode(1, 1), b'\x01')
		self.assertEqual(self.EncodeInt_CheckDecode(255, 1), b'\xff')
		self.assertEqual(self.EncodeInt_CheckDecode(0, 2), b'\x00\x00')
		self.assertEqual(self.EncodeInt_CheckDecode(1, 2), b'\x01\x00')
		self.assertEqual(self.EncodeInt_CheckDecode(255, 2), b'\xff\x00')
		self.assertEqual(self.EncodeInt_CheckDecode(256, 2), b'\x00\x01')
		self.assertEqual(self.EncodeInt_CheckDecode(258, 2), b'\x02\x01')

	def test_bad_state_transactions(self):
		## outputs don't match spec
		self.assertRaises(AssertionError, FromStateTransaction, 'Burn', (), (), {'amount':10})
		## outputs don't match spec
		self.assertRaises(AssertionError, FromStateTransaction, 'Burn', ('dostination',), ('_pkh',), {'amount':10})
		## lengths of keys and outputs spec don't match
		self.assertRaises(AssertionError, FromStateTransaction, 'Pay', ('change','destination'), ('changePKH'), {'sourceAccount':('sourceTXID',4), 'amount':20, 'maxBlock':100})

	def test_types(self):
		tx = FromStateTransaction('Burn', ('destination',), ('_pkh',), {'amount':10})
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10), ('_pkh', 0)]})
		tx = FromStateTransaction('Pay', ('change','destination'), ('changePKH','destinationPKH'), {'sourceAccount':('sourceTXID',4), 'amount':20, 'maxBlock':100})
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 4)], '_outputs': [(b'SWP\x01\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('changePKH', 0), ('destinationPKH', 0)]})
		tx = FromStateTransaction(
		    'LTCBuyOffer', ('change','refund'), ('changePKH','refundPKH'),
		    {'sourceAccount':('sourceTXID',5), 'receivingAddress':'receivingPKH', 'swapBillOffered':22, 'maxBlock':0, 'exchangeRate':123, 'maxBlockOffset':345}
		)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x02\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00{\x00\x00\x00Y\x01', 0), ('changePKH', 0), ('refundPKH', 0), ('receivingPKH', 0)], '_inputs': [('sourceTXID', 5)]} )
		tx = FromStateTransaction(
		    'LTCSellOffer', ('change','receiving'), ('changePKH','receivingPKH'),
		    {'sourceAccount':('sourceTXID',3), 'swapBillDesired':22, 'maxBlock':0, 'exchangeRate':123, 'maxBlockOffset':345}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 3)], '_outputs': [(b'SWP\x03\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00{\x00\x00\x00Y\x01', 0), ('changePKH', 0), ('receivingPKH', 0)]} )
		tx = FromStateTransaction(
		    'LTCExchangeCompletion', (), (),
		    {'pendingExchangeIndex':32, 'destinationAddress':'destinationPKH', 'destinationAmount':999}
		)
		#print('\t\tself.assertDictEqual(tx.__dict__,', tx.__dict__, ')')
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SWP\x04 \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('destinationPKH', 999)]} )

## TODO - check that stuff after end of encoded bytes in control address is ignored
## TOTO - check forwarding to future network version


	def not_test(self):
		bob = binascii.unhexlify(b'0b0b')
		bob2 = binascii.unhexlify(b'b0b2')
		bob3 = binascii.unhexlify(b'b0b3')
		bob4 = binascii.unhexlify(b'b0b4')
		alice = binascii.unhexlify(b'0a11ce')

		tx = self.EncodeAndCheck('Burn', {'amount':10, 'destinationAccount': bob})
		self.assertEqual(tx.numberOfInputs(), 0)
		self.assertEqual(tx.numberOfOutputs(), 2)
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10), (b'\x0b\x0b', 0)]})

		# burn decode must only accept all zeros
		tx._outputs[0] = (b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01', 10)
		self.assertRaises(TransactionTypes.NotValidSwapBillTransaction, TransactionTypes.ToStateTransaction, MockSourceLookup(), tx)
		tx._outputs[0] = (b'SWP\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10)
		self.assertRaises(TransactionTypes.NotValidSwapBillTransaction, TransactionTypes.ToStateTransaction, MockSourceLookup(), tx)
		tx._outputs[0] = (b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x80\x00\x00\x00\x00\x00\x00\x00', 10)
		self.assertRaises(TransactionTypes.NotValidSwapBillTransaction, TransactionTypes.ToStateTransaction, MockSourceLookup(), tx)

		details = {'sourceAccount':('bob_tx0',0), 'amount':10, 'destinationAccount':('alice_tx0',0), 'changeAccount':('bob_tx1',0), 'maxBlock':100}
		tx = self.EncodeAndCheck('Pay', details)
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 3)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x01\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), (b'\xb0\xb2', 0), (b'\n\x11\xce', 0)], '_inputs': [('txID_1_0b0b', 1)]})

		# pay transaction doesn't care about last 6 bytes of control address data
		tx._outputs[0] = (b'SWP\x01\n\x00\x00\x00\x00\x00d\x00\x00\x01\x00\x00\x00\x00\x00\x00', 0) # changes byte just before last 6
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(MockSourceLookup(), tx)
		self.assertNotEqual(decodedDetails, details)
		tx._outputs[0] = (b'SWP\x01\n\x00\x00\x00\x00\x00d\x00\x00\x00\x80\x00\x00\x00\x00\x00', 0) # changes byte in last 6
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(MockSourceLookup(), tx)
		self.assertEqual(decodedDetails, details)
		tx._outputs[0] = (b'SWP\x01\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\xff\xff\x00\x00\x00', 0) # changes bytes in last 6
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(MockSourceLookup(), tx)
		self.assertEqual(decodedDetails, details)
		tx._outputs[0] = (b'SWP\x01\n\x00\x00\x00\x00\x00d\x00\x00\x00\xff\xff\xff\xff\xff\xff', 0) # changes bytes in last 6
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(MockSourceLookup(), tx)
		self.assertEqual(decodedDetails, details)

		# and then reusing source address (doesn't make any difference now, to encoding, since we need to reseed in fact)
		tx = self.EncodeAndCheck('Pay', {'sourceAccount':bob, 'amount':10, 'destinationAccount':alice, 'changeAccount':bob, 'maxBlock':100})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 3)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('txID_1_0b0b', 1)], '_outputs': [(b'SWP\x01\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), (b'\x0b\x0b', 0), (b'\n\x11\xce', 0)]})
		# change type code and check the transaction is decoded correctly as forward to future network version
		tx._outputs[0] = (b'SWP\x09\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(MockSourceLookup(), tx)
		self.assertEqual(decodedType, 'ForwardToFutureNetworkVersion')
		self.assertDictEqual(decodedDetails, {'changeAccount': b'\x0b\x0b', 'maxBlock': 100, 'amount': 10})
		# last supported type code for forwarding
		tx._outputs[0] = (b'SWP\x7f\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(MockSourceLookup(), tx)
		self.assertEqual(decodedType, 'ForwardToFutureNetworkVersion')
		self.assertDictEqual(decodedDetails, {'changeAccount': b'\x0b\x0b', 'maxBlock': 100, 'amount': 10})
		# type codes after that are not supported by this client version
		tx._outputs[0] = (b'SWP\x80\n\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		self.assertRaises(TransactionTypes.UnsupportedTransaction, TransactionTypes.ToStateTransaction, MockSourceLookup(), tx)

		tx = self.EncodeAndCheck('LTCBuyOffer', {
		    'sourceAccount':bob, 'changeAccount':bob2, 'refundAccount':bob3, 'receivingAccount':bob4,
		    'swapBillOffered':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 4)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('txID_1_0b0b', 1)], '_outputs': [(b'SWP\x02d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 0), (b'\xb0\xb2', 0), (b'\xb0\xb4', 0), (b'\xb0\xb3', 0)]})
		# and then reusing source address (doesn't make any difference, as no special encoding for this currently)
		tx = self.EncodeAndCheck('LTCBuyOffer', {
		    'sourceAccount':bob, 'changeAccount':bob, 'refundAccount':bob, 'receivingAccount':bob2,
		    'swapBillOffered':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 4)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x02d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 0), (b'\x0b\x0b', 0), (b'\xb0\xb2', 0), (b'\x0b\x0b', 0)], '_inputs': [('txID_1_0b0b', 1)]})

		tx = self.EncodeAndCheck('LTCSellOffer', {
		    'sourceAccount':bob, 'changeAccount':bob2, 'receivingAccount':bob3,
		    'swapBillDesired':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 3)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x03d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 0), (b'\xb0\xb2', 0), (b'\xb0\xb3', 0)], '_inputs': [('txID_1_0b0b', 1)]})
		# and then reusing source address (no difference currently)
		tx = self.EncodeAndCheck('LTCSellOffer', {
		    'sourceAccount':bob, 'changeAccount':bob, 'receivingAccount':bob,
		    'swapBillDesired':100, 'exchangeRate':1234,
		    'maxBlock':100, 'maxBlockOffset':10
			})
		self.assertEqual(tx.numberOfInputs(), 1)
		self.assertEqual(tx.numberOfOutputs(), 3)
		#print('\t\tself.assertDictEqual(tx.__dict__,', tx.__dict__.__repr__() + ')')
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x03d\x00\x00\x00\x00\x00d\x00\x00\x00\xd2\x04\x00\x00\n\x00', 0), (b'\x0b\x0b', 0), (b'\x0b\x0b', 0)], '_inputs': [('txID_1_0b0b', 1)]})

		tx = self.EncodeAndCheck('LTCExchangeCompletion', {'pendingExchangeIndex':7, 'destinationAccount':alice, 'destinationAmount':1234}, ignoredBytesAtEnd=10)
		self.assertEqual(tx.numberOfInputs(), 0)
		self.assertEqual(tx.numberOfOutputs(), 2)
		#print('\t\tself.assertDictEqual(tx.__dict__,', tx.__dict__.__repr__() + ')')
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x04\x07\x00\x00\x00\x00\x00\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff', 0), (b'\n\x11\xce', 1234)], '_inputs': []})
