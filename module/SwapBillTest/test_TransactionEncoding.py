from __future__ import print_function
import unittest, binascii
from SwapBill import TransactionEncoding
from SwapBill.TransactionEncoding import FromStateTransaction, ToStateTransaction

class Test(unittest.TestCase):

	def checkIgnoredBytes(self, tx, numberOfIgnoredBytes):
		assert tx._outputs[0][0].startswith(b'SWP')
		transactionType, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		for fillByte in (b'\xff', b'\x00', b'\x80'):
			if numberOfIgnoredBytes > 0:
				tx._outputs[0] = (tx._outputs[0][0][:-numberOfIgnoredBytes] + fillByte * numberOfIgnoredBytes, tx._outputs[0][1])
				transactionType_Check, outputs_Check, details_Check = TransactionEncoding.ToStateTransaction(tx)
				self.assertEqual(transactionType, transactionType_Check)
				self.assertEqual(outputs, outputs_Check)
				self.assertDictEqual(details, details_Check)
		try:
			for fillByte in (b'\xff', b'\x00', b'\x80'):
				tx._outputs[0] = (tx._outputs[0][0][:-(numberOfIgnoredBytes + 1)] + fillByte * (numberOfIgnoredBytes + 1), tx._outputs[0][1])
				transactionType_Check, outputs_Check, details_Check = TransactionEncoding.ToStateTransaction(tx)
				self.assertEqual(transactionType, transactionType_Check)
				self.assertEqual(outputs, outputs_Check)
				self.assertDictEqual(details, details_Check)
		except (TransactionEncoding.NotValidSwapBillTransaction, AssertionError):
			pass
		else:
			raise Exception('Expected decoding failure with extra byte overwrite!')

	def EncodeInt_CheckDecode(self, value, numberOfBytes):
		result = TransactionEncoding._encodeInt(value, numberOfBytes)
		self.assertTrue(type(result) is type(b''))
		self.assertEqual(len(result), numberOfBytes)
		decoded = TransactionEncoding._decodeInt(result)
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

	def test_bad_burn_address(self):
		tx = FromStateTransaction('Burn', ('destination',), ('_pkh',), {'amount':10})
		self.assertEqual(tx._outputs[0], (b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10))
		tx._outputs[0] = (b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01', 10)
		self.assertRaises(TransactionEncoding.NotValidSwapBillTransaction, ToStateTransaction, tx)
		tx._outputs[0] = (b'SWP\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10)
		self.assertRaises(TransactionEncoding.NotValidSwapBillTransaction, ToStateTransaction, tx)
		tx._outputs[0] = (b'SWP\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10)
		self.assertRaises(TransactionEncoding.NotValidSwapBillTransaction, ToStateTransaction, tx)

	def test_bad_type_string(self):
		self.assertRaisesRegexp(Exception, "('Unknown transaction type string', 'Burneeyo')", FromStateTransaction, 'Burneeyo', ('destination',), ('_pkh',), {'amount':10})

	def test_types(self):
		tx = FromStateTransaction('Burn', ('destination',), ('_pkh',), {'amount':10})
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SWP\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10), ('_pkh', 0)]})
		tx = FromStateTransaction('Pay', ('change','destination'), ('changePKH','destinationPKH'), {'sourceAccount':('sourceTXID',4), 'amount':20, 'maxBlock':100})
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 4)], '_outputs': [(b'SWP\x01\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('changePKH', 0), ('destinationPKH', 0)]})
		self.checkIgnoredBytes(tx, 6)
		tx = FromStateTransaction(
		    'LTCBuyOffer', ('change','refund'), ('changePKH','refundPKH'),
		    {'sourceAccount':('sourceTXID',5), 'receivingAddress':'ltcSellPKH', 'swapBillOffered':22, 'maxBlock':0, 'exchangeRate':123}
		)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SWP\x02\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00{\x00\x00\x00\x00\x00', 0), ('changePKH', 0), ('refundPKH', 0), ('ltcSellPKH', 0)], '_inputs': [('sourceTXID', 5)]} )
		self.checkIgnoredBytes(tx, 2)
		tx = FromStateTransaction(
		    'LTCSellOffer', ('change','ltcSell'), ('changePKH','ltcSellPKH'),
		    {'sourceAccount':('sourceTXID',3), 'swapBillDesired':22, 'maxBlock':0, 'exchangeRate':123}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 3)], '_outputs': [(b'SWP\x03\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00{\x00\x00\x00\x00\x00', 0), ('changePKH', 0), ('ltcSellPKH', 0)]} )
		self.checkIgnoredBytes(tx, 2)
		tx = FromStateTransaction(
		    'LTCExchangeCompletion', (), (),
		    {'pendingExchangeIndex':32, 'destinationAddress':'destinationPKH', 'destinationAmount':999}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SWP\x04 \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('destinationPKH', 999)]} )
		self.checkIgnoredBytes(tx, 10)
		tx = FromStateTransaction(
		    'Collect', ('destination',), ('destinationPKH',),
		    {'sourceAccounts':[('sourceTXID1',5), ('sourceTXID2',6), ('sourceTXID3',7)]}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID1', 5), ('sourceTXID2', 6), ('sourceTXID3', 7)], '_outputs': [(b'SWP\x05\x03\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('destinationPKH', 0)]} )
		self.checkIgnoredBytes(tx, 14)

	def test_forwarding(self):
		# cannot encode forward to future network version transactions explicitly from state transactions
		self.assertRaisesRegexp(Exception, "('Unknown transaction type string', 'ForwardToFutureNetworkVersion')", FromStateTransaction, 'ForwardToFutureNetworkVersion', ('change',), ('changePKH',), {'amount':999})
		# pay transactions satisfy format requirements for forward to future network transactions
		# so hack the type code for a pay transaction to test this
		tx = FromStateTransaction('Pay', ('change','destination'), ('changePKH','destinationPKH'), {'sourceAccount':('sourceTXID',4), 'amount':20, 'maxBlock':100})
		tx._outputs[0] = (b'SWP\x0f\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		transactionType, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		self.assertEqual(transactionType, 'ForwardToFutureNetworkVersion')
		self.assertEqual(outputs, ('change',))
		self.assertDictEqual(details, {'sourceAccount':('sourceTXID',4), 'amount':20, 'maxBlock':100})
		# same as above, but with max typecode interpreted in this way
		tx._outputs[0] = (b'SWP\x7f\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 1)
		transactionType, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		self.assertEqual(transactionType, 'ForwardToFutureNetworkVersion')
		self.assertEqual(outputs, ('change',))
		self.assertDictEqual(details, {'sourceAccount':('sourceTXID',4), 'amount':20, 'maxBlock':100})
		# next typecode after that is not supported
		tx._outputs[0] = (b'SWP\x80\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		self.assertRaises(TransactionEncoding.UnsupportedTransaction, TransactionEncoding.ToStateTransaction, tx)
		# and ditto up to end of typecode byte range
		tx._outputs[0] = (b'SWP\xff\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		self.assertRaises(TransactionEncoding.UnsupportedTransaction, TransactionEncoding.ToStateTransaction, tx)
