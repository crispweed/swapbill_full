from __future__ import print_function
import unittest
from SwapBill import ChooseInputs

def _callWithSanityChecks(unspentAmounts, amountRequired):
	assignments, spent = ChooseInputs.ChooseInputs(unspentAmounts, amountRequired)
	assert type(assignments) is type([])
	assert type(spent) is int
	used = set()
	spent_Check = 0
	for i in assignments:
		assert type(i) is int
		assert i >= 0 and i < len(unspentAmounts)
		assert not i in used
		used.add(i)
		spent_Check += unspentAmounts[i]
	assert spent_Check == spent
	return assignments, spent

class Test(unittest.TestCase):
	def test(self):
		## test some assertion conditions
		self.assertRaises(AssertionError, ChooseInputs.ChooseInputs, [9,5,8,5], -1)

		## allow zero amountRequired
		inputs, spent = _callWithSanityChecks([9,5,8,5], 0)
		assert inputs == []

		inputs, spent = _callWithSanityChecks([9,5,8,5], 19)
		self.assertListEqual(inputs, [1,3,2,0])
