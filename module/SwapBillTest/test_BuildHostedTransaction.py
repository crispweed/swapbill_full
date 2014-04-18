from __future__ import print_function
import unittest
from SwapBill import BuildHostedTransaction
from SwapBill.HostTransaction import AsData

class MockTransaction(object):
	def encode(self):
		return self.typeCode, self.amount, self.maxBlock, self.extraData

def AmountForInput(hostTX, i, unspent, sourceAddressSingleUnspent):
	assert len(unspent[0]) == len(unspent[1])
	for j in range(len(unspent[0])):
		amount = unspent[0][j]
		unspentInput = unspent[1][j]
		if unspentInput[0] == hostTX.inputTXID(i) and unspentInput[1] == hostTX.inputVOut(i):
			return amount
	if not sourceAddressSingleUnspent is None:
		amount, unspentInput = sourceAddressSingleUnspent
		if unspentInput[0] == hostTX.inputTXID(i) and unspentInput[1] == hostTX.inputVOut(i):
			return amount
	raise Exception('No matching unspent')

def SumOfOutputs(hostTX):
	result = 0
	for i in range(hostTX.numberOfOutputs()):
		result += hostTX.outputAmount(i)
	return result

def SanityChecks(transactionFee, unspent, hostTX, sourceAddressSingleUnspent=None):
	inputTotal = 0
	for i in range(hostTX.numberOfInputs()):
		inputTotal += AmountForInput(hostTX, i, unspent, sourceAddressSingleUnspent)
	assert inputTotal == SumOfOutputs(hostTX) + transactionFee

class Test(unittest.TestCase):
	def test(self):
		dustLimit = 10
		transactionFee = 100000

		unspentAmounts = (20000000,)
		unspentAsInputs = (('txid1', 0, 'scriptPubKey1'),)
		unspent = (unspentAmounts, unspentAsInputs)
		changeAddress = b'change'

		swapBillTransaction = MockTransaction()
		swapBillTransaction.typeCode = 0
		swapBillTransaction.amount = 1000
		swapBillTransaction.maxBlock = 10000
		swapBillTransaction.extraData = b'.' * 6
		swapBillTransaction.controlAddressAmount = 999

		hostTX = BuildHostedTransaction.Build_FundedByAccount(dustLimit, transactionFee, swapBillTransaction, unspent, changeAddress)
		SanityChecks(transactionFee, unspent, hostTX)
		self.assertTupleEqual(AsData(hostTX), ([('txid1', 0)],[(b"SWB\x00\xe8\x03\x00\x00\x00\x00\x10'\x00\x00......", 999), (b'change', 19899001)]))

		swapBillTransaction = MockTransaction()
		swapBillTransaction.typeCode = 1
		swapBillTransaction.amount = 1001
		swapBillTransaction.maxBlock = 10001
		swapBillTransaction.extraData = b'-' * 6
		swapBillTransaction.destinations = (b'destination',)

		hostTX = BuildHostedTransaction.Build_FundedByAccount(dustLimit, transactionFee, swapBillTransaction, unspent, changeAddress)
		SanityChecks(transactionFee, unspent, hostTX)
		self.assertTupleEqual(AsData(hostTX), ([('txid1', 0)],[(b"SWB\x01\xe9\x03\x00\x00\x00\x00\x11'\x00\x00------", 10), (b'destination', 10), (b'change', 19899980)]))

		swapBillTransaction = MockTransaction()
		swapBillTransaction.typeCode = 2
		swapBillTransaction.source = b'source'
		swapBillTransaction.amount = 2002
		swapBillTransaction.maxBlock = 0xffffff
		swapBillTransaction.extraData = b'.' * 6
		swapBillTransaction.destinations = (b'destination',)

		sourceAddressSingleUnspent = (1000000, ('txid2', 1, 'scriptPubKey2'))

		hostTX = BuildHostedTransaction.Build_WithSourceAddress(dustLimit, transactionFee, swapBillTransaction, sourceAddressSingleUnspent, unspent, changeAddress)
		SanityChecks(transactionFee, unspent, hostTX, sourceAddressSingleUnspent)
		self.assertTupleEqual(AsData(hostTX), ([('txid2', 1)],[(b"SWB\x02\xd2\x07\x00\x00\x00\x00\xff\xff\xff\x00......", 10), (b'destination', 10), (b'source', 10), (b'change', 899970)]))

		# with multiple destinations
		swapBillTransaction.destinations = (b'destination', b'destination2')

		hostTX = BuildHostedTransaction.Build_WithSourceAddress(dustLimit, transactionFee, swapBillTransaction, sourceAddressSingleUnspent, unspent, changeAddress)
		SanityChecks(transactionFee, unspent, hostTX, sourceAddressSingleUnspent)
		self.assertTupleEqual(AsData(hostTX), ([('txid2', 1)],[(b"SWB\x02\xd2\x07\x00\x00\x00\x00\xff\xff\xff\x00......", 10), (b'destination', 10), (b'destination2', 10), (b'source', 10), (b'change', 899960)]))

		# with destination amount
		swapBillTransaction.destinations = (b'destination',)
		swapBillTransaction.destinationAmounts = (123,)

		hostTX = BuildHostedTransaction.Build_WithSourceAddress(dustLimit, transactionFee, swapBillTransaction, sourceAddressSingleUnspent, unspent, changeAddress)
		SanityChecks(transactionFee, unspent, hostTX, sourceAddressSingleUnspent)
		self.assertTupleEqual(AsData(hostTX), ([('txid2', 1)],[(b"SWB\x02\xd2\x07\x00\x00\x00\x00\xff\xff\xff\x00......", 10), (b'destination', 123), (b'source', 10), (b'change', 899857)]))

		# with multiple destination amounts
		swapBillTransaction.destinations = (b'destination', b'destination2')
		swapBillTransaction.destinationAmounts = (123, 456)

		hostTX = BuildHostedTransaction.Build_WithSourceAddress(dustLimit, transactionFee, swapBillTransaction, sourceAddressSingleUnspent, unspent, changeAddress)
		SanityChecks(transactionFee, unspent, hostTX, sourceAddressSingleUnspent)
		self.assertTupleEqual(AsData(hostTX), ([('txid2', 1)],[(b"SWB\x02\xd2\x07\x00\x00\x00\x00\xff\xff\xff\x00......", 10), (b'destination', 123), (b'destination2', 456), (b'source', 10), (b'change', 899401)]))

