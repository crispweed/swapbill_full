from __future__ import print_function
import unittest
from SwapBill import TransactionFee

class Test(unittest.TestCase):
	def test(self):
		byteSize = TransactionFee.startingMaximumSize
		transactionFee = TransactionFee.startingFee
		outputs = [TransactionFee.dustLimit] * 10
		outputs.append(TransactionFee.dustLimit * 2)
		self.assertEqual(transactionFee, TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputs))
		byteSize += 1
		transactionFee += TransactionFee.feeStep
		self.assertEqual(transactionFee, TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputs))
		byteSize = TransactionFee.startingMaximumSize + TransactionFee.sizeStep
		self.assertEqual(transactionFee, TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputs))
		byteSize += 1
		transactionFee += TransactionFee.feeStep
		self.assertEqual(transactionFee, TransactionFee.CalculateRequired_FromSizeAndOutputs(byteSize, outputs))

	def test_dust_limit_assert(self):
		byteSize = TransactionFee.startingMaximumSize
		transactionFee = TransactionFee.startingFee
		outputs = [TransactionFee.dustLimit-1]
		self.assertRaises(AssertionError, TransactionFee.CalculateRequired_FromSizeAndOutputs, byteSize, outputs)
