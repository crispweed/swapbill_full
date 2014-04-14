from __future__ import print_function
import unittest
from SwapBill import State

class Test(unittest.TestCase):
	def test_balance_add_and_subtract(self):
		state = State.State(100, 'mockhash')
		assert state.startBlockMatches('mockhash')
		assert not state.startBlockMatches('mockhosh')
		state.addToBalance('a', 10)
		state.addToBalance('b', 20)
		state.addToBalance('c', 30)
		assert state._balances == {'a':10, 'b':20, 'c':30}
		#state.subtractFromBalance('a', 1)
		cappedAmount = state.subtractFromBalance_Capped('a', 1)
		assert cappedAmount == 1
		assert state._balances == {'a':9, 'b':20, 'c':30}
		cappedAmount = state.subtractFromBalance_Capped('a', 100)
		assert cappedAmount == 9
		assert state._balances == {'b':20, 'c':30}
		#state.subtractFromBalance('b', 20)
		cappedAmount = state.subtractFromBalance_Capped('b', 20)
		assert cappedAmount == 20
		assert state._balances == {'c':30}
