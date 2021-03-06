from __future__ import print_function
import unittest, binascii
from SwapBill import TransactionEncoding
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

def FromStateTransactionWrapper(originalFunction):
	def Wrapper(transactionType, sourceAccounts, outputs, outputPubKeyHashes, originalDetails):
		tx = originalFunction(transactionType, sourceAccounts, outputs, outputPubKeyHashes, originalDetails)
		transactionType_Check, sourceAccounts_Check, outputs_Check, details_Check = TransactionEncoding.ToStateTransaction(tx)
		assert transactionType_Check == transactionType
		assert sourceAccounts_Check == sourceAccounts
		assert outputs_Check == outputs
		assert details_Check == originalDetails
		return tx
	return Wrapper
TransactionEncoding.FromStateTransaction = FromStateTransactionWrapper(TransactionEncoding.FromStateTransaction)

class Test(unittest.TestCase):

	def checkIgnoredBytes(self, tx, numberOfIgnoredBytes):
		transactionType, sourceAccounts, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		for fillByte in (b'\xff', b'\x00', b'\x80'):
			if numberOfIgnoredBytes > 0:
				tx._outputs[0] = (tx._outputs[0][0][:-numberOfIgnoredBytes] + fillByte * numberOfIgnoredBytes, tx._outputs[0][1])
				transactionType_Check, sourceAccounts_Check, outputs_Check, details_Check = TransactionEncoding.ToStateTransaction(tx)
				self.assertEqual(transactionType, transactionType_Check)
				self.assertEqual(sourceAccounts, sourceAccounts_Check)
				self.assertEqual(outputs, outputs_Check)
				self.assertDictEqual(details, details_Check)
		try:
			for fillByte in (b'\xff', b'\x00', b'\x80'):
				tx._outputs[0] = (tx._outputs[0][0][:-(numberOfIgnoredBytes + 1)] + fillByte * (numberOfIgnoredBytes + 1), tx._outputs[0][1])
				transactionType_Check, sourceAccounts_Check, outputs_Check, details_Check = TransactionEncoding.ToStateTransaction(tx)
				self.assertEqual(transactionType, transactionType_Check)
				self.assertEqual(sourceAccounts, sourceAccounts_Check)
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
		# outputs don't match spec
		self.assertRaises(AssertionError, TransactionEncoding.FromStateTransaction, 'Burn', [], (), (), {'amount':10})
		# outputs don't match spec
		self.assertRaises(AssertionError, TransactionEncoding.FromStateTransaction, 'Burn', [], ('dostination',), ('_pkh',), {'amount':10})
		# Burn is a funded type, so must have sourceAccounts list set
		self.assertRaises(AssertionError, TransactionEncoding.FromStateTransaction, 'Burn', None, ('destination',), ('_pkh',), {'amount':10})
		# bad type string
		self.assertRaisesRegexp(Exception, "('Unknown transaction type string', 'Burneeyo')", TransactionEncoding.FromStateTransaction, 'Burneeyo', [], ('destination',), ('_pkh',), {'amount':10})
		# lengths of keys and outputs spec don't match
		self.assertRaises(AssertionError, TransactionEncoding.FromStateTransaction, 'Pay', [('sourceTXID',4)], ('change','destination'), ('changePKH'), {'amount':20, 'maxBlock':100})
		# LTCExchangeCompletion is unfunded, so must not have sourceAccounts list set
		self.assertRaises(AssertionError, TransactionEncoding.FromStateTransaction, 'LTCExchangeCompletion', [], (), (), {'pendingExchangeIndex':10, 'destinationAddress':'madeUpAddress', 'destinationAmount':10})
		# control group!
		TransactionEncoding.FromStateTransaction('Burn', [], ('destination',), ('_pkh',), {'amount':10})
		TransactionEncoding.FromStateTransaction('Pay', [('sourceTXID',4)], ('change','destination'), ('changePKH', 'destinationPKH'), {'amount':20, 'maxBlock':100})
		TransactionEncoding.FromStateTransaction('LTCExchangeCompletion', None, (), (), {'pendingExchangeIndex':10, 'destinationAddress':'madeUpAddress', 'destinationAmount':10})

	def test_bad_burn_address(self):
		tx = TransactionEncoding.FromStateTransaction('Burn', [], ('destination',), ('_pkh',), {'amount':10})
		self.assertEqual(tx._outputs[0], (b'SB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10))
		tx._outputs[0] = (b'SB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01', 10)
		self.assertRaises(TransactionEncoding.NotValidSwapBillTransaction, TransactionEncoding.ToStateTransaction, tx)
		tx._outputs[0] = (b'SB\x00\x80\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10)
		self.assertRaises(TransactionEncoding.NotValidSwapBillTransaction, TransactionEncoding.ToStateTransaction, tx)
		tx._outputs[0] = (b'SB\x00\x00\x00\x00\x00\x00\x00\x04\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10)
		self.assertRaises(TransactionEncoding.NotValidSwapBillTransaction, TransactionEncoding.ToStateTransaction, tx)

	def test_types(self):
		tx = TransactionEncoding.FromStateTransaction('Burn', [], ('destination',), ('_pkh',), {'amount':10})
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 10), ('_pkh', 0)]})
		tx = TransactionEncoding.FromStateTransaction('Pay', [('sourceTXID',4)], ('change','destination'), ('changePKH','destinationPKH'), {'amount':20, 'maxBlock':100})
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 4)], '_outputs': [(b'SB\x01\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('changePKH', 0), ('destinationPKH', 0)]})
		self.checkIgnoredBytes(tx, 7)
		tx = TransactionEncoding.FromStateTransaction(
		    'LTCBuyOffer',
		    [('sourceTXID',5)],
		    ('ltcBuy',), ('ltcBuyPKH',),
		    {'receivingAddress':'ltcReceivePKH', 'swapBillOffered':22, 'maxBlock':0, 'exchangeRate':123}
		)
		self.assertDictEqual(tx.__dict__, {'_outputs': [(b'SB\x02\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00{\x00\x00\x00\x00\x00\x00', 0), ('ltcBuyPKH', 0), ('ltcReceivePKH', 0)], '_inputs': [('sourceTXID', 5)]} )
		self.checkIgnoredBytes(tx, 3)
		tx = TransactionEncoding.FromStateTransaction(
		    'LTCSellOffer',
		    [('sourceTXID',3)],
		    ('ltcSell',), ('ltcSellPKH',),
		    {'ltcOffered':22, 'maxBlock':0, 'exchangeRate':123}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 3)], '_outputs': [(b'SB\x03\x16\x00\x00\x00\x00\x00\x00\x00\x00\x00{\x00\x00\x00\x00\x00\x00', 0), ('ltcSellPKH', 0)]} )
		self.checkIgnoredBytes(tx, 3)
		tx = TransactionEncoding.FromStateTransaction(
		    'LTCExchangeCompletion',
		    None,
		    (), (),
		    {'pendingExchangeIndex':32, 'destinationAddress':'destinationPKH', 'destinationAmount':999}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [], '_outputs': [(b'SB\x80 \x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0), ('destinationPKH', 999)]} )
		self.checkIgnoredBytes(tx, 11)
		tx = TransactionEncoding.FromStateTransaction(
		    'BackLTCSells',
		    [('sourceTXID',7)],
		    ('ltcSellBacker',), ('ltcSellBackerPKH',),
		    {'backingAmount':32, 'transactionsBacked':4, 'ltcReceiveAddress':'receivePKH', 'maxBlock':123, 'commission':0xfffffff}
		)
		self.assertDictEqual(tx.__dict__, {'_inputs': [('sourceTXID', 7)], '_outputs': [(b'SB\x04 \x00\x00\x00\x00\x00\x04\x00\x00{\x00\x00\x00\xff\xff\xff\x0f', 0), ('ltcSellBackerPKH', 0), ('receivePKH', 0)]})
		self.checkIgnoredBytes(tx, 0)

	def test_forwarding(self):
		# cannot encode forward to future network version transactions explicitly from state transactions
		self.assertRaisesRegexp(Exception, "('Unknown transaction type string', 'ForwardToFutureNetworkVersion')", TransactionEncoding.FromStateTransaction, 'ForwardToFutureNetworkVersion', [('sourceTXID',4)], ('change',), ('changePKH',), {'amount':999, 'maxBlock':100})
		# pay transactions satisfy format requirements for forward to future network transactions
		# so hack the type code for a pay transaction to test this
		tx = TransactionEncoding.FromStateTransaction('Pay', [('sourceTXID',4)], ('change','destination'), ('changePKH','destinationPKH'), {'amount':20, 'maxBlock':100})
		tx._outputs[0] = (b'SB\x0f\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		transactionType, sourceAccounts, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		self.assertEqual(transactionType, 'ForwardToFutureNetworkVersion')
		self.assertEqual(sourceAccounts, [('sourceTXID',4)])
		self.assertEqual(outputs, ('change',))
		self.assertDictEqual(details, {'amount':20, 'maxBlock':100})
		# same as above, but with max typecode interpreted in this way
		tx._outputs[0] = (b'SB\x7f\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 1)
		transactionType, sourceAccounts, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		self.assertEqual(transactionType, 'ForwardToFutureNetworkVersion')
		self.assertEqual(sourceAccounts, [('sourceTXID',4)])
		self.assertEqual(outputs, ('change',))
		self.assertDictEqual(details, {'amount':20, 'maxBlock':100})
		# after that, we get unfunded transactions
		tx._outputs[0] = (b'SB\x80\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		transactionType, sourceAccounts, outputs, details = TransactionEncoding.ToStateTransaction(tx)
		self.assertEqual(transactionType, 'LTCExchangeCompletion')
		# codes after unfunded not supported (increase the typecode byte, if more unfunded added)
		tx._outputs[0] = (b'SB\x90\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		self.assertRaises(TransactionEncoding.UnsupportedTransaction, TransactionEncoding.ToStateTransaction, tx)
		# and ditto up to end of typecode byte range
		tx._outputs[0] = (b'SB\xff\x14\x00\x00\x00\x00\x00d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 0)
		self.assertRaises(TransactionEncoding.UnsupportedTransaction, TransactionEncoding.ToStateTransaction, tx)

	def test_destination_range(self):
		details = {'pendingExchangeIndex':32, 'destinationAddress':'destinationPKH', 'destinationAmount':100}
		tx = TransactionEncoding.FromStateTransaction('LTCExchangeCompletion', None, (), (), details)
		details['destinationAmount'] = 0
		tx = TransactionEncoding.FromStateTransaction('LTCExchangeCompletion', None, (), (), details)
		details['destinationAmount'] = -1
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Negative output amounts are not permitted', TransactionEncoding.FromStateTransaction, 'LTCExchangeCompletion', None, (), (), details)
		details['destinationAmount'] = 0xffffffffffffffff
		tx = TransactionEncoding.FromStateTransaction('LTCExchangeCompletion', None, (), (), details)
		details['destinationAmount'] += 1
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Control address output amount exceeds supported range', TransactionEncoding.FromStateTransaction, 'LTCExchangeCompletion', None, (), (), details)
