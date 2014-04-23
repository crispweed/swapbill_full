from __future__ import print_function
import unittest
from SwapBill import GetUnspent

class MockBuildLayer(object):
	def __init__(self):
		self.addresses = []
		self.amounts = []
		self.asInputs = []
	def _add(self, address, amount, asInput):
		self.addresses.append(address)
		self.amounts.append(amount)
		self.asInputs.append(asInput)
	def getUnspent(self):
		return self.addresses, self.amounts, self.asInputs

class Test(unittest.TestCase):
	def test(self):
		buildLayer = MockBuildLayer()

		balances = {'a':11}

		# behaviour with no unspent available
		unspent, swapBillUnspent = GetUnspent.GetUnspent(buildLayer, {})
		self.assertTupleEqual(unspent, ([], []))
		self.assertDictEqual(swapBillUnspent, {})
				
		# add one non swapbill unspent
		buildLayer._add('nonswapbill', 2, 'input1')

		unspent, swapBillUnspent = GetUnspent.GetUnspent(buildLayer, {})
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertDictEqual(swapBillUnspent, {})

		# add one swapbill unspent
		buildLayer._add('b', 5, 'input2')
		# (not in balances initially)
		unspent, swapBillUnspent = GetUnspent.GetUnspent(buildLayer, balances)
		self.assertTupleEqual(unspent, ([2, 5], ['input1', 'input2'])) ## don't actually care about order here, currently
		self.assertDictEqual(swapBillUnspent, {})
		# (and then added to balances)
		balances['input2'] = 88
		unspent, swapBillUnspent = GetUnspent.GetUnspent(buildLayer, balances)
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertDictEqual(swapBillUnspent, {'input2': ('b', 5)})

		# add another swapbill unspent
		buildLayer._add('c', 9, 'input3')
		balances['input3'] = 66
		unspent, swapBillUnspent = GetUnspent.GetUnspent(buildLayer, balances)
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertDictEqual(swapBillUnspent, {'input2': ('b', 5), 'input3': ('c', 9)})

