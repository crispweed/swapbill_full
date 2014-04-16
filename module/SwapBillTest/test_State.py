from __future__ import print_function
import unittest
from SwapBill import State

class Test(unittest.TestCase):
	def test_state_setup(self):
		state = State.State(100, 'mockhash')
		assert state.startBlockMatches('mockhash')
		assert not state.startBlockMatches('mockhosh')

	def test_transactions(self):
		state = State.State(100, 'mockhash')

		## TODO need to be careful that transaction type and arguments match between checkWouldApplySuccessfully_ and apply_ call in the stuff below
		## split out at least arguments into a variable

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_Burn(10, 'a')
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_Burn(10, 'a')

		self.assertEqual(state._balances, {'a':10})

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_Burn(20, 'b')
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_Burn(20, 'b')

		self.assertEqual(state._balances, {'a':10, 'b':20})

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_Burn(30, 'c')
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_Burn(30, 'c')

		self.assertEqual(state._balances, {'a':10, 'b':20, 'c':30})

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_Transfer('c', 20, 'a')
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_Transfer('c', 20, 'a')

		self.assertEqual(state._balances, {'a':30, 'b':20, 'c':10})

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_Transfer('c', 15, 'a')
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'insufficient balance in source account (transfer capped)')
		state.apply_Transfer('c', 15, 'a')

		self.assertEqual(state._balances, {'a':40, 'b':20})

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_Transfer('c', 5, 'a')
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'source account balance is 0')
		state.apply_Transfer('c', 5, 'a')

		self.assertEqual(state._balances, {'a':40, 'b':20})

		# cannot post buy or sell offers, because of minimum exchange amount constraint

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_AddLTCBuyOffer('a', 30, 0x80000000, 200, 'a_receive')
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount (offer not posted)')
		state.apply_AddLTCBuyOffer('a', 30, 0x80000000, 200, 'a_receive')

		self.assertEqual(state._balances, {'a':40, 'b':20})

		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_AddLTCSellOffer('b', 300, 0x80000000, 200)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount (offer not posted)')
		state.apply_AddLTCSellOffer('a', 300, 0x80000000, 200)

		self.assertEqual(state._balances, {'a':40, 'b':20})

		# let's give these guys some real money, and then try again

		state.apply_Burn(100000000, 'a')
		state.apply_Burn(200000000, 'b')
		state.apply_Burn(200000000, 'c')
		self.assertEqual(state._balances, {'a': 100000040, 'b': 200000020, 'c': 200000000})

		# a wants to buy

		# try offering more than available
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_AddLTCBuyOffer('a', 3000000000, 0x80000000, 200, 'a_receive')
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'insufficient balance in source account (offer not posted)')
		state.apply_AddLTCBuyOffer('a', 3000000000, 0x80000000, 200, 'a_receive')

		self.assertEqual(state._balances, {'a': 100000040, 'b': 200000020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)

		# reasonable buy offer that should go through
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_AddLTCBuyOffer('a', 30000000, 0x80000000, 200, 'a_receive')
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_AddLTCBuyOffer('a', 30000000, 0x80000000, 200, 'a_receive')

		self.assertEqual(state._balances, {'a': 70000040, 'b': 200000020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 1)

		# b wants to sell

		# try offering more than available
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_AddLTCSellOffer('b', 40000000000, 0x80000000, 200)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'insufficient balance for deposit in source account (offer not posted)')
		state.apply_AddLTCSellOffer('b', 40000000000, 0x80000000, 200)

		self.assertEqual(state._balances, {'a': 70000040, 'b': 200000020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 0)

		# reasonable sell offer that should go through (and match)
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_AddLTCSellOffer('b', 40000000, 0x80000000, 200)
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_AddLTCSellOffer('b', 40000000, 0x80000000, 200)

		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# b must now complete with appropriate ltc payment

		# bad pending exchange index
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_CompleteLTCExchange(1, 'a_receive', 20000000)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'no pending exchange with the specified index (transaction ignored)')
		state.apply_CompleteLTCExchange(1, 'a_receive', 20000000)

		# no state change
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# bad receive address
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_CompleteLTCExchange(0, 'randomAddress', 20000000)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'destination account does not match destination for pending exchange with the specified index (transaction ignored)')
		state.apply_CompleteLTCExchange(0, 'randomAddress', 20000000)

		# no state change
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# insufficient payment
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_CompleteLTCExchange(0, 'a_receive', 200)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'amount is less than required payment amount (transaction ignored)')
		state.apply_CompleteLTCExchange(0, 'a_receive', 200)

		# no state change (b just loses these ltc)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# pays amount offered for sale, not the amount
		# state should warn us about the ltc overpay, and report the transaction as 'unsuccessful'
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_CompleteLTCExchange(0, 'a_receive', 20000000)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertEqual(reason, 'amount is greater than required payment amount (exchange completes, but with ltc overpay)')
		## TODO add check that this actually goes through
		#state.apply_CompleteLTCExchange(0, 'a_receive', 20000000)

		# pays actual amount required for match with a's buy offer
		# (well formed completion transaction which should go through)
		wouldApplySuccessfully, reason = state.checkWouldApplySuccessfully_CompleteLTCExchange(0, 'a_receive', 15000000)
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, '')
		state.apply_CompleteLTCExchange(0, 'a_receive', 15000000)

		# b gets
		# payment of the 30000000 offered by a
		# plus fraction of deposit for the amount matched (=1875000)
		# (the rest of the deposit is left with an outstanding remainder sell offer)

		self.assertEqual(state._balances, {'a': 70000040, 'b': 229375020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 0)

		## TODO - test for fail to complete due to expiry

		## TODO **** test exact match
		## TODO **** test outstanding buy remainder
		## TODO **** test discarded buy remainder
		## TODO **** test discarded sell remainder

	def test_ltc_trading(self):
		state = State.State(100, 'starthash')

		milliSatoshi = 100000

		state.apply_Burn(10000 * milliSatoshi, 'a')
		state.apply_Burn(10000 * milliSatoshi, 'b')

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'a': 10000 * milliSatoshi, 'b': 10000 * milliSatoshi})

		state.apply_AddLTCBuyOffer('a', 100 * milliSatoshi, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in a's balance to fund the offer, so the offer should be added, and the funding amount moved in to the offer
		self.assertEqual(state._balances['a'], 9900 * milliSatoshi)

		state.apply_AddLTCSellOffer('b', 160 * milliSatoshi, int(0.4 * 0x100000000), 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in b's balance to fund the offer, so the offer should be added, and the deposit amount moved in to the offer
		self.assertEqual(state._balances['b'], 9990 * milliSatoshi)

		self.assertEqual(state._pendingExchanges, {}) ## the offers so far don't match
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# c has no balance to fund the offer, so this offer should not be added, with no effect on state
		state.apply_AddLTCSellOffer('c', 320 * milliSatoshi, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		state.apply_AddLTCBuyOffer('c', 100 * milliSatoshi, 0x80000000, 150, 'c_receive_ltc')
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# same if there is some swapbill in c's account, but not enough
		state.apply_Burn(10 * milliSatoshi, 'c')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.apply_AddLTCSellOffer('c', 320 * milliSatoshi, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		state.apply_AddLTCBuyOffer('c', 100 * milliSatoshi, 0x80000000, 150, 'c_receive_ltc')
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# now add just enough to make the sell offer
		state.apply_Burn(10 * milliSatoshi, 'c')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.apply_AddLTCSellOffer('c', 320 * milliSatoshi, int(0.6 * 0x100000000), 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 2)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._pendingExchanges[0].__dict__,
			{'expiry': 150, 'swapBillDeposit': 625000, 'ltc': 5499999, 'ltcReceiveAddress': 'a_receive_ltc', 'swapBillAmount': 10000000, 'buyerAddress': 'a', 'sellerAddress': 'c'})

		state.apply_Burn(500 * milliSatoshi, 'd')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		state.apply_AddLTCBuyOffer('d', 500 * milliSatoshi, int(0.3 * 0x100000000), 150, 'd_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 3)
		self.assertEqual(state._pendingExchanges[1].__dict__,
			{'expiry': 150, 'swapBillDeposit': 1375000, 'ltc': 9899999, 'ltcReceiveAddress': 'd_receive_ltc', 'swapBillAmount': 22000000, 'buyerAddress': 'd', 'sellerAddress': 'c'})
