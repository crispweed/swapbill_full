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
		unspent = GetUnspent.GetUnspent(buildLayer, {})
		self.assertTupleEqual(unspent, ([], []))
		self.assertRaises(AssertionError, GetUnspent.GetUnspent_WithSingleSource, buildLayer, balances, 'b')
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'a')
		self.assertTupleEqual(unspent, ([], []))
		self.assertIsNone(singleSourceUnspent)
		seeded = GetUnspent.AddressesWithUnspent(buildLayer, {})
		self.assertSetEqual(seeded, set())

		# add one non swapbill unspent
		buildLayer._add('nonswapbill', 2, 'input1')

		unspent = GetUnspent.GetUnspent(buildLayer, {})
		self.assertTupleEqual(unspent, ([2], ['input1']))
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'a')
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertIsNone(singleSourceUnspent)
		seeded = GetUnspent.AddressesWithUnspent(buildLayer, {})
		self.assertSetEqual(seeded, set())

		# add one swapbill unspent
		buildLayer._add('b', 5, 'input2')
		# (not in balances initially)
		unspent = GetUnspent.GetUnspent(buildLayer, balances)
		self.assertTupleEqual(unspent, ([2, 5], ['input1', 'input2'])) ## don't actually care about order here, currently
		# (and then added to balances)
		balances['b'] = 88

		unspent = GetUnspent.GetUnspent(buildLayer, balances)
		self.assertTupleEqual(unspent, ([2], ['input1']))
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'a')
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertIsNone(singleSourceUnspent)
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'b')
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertEqual(singleSourceUnspent, (5, 'input2'))
		seeded = GetUnspent.AddressesWithUnspent(buildLayer, {})
		self.assertSetEqual(seeded, set())
		seeded = GetUnspent.AddressesWithUnspent(buildLayer, balances)
		self.assertSetEqual(seeded, set('b'))

		# add another swapbill unspent
		buildLayer._add('c', 9, 'input3')
		balances['c'] = 66

		unspent = GetUnspent.GetUnspent(buildLayer, balances)
		self.assertTupleEqual(unspent, ([2], ['input1']))
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'a')
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertIsNone(singleSourceUnspent)
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'b')
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertEqual(singleSourceUnspent, (5, 'input2'))
		unspent, singleSourceUnspent = GetUnspent.GetUnspent_WithSingleSource(buildLayer, balances, 'c')
		self.assertTupleEqual(unspent, ([2], ['input1']))
		self.assertEqual(singleSourceUnspent, (9, 'input3'))
		seeded = GetUnspent.AddressesWithUnspent(buildLayer, balances)
		self.assertSetEqual(seeded, set('bc'))

