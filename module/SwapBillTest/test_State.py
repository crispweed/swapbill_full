from __future__ import print_function
import unittest
from SwapBill import State

milliCoin = 100000

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


	def test_ltc_trading(self):
		state = State.State(100, 'starthash')

		state.apply_Burn(10000 * milliCoin, 'a')
		state.apply_Burn(10000 * milliCoin, 'b')

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'a': 10000 * milliCoin, 'b': 10000 * milliCoin})

		state.apply_AddLTCBuyOffer('a', 100 * milliCoin, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in a's balance to fund the offer, so the offer should be added, and the funding amount moved in to the offer
		self.assertEqual(state._balances['a'], 9900 * milliCoin)

		state.apply_AddLTCSellOffer('b', 160 * milliCoin, int(0.4 * 0x100000000), 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in b's balance to fund the offer, so the offer should be added, and the deposit amount moved in to the offer
		self.assertEqual(state._balances['b'], 9990 * milliCoin)

		self.assertEqual(state._pendingExchanges, {}) ## the offers so far don't match
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# c has no balance to fund the offer, so this offer should not be added, with no effect on state
		state.apply_AddLTCSellOffer('c', 320 * milliCoin, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		state.apply_AddLTCBuyOffer('c', 100 * milliCoin, 0x80000000, 150, 'c_receive_ltc')
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# same if there is some swapbill in c's account, but not enough
		state.apply_Burn(10 * milliCoin, 'c')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.apply_AddLTCSellOffer('c', 320 * milliCoin, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		state.apply_AddLTCBuyOffer('c', 100 * milliCoin, 0x80000000, 150, 'c_receive_ltc')
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# now add just enough to make the sell offer
		state.apply_Burn(10 * milliCoin, 'c')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.apply_AddLTCSellOffer('c', 320 * milliCoin, int(0.6 * 0x100000000), 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 2)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._pendingExchanges[0].__dict__,
			{'expiry': 150, 'swapBillDeposit': 625000, 'ltc': 5499999, 'ltcReceiveAddress': 'a_receive_ltc', 'swapBillAmount': 10000000, 'buyerAddress': 'a', 'sellerAddress': 'c'})

		state.apply_Burn(500 * milliCoin, 'd')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		state.apply_AddLTCBuyOffer('d', 500 * milliCoin, int(0.3 * 0x100000000), 150, 'd_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 3)
		self.assertEqual(state._pendingExchanges[1].__dict__,
			{'expiry': 150, 'swapBillDeposit': 1375000, 'ltc': 9899999, 'ltcReceiveAddress': 'd_receive_ltc', 'swapBillAmount': 22000000, 'buyerAddress': 'd', 'sellerAddress': 'c'})

	def test_small_sell_remainder_refunded(self):
		state = State.State(100, 'starthash')
		state.apply_Burn(10000000, 'b')
		state.apply_AddLTCSellOffer('b', 10000000, 0x80000000, 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.apply_Burn(9900000, 'a')
		state.apply_AddLTCBuyOffer('a', 9900000, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# b should be refunded 100000 // 10000000 of his depost = 6250
		# balance is the 9375000 + 6250
		self.assertEqual(state._balances, {'b': 9381250})
		self.assertEqual(len(state._pendingExchanges), 1)
		state.apply_CompleteLTCExchange(0, 'a_receive_ltc', 5000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 19900000})

	def test_small_buy_remainder_refunded(self):
		state = State.State(100, 'starthash')
		state.apply_Burn(10000000, 'b')
		state.apply_AddLTCSellOffer('b', 10000000, 0x80000000, 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.apply_Burn(10100000, 'a')
		state.apply_AddLTCBuyOffer('a', 10100000, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# a should be refunded 100000 remainder from buy offer
		self.assertEqual(state._balances, {'a': 100000, 'b': 9375000})
		self.assertEqual(len(state._pendingExchanges), 1)
		state.apply_CompleteLTCExchange(0, 'a_receive_ltc', 5000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'a': 100000, 'b': 20000000})

	def test_exact_match(self):
		state = State.State(100, 'starthash')
		state.apply_Burn(10000000, 'b')
		state.apply_AddLTCSellOffer('b', 10000000, 0x80000000, 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.apply_Burn(10000000, 'a')
		state.apply_AddLTCBuyOffer('a', 10000000, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 9375000})
		self.assertEqual(len(state._pendingExchanges), 1)
		state.apply_CompleteLTCExchange(0, 'a_receive_ltc', 5000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 20000000})

	def test_sell_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		state.apply_Burn(20000000, 'b')
		state.apply_AddLTCSellOffer('b', 20000000, 0x80000000, 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {'b': 18750000})
		state.apply_Burn(10000000, 'a')
		state.apply_AddLTCBuyOffer('a', 10000000, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 18750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1) ## half of sell offer is left outstanding
		state.apply_CompleteLTCExchange(0, 'a_receive_ltc', 5000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded half his deposit, remaining deposit = 625000
		# and b now has all swapbill except deposit for outstanding sell offer
		self.assertEqual(state._balances, {'b': 29375000})
		# a goes on to buy the rest
		state.apply_Burn(10000000, 'a')
		state.apply_AddLTCBuyOffer('a', 10000000, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.apply_CompleteLTCExchange(1, 'a_receive_ltc', 5000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'b': 40000000})

	def test_buy_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		state.apply_Burn(20000000, 'b')
		state.apply_AddLTCSellOffer('b', 20000000, 0x80000000, 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {'b': 18750000})
		state.apply_Burn(30000000, 'a')
		state.apply_AddLTCBuyOffer('a', 30000000, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 18750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 1) ## half of buy offer is left outstanding
		self.assertEqual(state._LTCSells.size(), 0)
		state.apply_CompleteLTCExchange(0, 'a_receive_ltc', 10000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded all his deposit, and receives payment in swapbill
		self.assertEqual(state._balances, {'b': 40000000})
		# b goes on to sell the rest
		state.apply_Burn(10000000, 'b')
		state.apply_AddLTCSellOffer('b', 10000000, 0x80000000, 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.apply_CompleteLTCExchange(1, 'a_receive_ltc', 10000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'b': 60000000})

## TODO tests for offer matching multiple other offers