## TODO test error reporting

	def test_regression(self):
		sbTX = MockTransaction()
		sbTX.typeCode = 0 ## not relevant to this unit test

		## case where source was not being reseeded, due to smallest inputs exactly meeting requirements for control and dest
		sbTX.source = b'bob'
		sbTX.amount = 10000000
		sbTX.maxBlock = 0xffffff
		sbTX.extraData = b'.' * 6
		sbTX.destinations = (b'bob_LTC_Receive',)
		sourceSingleUnspent = (100000, ('tx2', 0, 'script pub key for bob'))
		unspent = ([100000, 9700000, 100000], [('tx6', 2, 'script pub key for alice_LTC_Receive'), ('tx7', 3, 'script pub key for change'), ('tx8', 0, 'script pub key for alice')])
		transactionFee = 100000
		hostTX = BuildHostedTransaction.Build_WithSourceAddress(
		    dustLimit=100000, transactionFee=transactionFee,
		    swapBillTransaction=sbTX, sourceAddressSingleUnspent=sourceSingleUnspent, backerAccountUnspent=unspent, changePubKeyHash=b'change')
		SanityChecks(transactionFee, unspent, hostTX, sourceSingleUnspent)
		self.assertEqual(hostTX.numberOfOutputs(), 4)
		expectedInputs = [('tx6', 2), ('tx8', 0), ('tx7', 3), ('tx2', 0)]
		expectedOutputs = [(b'SWB\x00\x80\x96\x98\x00\x00\x00\xff\xff\xff\x00......', 100000), (b'bob_LTC_Receive', 100000), (b'bob', 100000), (b'change', 9600000)]
		self.assertTupleEqual(AsData(hostTX), (expectedInputs, expectedOutputs))
