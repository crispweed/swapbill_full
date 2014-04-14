from __future__ import print_function
import unittest
from SwapBill import LTCTrading, State

class MockObject(object):
	pass

class Test(unittest.TestCase):
	def test(self):
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x80000000, 122), 61)
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x40000000, 100), 25)
		self.assertEqual(LTCTrading.LTCWithExchangeRate(0x40000000, 101), 25)
		## TODO: define maximum range for swapbill values, and test with these

		milliSatoshi = 100000
		self.assertEqual(LTCTrading.minimumExchangeLTC, 10 * milliSatoshi)
		self.assertTrue(LTCTrading.SatisfiesMinimumExchange(0x80000000,  20 * milliSatoshi))
		self.assertFalse(LTCTrading.SatisfiesMinimumExchange(0x70000000,  20 * milliSatoshi))

		state = State.State(100, 'starthash')
		state.create(20000 * milliSatoshi)
		state.addToBalance('a', 10000 * milliSatoshi)
		state.addToBalance('b', 10000 * milliSatoshi)

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		state.requestAddLTCBuyOffer('a', 100 * milliSatoshi, 0x80000000, 150, 'a_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in a's balance to fund the offer, so the offer should be added, and the funding amount moved in to the offer
		self.assertEqual(state._balances['a'], 9900 * milliSatoshi)

		state.requestAddLTCSellOffer('b', 160 * milliSatoshi, 10 * milliSatoshi, int(0.4 * 0x100000000), 150)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in b's balance to fund the offer, so the offer should be added, and the deposit amount moved in to the offer
		self.assertEqual(state._balances['b'], 9990 * milliSatoshi)

		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		LTCTrading.Match(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertEqual(state._pendingExchanges, {}) ## the offers so far don't match
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# c has no balance to fund the offer, so this offer should not be added, with no effect on state
		state.requestAddLTCSellOffer('c', 320 * milliSatoshi, 20 * milliSatoshi, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		state.requestAddLTCBuyOffer('c', 100 * milliSatoshi, 0x80000000, 150, 'c_receive_ltc')
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# same if there is some swapbill in c's account, but not enough
		state.create(10 * milliSatoshi)
		state.addToBalance('c', 10 * milliSatoshi)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.requestAddLTCSellOffer('c', 320 * milliSatoshi, 20 * milliSatoshi, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		state.requestAddLTCBuyOffer('c', 100 * milliSatoshi, 0x80000000, 150, 'c_receive_ltc')
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# now add just enough to make the sell offer
		state.create(10 * milliSatoshi)
		state.addToBalance('c', 10 * milliSatoshi)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		state.requestAddLTCSellOffer('c', 320 * milliSatoshi, 20 * milliSatoshi, int(0.6 * 0x100000000), 150)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		LTCTrading.Match(state)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._pendingExchanges[0].__dict__,
			{'expiry': 150, 'swapBillDeposit': 625000, 'ltc': 5499999, 'ltcReceiveAddress': 'a_receive_ltc', 'swapBillAmount': 10000000, 'buyerAddress': 'a', 'sellerAddress': 'c'})

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		state.create(500 * milliSatoshi)
		state.addToBalance('d', 500 * milliSatoshi)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		state.requestAddLTCBuyOffer('d', 500 * milliSatoshi, int(0.3 * 0x100000000), 150, 'd_receive_ltc')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		LTCTrading.Match(state)
		self.assertEqual(len(state._pendingExchanges), 2)
		self.assertEqual(state._pendingExchanges[1].__dict__,
			{'expiry': 150, 'swapBillDeposit': 1375000, 'ltc': 9899999, 'ltcReceiveAddress': 'd_receive_ltc', 'swapBillAmount': 22000000, 'buyerAddress': 'd', 'sellerAddress': 'c'})

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
