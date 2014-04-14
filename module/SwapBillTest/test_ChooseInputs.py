from __future__ import print_function
import unittest
from SwapBill import ChooseInputs

def _callWithSanityChecks(maxInputs, unspentAmounts, amountRequired):
	assignments, spent = ChooseInputs.ChooseInputs(maxInputs, unspentAmounts, amountRequired)
	assert type(assignments) is type([])
	assert type(spent) is int
	assert len(assignments) <= maxInputs
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
		self.assertRaises(AssertionError, ChooseInputs.ChooseInputs, 1, [9,5,8,5], -1)

		## allow zero maxInputs
		inputs, spent = _callWithSanityChecks(0, [9,5,8,5], 8)
		assert inputs == []

		## allow zero amountRequired
		inputs, spent = _callWithSanityChecks(1, [9,5,8,5], 0)
		assert inputs == []

		inputs, spent = _callWithSanityChecks(1, [9,5,8,5], 8)
		#print(inputs)
		assert inputs == [2]
		inputs, spent = _callWithSanityChecks(1, [9,5,8,5], 9)
		assert inputs == [0]
		inputs, spent = _callWithSanityChecks(1, [9,5,8,5], 10) ## fail to meet amount required, but return best
		assert inputs == [0]
		inputs, spent = _callWithSanityChecks(2, [9,5,8,5], 10)
		assert inputs == [1,3]
		inputs, spent = _callWithSanityChecks(2, [9,5,8,5], 11)
		assert inputs == [3,2]
		inputs, spent = _callWithSanityChecks(2, [9,5,8,5], 14)
		assert inputs == [2,0]
		inputs, spent = _callWithSanityChecks(3, [9,5,8,5], 1)
		assert inputs == [1]
		inputs, spent = _callWithSanityChecks(3, [9,5,8,5], 6)
		assert inputs == [1,3]
		inputs, spent = _callWithSanityChecks(3, [9,5,8,5], 11)
		assert inputs == [1,3,2]
		inputs, spent = _callWithSanityChecks(3, [9,5,8,5], 19)
		assert inputs == [3,2,0]
		inputs, spent = _callWithSanityChecks(3, [9,5,8,5], 30) ## fail to meet amount required, but return best
		assert inputs == [3,2,0]

