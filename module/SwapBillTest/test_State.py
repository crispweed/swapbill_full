from __future__ import print_function
import unittest
from SwapBill import State

milliCoin = 100000

def Pack(**details):
	return details

class Test(unittest.TestCase):
	def test_state_setup(self):
		state = State.State(100, 'mockhash')
		assert state.startBlockMatches('mockhash')
		assert not state.startBlockMatches('mockhosh')

	def Apply_AssertSucceeds(self, state, transactionType, **details):
		## note that applyTransaction now calls check and asserts success internally
		## but this then also asserts that there is no warning
		succeeds, reason = state.checkTransaction(transactionType, details)
		self.assertEqual(succeeds, True)
		self.assertEqual(reason, '')
		state.applyTransaction(transactionType, details)

	def Apply_AssertFails(self, state, transactionType, **details):
		wouldApplySuccessfully, reason = state.checkTransaction(transactionType, details)
		self.assertEqual(wouldApplySuccessfully, False)
		self.assertRaises(AssertionError, state.applyTransaction, transactionType, details)
		return reason

	def test_transactions(self):
		state = State.State(100, 'mockhash')

		self.Apply_AssertSucceeds(state, 'Burn', amount=10, destinationAccount='a')
		self.assertEqual(state._balances, {'a':10})
		self.Apply_AssertSucceeds(state, 'Burn', amount=20, destinationAccount='b')
		self.assertEqual(state._balances, {'a':10, 'b':20})
		self.Apply_AssertSucceeds(state, 'Burn', amount=30, destinationAccount='c')
		self.assertEqual(state._balances, {'a':10, 'b':20, 'c':30})

		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount='c', changeAccount='c', amount=20, destinationAccount='a', maxBlock=200)
		self.assertEqual(state._balances, {'a':30, 'b':20, 'c':10})

		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount='c', changeAccount='c', amount=15, destinationAccount='a', maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {'a':30, 'b':20, 'c':10})

		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount='c', changeAccount='c', amount=10, destinationAccount='a', maxBlock=200)
		self.assertEqual(state._balances, {'a':40, 'b':20})

		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount='c', changeAccount='c', amount=15, destinationAccount='a', maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {'a':40, 'b':20})

		# cannot post buy or sell offers, because of minimum exchange amount constraint

		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=30, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive', maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount (offer not posted)')
		self.assertEqual(state._balances, {'a':40, 'b':20})

		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=300, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount (offer not posted)')
		self.assertEqual(state._balances, {'a':40, 'b':20})

		# let's give these guys some real money, and then try again

		self.Apply_AssertSucceeds(state, 'Burn', amount=100000000, destinationAccount='a')
		self.Apply_AssertSucceeds(state, 'Burn', amount=200000000, destinationAccount='b')
		self.Apply_AssertSucceeds(state, 'Burn', amount=200000000, destinationAccount='c')
		self.assertEqual(state._balances, {'a': 100000040, 'b': 200000020, 'c': 200000000})

		# a wants to buy

		# try offering more than available
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=3000000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive', maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (offer not posted)')
		self.assertEqual(state._balances, {'a': 100000040, 'b': 200000020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)

		# reasonable buy offer that should go through
		self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=30000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive', maxBlock=200)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 200000020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 1)

		# b wants to sell

		# try offering more than available
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=40000000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance for deposit in source account (offer not posted)')
		self.assertEqual(state._balances, {'a': 70000040, 'b': 200000020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 0)

		# reasonable sell offer that should go through (and match)
		self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=40000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# b must now complete with appropriate ltc payment

		# bad pending exchange index
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=1, destinationAccount='a_receive', destinationAmount=20000000)
		self.assertEqual(reason, 'no pending exchange with the specified index (transaction ignored)')
		# no state change
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# bad receive address
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAccount='randomAddress', destinationAmount=20000000)
		self.assertEqual(reason, 'destination account does not match destination for pending exchange with the specified index (transaction ignored)')
		# no state change
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# insufficient payment
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAccount='a_receive', destinationAmount=14999999)
		self.assertEqual(reason, 'amount is less than required payment amount (transaction ignored)')
		# no state change (b just loses these ltc)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# pays amount offered for sale, not the amount
		# state should warn us about the ltc overpay, but allow the transaction to go through
		details= {'pendingExchangeIndex':0, 'destinationAccount':'a_receive', 'destinationAmount':20000000}
		wouldApplySuccessfully, reason = state.checkTransaction('LTCExchangeCompletion', details)
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, 'amount is greater than required payment amount (exchange completes, but with ltc overpay)')

		# pays actual amount required for match with a's buy offer
		# (well formed completion transaction which should go through)
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAccount='a_receive', destinationAmount=15000000)
		# b gets
		# payment of the 30000000 offered by a
		# plus fraction of deposit for the amount matched (=1875000)
		# (the rest of the deposit is left with an outstanding remainder sell offer)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 229375020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 0)

		self.Apply_AssertSucceeds(state, 'ForwardToFutureNetworkVersion', sourceAccount='a', amount=1, maxBlock=200)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._totalForwarded, 1)

	def test_pay(self):
		state = State.State(100, 'mockhash')
		self.Apply_AssertSucceeds(state, 'Burn', amount=20, destinationAccount='b')
		self.Apply_AssertSucceeds(state, 'Burn', amount=30, destinationAccount='c')
		self.Apply_AssertSucceeds(state, 'Burn', amount=10, destinationAccount='a')
		self.assertEqual(state._balances, {'a':10, 'b':20, 'c':30})
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount='a', amount=3, destinationAccount='c', changeAccount='a2', maxBlock=200)
		self.assertEqual(state._balances, {'a2':7, 'b':20, 'c':33})
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount='a2', amount=8, destinationAccount='c', changeAccount='a3', maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {'a2':7, 'b':20, 'c':33})
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount='a2', amount=5, destinationAccount='c', changeAccount='a3', maxBlock=99)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances, {'a2':7, 'b':20, 'c':33})
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount='a2', amount=5, destinationAccount='b', changeAccount='a3', maxBlock=100)
		self.assertEqual(state._balances, {'a3':2, 'b':25, 'c':33})

	def test_ltc_trading(self):
		state = State.State(100, 'starthash')

		state.applyTransaction('Burn', {'amount':10000 * milliCoin, 'destinationAccount':'a'})
		state.applyTransaction('Burn', {'amount':10000 * milliCoin, 'destinationAccount':'b'})

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'a': 10000 * milliCoin, 'b': 10000 * milliCoin})

		details = Pack(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=100 * milliCoin, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		state.applyTransaction('LTCBuyOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in a's balance to fund the offer, so the offer should be added, and the funding amount moved in to the offer
		self.assertEqual(state._balances['a'], 9900 * milliCoin)

		details = Pack(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=160 * milliCoin, exchangeRate=int(0.4 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		state.applyTransaction('LTCSellOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in b's balance to fund the offer, so the offer should be added, and the deposit amount moved in to the offer
		self.assertEqual(state._balances['b'], 9990 * milliCoin)

		self.assertEqual(state._pendingExchanges, {}) ## the offers so far don't match
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# c has no balance to fund the offer, so this offer should not be added, with no effect on state
		details = Pack(sourceAccount='c', changeAccount='c', receivingAccount='c', swapBillDesired=320 * milliCoin, exchangeRate=int(0.6 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		result = state.checkTransaction('LTCSellOffer', details)
		self.assertEqual(result, (False, 'insufficient balance for deposit in source account (offer not posted)'))
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCSellOffer', details)

		# same for buy offers
		details = Pack(sourceAccount='c', changeAccount='c', refundAccount='c', swapBillOffered=100 * milliCoin, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='c_receive_ltc', maxBlock=200)
		result = state.checkTransaction('LTCBuyOffer', details)
		self.assertEqual(result, (False, 'insufficient balance in source account (offer not posted)'))
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCBuyOffer', details)

		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# same if there is some swapbill in c's account, but not enough
		details = Pack(amount=10 * milliCoin, destinationAccount='c')
		state.applyTransaction('Burn', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		details = Pack(sourceAccount='c', changeAccount='c', receivingAccount='c', swapBillDesired=320 * milliCoin, exchangeRate=int(0.6 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCSellOffer', details)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		details = Pack(sourceAccount='c', changeAccount='c', refundAccount='c', swapBillOffered=100 * milliCoin, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='c_receive_ltc', maxBlock=200)
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCBuyOffer', details)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# now add just enough to make the sell offer
		state.applyTransaction('Burn', {'amount':10 * milliCoin, 'destinationAccount':'c'})
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		details = Pack(sourceAccount='c', changeAccount='c', receivingAccount='c', swapBillDesired=320 * milliCoin, exchangeRate=int(0.6 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		state.applyTransaction('LTCSellOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 2)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._pendingExchanges[0].__dict__,
			{'expiry': 150, 'swapBillDeposit': 625000, 'ltc': 5499999, 'ltcReceiveAddress': 'a_receive_ltc', 'swapBillAmount': 10000000, 'buyerAddress': 'a', 'sellerReceivingAccount': 'c'})

		state.applyTransaction('Burn', {'amount':500 * milliCoin, 'destinationAccount':'d'})
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		details = Pack(sourceAccount='d', changeAccount='d', refundAccount='d', swapBillOffered=500 * milliCoin, exchangeRate=int(0.3 * 0x100000000), maxBlockOffset=0, receivingAccount='d_receive_ltc', maxBlock=200)
		state.applyTransaction('LTCBuyOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 3)
		self.assertEqual(state._pendingExchanges[1].__dict__,
			{'expiry': 150, 'swapBillDeposit': 1375000, 'ltc': 9899999, 'ltcReceiveAddress': 'd_receive_ltc', 'swapBillAmount': 22000000, 'buyerAddress': 'd', 'sellerReceivingAccount': 'c'})

	def SellOffer(self, state, source, swapBillDesired, exchangeRate):
		details = {'sourceAccount':source, 'changeAccount':source, 'receivingAccount':source, 'swapBillDesired':swapBillDesired, 'exchangeRate':exchangeRate, 'maxBlockOffset':0, 'maxBlock':200}
		self.Apply_AssertSucceeds(state, 'LTCSellOffer', **details)
	def BuyOffer(self, state, source, swapBillOffered, exchangeRate):
		details = {'sourceAccount':source, 'changeAccount':source, 'refundAccount':source, 'receivingAccount':source + '_receive_ltc', 'swapBillOffered':swapBillOffered, 'exchangeRate':exchangeRate, 'maxBlockOffset':0, 'maxBlock':200}
		self.Apply_AssertSucceeds(state, 'LTCBuyOffer', **details)
	def Completion(self, state, pendingExchangeIndex, destinationAccount, destinationAmount):
		details = {'pendingExchangeIndex':pendingExchangeIndex, 'destinationAccount':destinationAccount, 'destinationAmount':destinationAmount}
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', **details)

	def test_small_sell_remainder_refunded(self):
		state = State.State(100, 'starthash')
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'b'})
		#state.apply_LTCSellOffer(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=10000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.applyTransaction('Burn', {'amount':9900000, 'destinationAccount':'a'})
		#state.apply_LTCBuyOffer(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=9900000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		self.BuyOffer(state, 'a', swapBillOffered=9900000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# b should be refunded 100000 // 10000000 of his depost = 6250
		# balance is the 9375000 + 6250
		self.assertEqual(state._balances, {'b': 9381250})
		self.assertEqual(len(state._pendingExchanges), 1)
		#state.applyTransaction('LTCExchangeCompletion', 0, 'a_receive_ltc', 5000000)
		self.Completion(state, 0, 'a_receive_ltc', 9900000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 19900000})

	def test_small_buy_remainder_refunded(self):
		state = State.State(100, 'starthash')
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'b'})
		#state.apply_LTCSellOffer(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=10000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.applyTransaction('Burn', {'amount':10100000, 'destinationAccount':'a'})
		#state.apply_LTCBuyOffer(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=10100000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		self.BuyOffer(state, 'a', swapBillOffered=10100000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# a should be refunded 100000 remainder from buy offer
		self.assertEqual(state._balances, {'a': 100000, 'b': 9375000})
		self.assertEqual(len(state._pendingExchanges), 1)
		#state.apply_LTCExchangeCompletion(0, 'a_receive_ltc', 5000000)
		self.Completion(state, 0, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'a': 100000, 'b': 20000000})

	def test_exact_match(self):
		state = State.State(100, 'starthash')
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'b'})
		#state.apply_LTCSellOffer(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=10000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'a'})
		#state.apply_LTCBuyOffer(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=10000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		self.BuyOffer(state, 'a', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 9375000})
		self.assertEqual(len(state._pendingExchanges), 1)
		#state.apply_LTCExchangeCompletion(0, 'a_receive_ltc', 5000000)
		self.Completion(state, 0, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 20000000})

	def test_sell_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		state.applyTransaction('Burn', {'amount':20000000, 'destinationAccount':'b'})
		#state.apply_LTCSellOffer(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=20000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.SellOffer(state, 'b', swapBillDesired=20000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {'b': 18750000})
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'a'})
		#state.apply_LTCBuyOffer(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=10000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		self.BuyOffer(state, 'a', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 18750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1) ## half of sell offer is left outstanding
		#state.apply_LTCExchangeCompletion(0, 'a_receive_ltc', 5000000)
		self.Completion(state, 0, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded half his deposit, remaining deposit = 625000
		# and b now has all swapbill except deposit for outstanding sell offer
		self.assertEqual(state._balances, {'b': 29375000})
		# a goes on to buy the rest
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'a'})
		#state.apply_LTCBuyOffer(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=10000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		self.BuyOffer(state, 'a', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		#state.apply_LTCExchangeCompletion(1, 'a_receive_ltc', 5000000)
		self.Completion(state, 1, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'b': 40000000})

	def test_buy_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		state.applyTransaction('Burn', {'amount':20000000, 'destinationAccount':'b'})
		#state.apply_LTCSellOffer(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=20000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.SellOffer(state, 'b', swapBillDesired=20000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {'b': 18750000})
		state.applyTransaction('Burn', {'amount':30000000, 'destinationAccount':'a'})
		#state.apply_LTCBuyOffer(sourceAccount='a', changeAccount='a', refundAccount='a', swapBillOffered=30000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAccount='a_receive_ltc', maxBlock=200)
		self.BuyOffer(state, 'a', swapBillOffered=30000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 18750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 1) ## half of buy offer is left outstanding
		self.assertEqual(state._LTCSells.size(), 0)
		#state.apply_LTCExchangeCompletion(0, 'a_receive_ltc', 10000000)
		self.Completion(state, 0, 'a_receive_ltc', 20000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded all his deposit, and receives payment in swapbill
		self.assertEqual(state._balances, {'b': 40000000})
		# b goes on to sell the rest
		state.applyTransaction('Burn', {'amount':10000000, 'destinationAccount':'b'})
		#state.apply_LTCSellOffer(sourceAccount='b', changeAccount='b', receivingAccount='b', swapBillDesired=10000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 1)
		#state.apply_LTCExchangeCompletion(1, 'a_receive_ltc', 10000000)
		self.Completion(state, 1, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 60000000})

	def test_state_transaction(self):
		state = State.State(100, 'starthash')
		transactionType = 'Burneeheeyooo'
		transactionDetails = {'amount':1000, 'destinationAccount':'burnDestination'}
		self.assertRaises(State.InvalidTransactionType, state.checkTransaction, transactionType, transactionDetails)
		transactionType = 'Burn'
		transactionDetails = {'amount':1000, 'destinationAccount':'burnDestination', 'spuriousValue':'blah'}
		self.assertRaises(State.InvalidTransactionParameters, state.checkTransaction, transactionType, transactionDetails)
		transactionDetails = {'amount':1000, 'destinationAccount':'burnDestination'}
		result = state.checkTransaction(transactionType, transactionDetails)
		self.assertEqual(result, (True, ''))
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {})
		state.applyTransaction(transactionType, transactionDetails)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'burnDestination': 1000})

	def test_max_block_limit(self):
		state = State.State(100, 'starthash')
		maxBlock = 200
		##.. fill in or remove!
		#transactionType = 'Burneeheeyooo'
		#transactionDetails = {'amount':1000, 'destinationAccount':'burnDestination'}
		#self.assertRaises(State.InvalidTransactionType, state.checkTransaction, transactionType, transactionDetails)
		#transactionType = 'Burn'
		#transactionDetails = {'amount':1000, 'destinationAccount':'burnDestination', 'spuriousValue':'blah'}
		#self.assertRaises(State.InvalidTransactionParameters, state.checkTransaction, transactionType, transactionDetails)
		#transactionDetails = {'amount':1000, 'destinationAccount':'burnDestination'}
		#result = state.checkTransaction(transactionType, transactionDetails)
		#self.assertEqual(result, (True, ''))
		#self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		#self.assertEqual(state._balances, {})
		#state.applyTransaction(transactionType, transactionDetails)
		#self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		#self.assertEqual(state._balances, {'burnDestination': 1000})


## TODO tests for offer matching multiple other offers
## TODO - test for fail to complete due to expiry
## TODO test with different change and refund accounts in the case of a buy offer, and different change and receive accounts in the case of a sell offer
