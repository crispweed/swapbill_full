from __future__ import print_function
import unittest
from SwapBill import BuildHostedTransaction

class MockObject(object):
	pass
class MockTransaction(object):
	def encode(self):
		return self.amount, self.maxBlock, self.extraData

def SanityChecks(config, unspent, inputs, targetAddresses, targetAmounts):
	assert len(targetAddresses) == len(targetAmounts)
	for amount in targetAmounts:
		assert type(amount) is int
		assert amount > 0
	inputAmounts = []
	for input in inputs:
		i = unspent[1].index(input)
		inputAmounts.append(unspent[0][i])
	assert sum(inputAmounts) == sum(targetAmounts) + config.transactionFee

class Test(unittest.TestCase):
	def test(self):
		config = MockObject()
		config.dustOutputAmount = 10
		config.seedAmount = 1000
		config.minimumTransactionAmount = 10000000
		config.transactionFee = 100000
		config.addressVersion = b'\x6f'

		unspentAmounts = (20000000,)
		unspentAsInputs = (('txid1', 0, 'scriptPubKey1'),)
		unspent = (unspentAmounts, unspentAsInputs)
		changeAddress = 'changeAddress'
		seedDestination = True

		swapBillTransaction = MockTransaction()
		swapBillTransaction.typeCode = 0
		swapBillTransaction.amount = 1000
		swapBillTransaction.maxBlock = 10000
		swapBillTransaction.extraData = b'.' * 6
		swapBillTransaction.controlAddressAmount = 999

		inputs, targetAddresses, targetAmounts = BuildHostedTransaction.Build_FundedByAccount(config, swapBillTransaction, unspent, changeAddress, seedDestination)
		SanityChecks(config, unspent, inputs, targetAddresses, targetAmounts)

		#print(inputs)
		#print(targetAddresses.__repr__())
		#print(targetAmounts)
		assert inputs == [('txid1', 0, 'scriptPubKey1')]
		assert targetAddresses == ['mo7cukoTfzNpYmfyGE2NxgncGSEhQRLSpY', 'changeAddress']
		assert targetAmounts == [999, 19899001]

		swapBillTransaction = MockTransaction()
		swapBillTransaction.typeCode = 1
		swapBillTransaction.amount = 1001
		swapBillTransaction.maxBlock = 10001
		swapBillTransaction.extraData = b'-' * 6
		swapBillTransaction.destinationAddress = 'destination'

		inputs, targetAddresses, targetAmounts = BuildHostedTransaction.Build_FundedByAccount(config, swapBillTransaction, unspent, changeAddress, seedDestination)
		SanityChecks(config, unspent, inputs, targetAddresses, targetAmounts)

		#print(inputs)
		#print(targetAddresses.__repr__())
		#print(targetAmounts)
		assert inputs == [('txid1', 0, 'scriptPubKey1')]
		assert targetAddresses == ['mo7cuks3LbZwJNiM8NzcZ98fXhkwSXvbG4', 'destination', 'changeAddress']
		assert targetAmounts == [10, 1000, 19898990]

## TODO test error reporting (make errors into exceptions?)
