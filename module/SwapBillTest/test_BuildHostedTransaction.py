from __future__ import print_function
import unittest
from SwapBill.BuildHostedTransaction import AddPaymentFeesAndChange
from SwapBill.HostTransaction import AsData, FromData

def AmountForInput(resultTX, i, unspent, sourceLookup):
	assert len(unspent[0]) == len(unspent[1])
	for j in range(len(unspent[0])):
		amount = unspent[0][j]
		unspentInput = unspent[1][j]
		if unspentInput[0] == resultTX.inputTXID(i) and unspentInput[1] == resultTX.inputVOut(i):
			return amount
	# if we get here then sourceLookup must be set and match
	return sourceLookup.lookupAmountForTXInput(resultTX.inputTXID(i), resultTX.inputVOut(i))

class MockSourceLookup(object):
	def __init__(self, txID, vOut, amount):
		self._txID = txID
		self._vOut = vOut
		self._amount = amount
	def lookupAmountForTXInput(self, txID, vOut):
		assert txID == self._txID
		assert vOut == self._vOut
		return self._amount

class Test(unittest.TestCase):

	def SanityChecks(self, transactionFee, dustLimit, unspent, resultTX, sourceLookup=None):
		inputTotal = 0
		for i in range(resultTX.numberOfInputs()):
			inputTotal += AmountForInput(resultTX, i, unspent, sourceLookup)
		transactionFeePaid = inputTotal - resultTX.sumOfOutputs()
		self.assertTrue(transactionFeePaid >= transactionFee)
		self.assertTrue(transactionFeePaid < transactionFee + dustLimit)

	def test(self):
		dustLimit = 10
		transactionFee = 100000

		unspentAmounts = (20000000,)
		unspentAsInputs = (('txid1', 0),)
		unspent = (unspentAmounts, unspentAsInputs)
		changeAddress = b'change'

		#baseTX = FromData(([('txid1', 0)],[(b'controlAddress', 0)]))
		baseTX = FromData(([],[(b'controlAddress', 999)]))
		#sourceLookup = MockSourceLookup()
		resultTX = AddPaymentFeesAndChange(baseTX, None, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX)
		self.assertTupleEqual(AsData(resultTX), ([('txid1', 0)],[(b"controlAddress", 999), (b'change', 19899001)]))

		baseTX = FromData(([],[(b'controlAddress', 0), (b'destination', 0)]))
		resultTX = AddPaymentFeesAndChange(baseTX, None, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX)
		self.assertTupleEqual(AsData(resultTX), ([('txid1', 0)],[(b"controlAddress", 10), (b'destination', 10), (b'change', 19899980)]))

		#swapBillTransaction.source = b'source'
		#swapBillTransaction.destinations = (b'destination',)
		#sourceAddressSingleUnspent = (1000000, ('txid2', 1, 'scriptPubKey2'))

		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 0)]))
		sourceLookup = MockSourceLookup('txid2', 1, 1000000)
		resultTX = AddPaymentFeesAndChange(baseTX, sourceLookup, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, sourceLookup)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 10), (b'change', 899980)]))

		# with multiple destinations
		#swapBillTransaction.destinations = (b'destination', b'destination2')
		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 0), (b'destination2', 0)]))
		resultTX = AddPaymentFeesAndChange(baseTX, sourceLookup, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, sourceLookup)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 10), (b'destination2', 10), (b'change', 899970)]))

		# with destination amount
		#swapBillTransaction.destinations = (b'destination',)
		#swapBillTransaction.destinationAmounts = (123,)
		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 123)]))
		resultTX = AddPaymentFeesAndChange(baseTX, sourceLookup, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, sourceLookup)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 123), (b'change', 899867)]))

		# with multiple destination amounts
		#swapBillTransaction.destinations = (b'destination', b'destination2')
		#swapBillTransaction.destinationAmounts = (123, 456)
		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 123), (b'destination2', 456)]))
		resultTX = AddPaymentFeesAndChange(baseTX, sourceLookup, dustLimit, transactionFee, unspent, changeAddress)
		#resultTX = BuildHostedTransaction.Build_WithSourceAddress(dustLimit, transactionFee, swapBillTransaction, sourceAddressSingleUnspent, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, sourceLookup)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 123), (b'destination2', 456), (b'change', 899411)]))

	def test_Regression(self):
		# it is now expected for transaction fee to be overpaid, in some cases
		# because if change is less than dust limit, this goes into the transaction fee
		# as shown in this example
		# (could potentially add this to one of the other outputs, but this complicates things)
		dustLimit = 100000
		transactionFee = 100000
		unspentAmounts = (100000, 200000, 300000, 100000)
		unspentAsInputs = [('1', 7), ('2', 7), ('3', 7), ('4', 0)]
		unspent = (unspentAmounts, unspentAsInputs)
		changeAddress = b'change'
		baseTX = FromData(([],[(b'controlAddress', 150000), (b'destAddress', 0)]))
		resultTX = AddPaymentFeesAndChange(baseTX, None, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, dustLimit)
		self.assertTupleEqual(AsData(resultTX), ([('1', 7), ('4', 0), ('2', 7)],[(b"controlAddress", 150000), (b'destAddress', 100000)]))
