from __future__ import print_function
import unittest
from SwapBill.BuildHostedTransaction import AddPaymentFeesAndChange
from SwapBill.HostTransaction import AsData, FromData

def AmountForInput(resultTX, i, unspent):
	assert len(unspent[0]) == len(unspent[1])
	for j in range(len(unspent[0])):
		amount = unspent[0][j]
		unspentInput = unspent[1][j]
		if unspentInput[0] == resultTX.inputTXID(i) and unspentInput[1] == resultTX.inputVOut(i):
			return amount
	raise Exception('input not found')

class Test(unittest.TestCase):

	def SanityChecks(self, transactionFee, dustLimit, unspent, resultTX, numberOfBaseInputs=0, baseInputsAmount=0):
		inputTotal = baseInputsAmount
		for i in range(resultTX.numberOfInputs()):
			if i >= numberOfBaseInputs:
				inputTotal += AmountForInput(resultTX, i, unspent)
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

		baseTX = FromData(([],[(b'controlAddress', 999)]))
		resultTX = AddPaymentFeesAndChange(baseTX, 0, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX)
		self.assertTupleEqual(AsData(resultTX), ([('txid1', 0)],[(b"controlAddress", 999), (b'change', 19899001)]))

		baseTX = FromData(([],[(b'controlAddress', 0), (b'destination', 0)]))
		resultTX = AddPaymentFeesAndChange(baseTX, 0, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX)
		self.assertTupleEqual(AsData(resultTX), ([('txid1', 0)],[(b"controlAddress", 10), (b'destination', 10), (b'change', 19899980)]))

		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 0)]))
		baseInputsAmount = 1000000
		resultTX = AddPaymentFeesAndChange(baseTX, baseInputsAmount, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, 1, baseInputsAmount)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 10), (b'change', 899980)]))

		# with multiple destinations
		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 0), (b'destination2', 0)]))
		resultTX = AddPaymentFeesAndChange(baseTX, baseInputsAmount, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, 1, baseInputsAmount)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 10), (b'destination2', 10), (b'change', 899970)]))

		# with destination amount
		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 123)]))
		resultTX = AddPaymentFeesAndChange(baseTX, baseInputsAmount, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, 1, baseInputsAmount)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 123), (b'change', 899867)]))

		# with multiple destination amounts
		baseTX = FromData(([('txid2', 1)],[(b'controlAddress', 0), (b'destination', 123), (b'destination2', 456)]))
		resultTX = AddPaymentFeesAndChange(baseTX, baseInputsAmount, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX, 1, baseInputsAmount)
		self.assertTupleEqual(AsData(resultTX), ([('txid2', 1)],[(b"controlAddress", 10), (b'destination', 123), (b'destination2', 456), (b'change', 899411)]))

	def test_Regression(self):
		# it is now expected for transaction fee to be overpaid, in some cases
		# because if change is less than dust limit, this goes into the transaction fee
		# as shown in this example
		# (could potentially add this to one of the other outputs, but this complicates things)
		dustLimit = 100000
		transactionFee = 100000
		unspentAmounts = (100000, 100000, 200000, 300000)
		unspentAsInputs = [('1', 7), ('4', 0), ('2', 7), ('3', 7)]
		unspent = (unspentAmounts, unspentAsInputs)
		changeAddress = b'change'
		baseTX = FromData(([],[(b'controlAddress', 150000), (b'destAddress', 0)]))
		resultTX = AddPaymentFeesAndChange(baseTX, 0, dustLimit, transactionFee, unspent, changeAddress)
		self.SanityChecks(transactionFee, dustLimit, unspent, resultTX)
		self.assertTupleEqual(AsData(resultTX), ([('1', 7), ('4', 0), ('2', 7)],[(b"controlAddress", 150000), (b'destAddress', 100000)]))
