from __future__ import print_function
import unittest
from SwapBill import State
from SwapBill.State import OutputsSpecDoesntMatch, InvalidTransactionType, InvalidTransactionParameters

milliCoin = 100000

def Pack(**details):
	return details

class Test(unittest.TestCase):
	outputsLookup = {
	    'Burn':('destination',),
	    'Pay':('change','destination'),
	    'LTCBuyOffer':('change','refund'),
	    'LTCSellOffer':('change','receiving'),
	    'LTCExchangeCompletion':()
	    }
	
	def __init__(self, *args, **kwargs):
		super(Test, self).__init__(*args, **kwargs)
		self._nextTX = 0

	def test_state_setup(self):
		state = State.State(100, 'mockhash')
		assert state.startBlockMatches('mockhash')
		assert not state.startBlockMatches('mockhosh')

	def test_bad_transactions(self):
		state = State.State(100, 'mockhash')
		self.assertRaises(InvalidTransactionType, state.checkTransaction, 'Burnee', ('destination',), {'amount':0})
		self.assertRaises(InvalidTransactionParameters, state.checkTransaction, 'Burn', ('destination',), {})
		self.assertRaises(InvalidTransactionParameters, state.checkTransaction, 'Burn', ('destination',), {'amount':0, 'spuriousAdditionalDetail':0})

	def TXID(self):
		self._nextTX += 1
		return 'tx' + str(self._nextTX)

	def test_burn(self):
		state = State.State(100, 'mockhash')
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Burn', ('none',), {'amount':0})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Burn', ('destination','destination'), {'amount':0})
		succeeds, reason = state.checkTransaction('Burn', ('destination',), {'amount':0})
		self.assertEqual(succeeds, False)
		self.assertEqual(reason, 'non zero burn amount not permitted')
		succeeds, reason = state.checkTransaction('Burn', ('destination',), {'amount':1})
		self.assertEqual(succeeds, True)
		self.assertEqual(reason, '')
		state.applyTransaction(transactionType='Burn', txID=self.TXID(), outputs=('destination',), transactionDetails={'amount':1})
		self.assertEqual(state._balances, {('tx1',1):1})
		# state should assert if you try to apply a bad transaction, and exit without any effect
		self.assertRaises(AssertionError, state.applyTransaction, 'Burn', 'badTX', ('destination',), {'amount':0})
		self.assertEqual(state._balances, {('tx1',1):1})
		state.applyTransaction(transactionType='Burn', txID=self.TXID(), outputs=('destination',), transactionDetails={'amount':2})
		self.assertEqual(state._balances, {('tx1',1):1, ('tx2',1):2})

	def Burn(self, amount):
		txID = self.TXID()
		self.state.applyTransaction(transactionType='Burn', txID=txID, outputs=('destination',), transactionDetails={'amount':amount})
		return (txID, 1)

	def Apply_AssertSucceeds(self, state, transactionType, **details):
		outputs = self.outputsLookup[transactionType]
		### note that applyTransaction now calls check and asserts success internally
		### but this then also asserts that there is no warning
		canApply, reason = state.checkTransaction(transactionType, outputs, details)
		self.assertEqual(canApply, True)
		self.assertEqual(reason, '')
		state.applyTransaction(transactionType, txID=self.TXID(), outputs=outputs, transactionDetails=details)

	def Apply_AssertFails(self, state, transactionType, **details):
		outputs = self.outputsLookup[transactionType]
		canApply, reason = state.checkTransaction(transactionType, outputs, details)
		self.assertEqual(canApply, False)
		self.assertRaises(AssertionError, state.applyTransaction, transactionType, txID='AssertFails_TXID', outputs=outputs, transactionDetails=details)
		return reason

	def test_burn_and_pay(self):
		state = State.State(100, 'mockhash')
		self.state = state
		output1 = self.Burn(10)
		self.assertEqual(state._balances, {output1:10})
		output2 = self.Burn(20)
		self.assertEqual(state._balances, {output1:10, output2:20})
		output3 = self.Burn(30)
		self.assertEqual(state._balances, {output1:10, output2:20, output3:30})
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})

		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=('tx3',1), amount=20, maxBlock=200)
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# can't repeat the same transaction (output has been consumed)
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx3',1), amount=20, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# can't pay from a nonexistant account
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx12',2), amount=20, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# pay transaction fails and has no affect on state if there is not enough balance for payment
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx1',1), amount=11, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# (but reduce by one and this should go through)
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=('tx1',1), amount=10, maxBlock=200)
		self.assertEqual(state._balances, {('tx2',1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

		# transaction with maxBlock before current block fails 
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx2',1), amount=20, maxBlock=99)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances, {('tx2',1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

		# but maxBlock exactly equal to current block is ok 
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=('tx2',1), amount=20, maxBlock=200)
		self.assertEqual(state._balances, {('tx6',2):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

	def test_minimum_exchange_amount(self):
		state = State.State(100, 'mockhash')
		self.state = state
		burnOutput = self.Burn(100)
		self.assertEqual(state._balances, {burnOutput:100})		
		# cannot post buy or sell offers, because of minimum exchange amount constraint
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccount=burnOutput, swapBillOffered=100, exchangeRate=0x80000000, maxBlockOffset=0, receivingAddress='a_receive', maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount (offer not posted)')
		self.assertEqual(state._balances, {burnOutput:100})
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccount=burnOutput, swapBillDesired=100, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount (offer not posted)')
		self.assertEqual(state._balances, {burnOutput:100})

	def not_test_ltc_trading1(self):
		# let's give out some real money, and then try again
		state = State.State(100, 'mockhash')
		self.state = state
		self.Apply_AssertSucceeds(state, 'Burn', 'tx0', amount=100000000, destinationOutput=10)
		self.Apply_AssertSucceeds(state, 'Burn', 'tx1', amount=200000000, destinationOutput=20)
		self.Apply_AssertSucceeds(state, 'Burn', 'tx2', amount=200000000, destinationOutput=30)
		self.assertEqual(state._balances, {('tx0',10): 100000000, ('tx1',20): 200000000, ('tx2',30): 200000000})

		# let's identify people involved in the exchange by tens digit of vout

		# mr 10s wants to buy

		# try offering more than available
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccount=('tx0',10), changeOutput=11, refundOutput=12, swapBillOffered=3000000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAddress='tens_receive', maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (offer not posted)')
		self.assertEqual(state._balances, {('tx0',10): 100000000, ('tx1',20): 200000000, ('tx2',30): 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)

		# reasonable buy offer that should go through
		self.Apply_AssertSucceeds(state, 'LTCBuyOffer', 'tx3', sourceAccount=('tx0',10), changeOutput=11, refundOutput=12, swapBillOffered=30000000, exchangeRate=0x80000000, maxBlockOffset=0, receivingAddress='tens_receive', maxBlock=200)
		self.assertEqual(state._balances, {('tx3',11): 70000000, ('tx1',20): 200000000, ('tx2',30): 200000000})
		self.assertEqual(state._LTCBuys.size(), 1)

		# mr 20s wants to sell

		# try offering more than available
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccount=('tx1',20), changeOutput=21, receivingOutput=22, swapBillDesired=40000000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance for deposit in source account (offer not posted)')
		self.assertEqual(state._balances, {('tx3',11): 70000000, ('tx1',20): 200000000, ('tx2',30): 200000000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 0)

		# reasonable sell offer that should go through (and match)
		self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccount='b', changeOutput='b', receivingOutput='b', swapBillDesired=40000000, exchangeRate=0x80000000, maxBlockOffset=0, maxBlock=200)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		return

		# mr 20s must now complete with appropriate ltc payment

		# bad pending exchange index
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=1, destinationOutput='a_receive', destinationAmount=20000000)
		self.assertEqual(reason, 'no pending exchange with the specified index (transaction ignored)')
		# no state change
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# bad receive address
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationOutput='randomAddress', destinationAmount=20000000)
		self.assertEqual(reason, 'destination account does not match destination for pending exchange with the specified index (transaction ignored)')
		# no state change
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# insufficient payment
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationOutput='a_receive', destinationAmount=14999999)
		self.assertEqual(reason, 'amount is less than required payment amount (transaction ignored)')
		# no state change (b just loses these ltc)
		self.assertEqual(state._balances, {'a': 70000040, 'b': 197500020, 'c': 200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# pays amount offered for sale, not the amount
		# state should warn us about the ltc overpay, but allow the transaction to go through
		details= {'pendingExchangeIndex':0, 'destinationOutput':'a_receive', 'destinationAmount':20000000}
		wouldApplySuccessfully, reason = state.checkTransaction('LTCExchangeCompletion', details)
		self.assertEqual(wouldApplySuccessfully, True)
		self.assertEqual(reason, 'amount is greater than required payment amount (exchange completes, but with ltc overpay)')

		# pays actual amount required for match with a's buy offer
		# (well formed completion transaction which should go through)
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationOutput='a_receive', destinationAmount=15000000)
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

	def not_test_pay(self):
		state = State.State(100, 'mockhash')
		self.state = state
		self.Apply_AssertSucceeds(state, 'Burn', amount=20, destinationOutput='b')
		self.Apply_AssertSucceeds(state, 'Burn', amount=30, destinationOutput='c')
		self.Apply_AssertSucceeds(state, 'Burn', amount=10, destinationOutput='a')
		self.assertEqual(state._balances, {'a':10, 'b':20, 'c':30})
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount='a', amount=3, destinationOutput='c', changeOutput='a2', maxBlock=200)
		self.assertEqual(state._balances, {'a2':7, 'b':20, 'c':33})
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount='a2', amount=8, destinationOutput='c', changeOutput='a3', maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {'a2':7, 'b':20, 'c':33})
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount='a2', amount=5, destinationOutput='c', changeOutput='a3', maxBlock=99)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances, {'a2':7, 'b':20, 'c':33})
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount='a2', amount=5, destinationOutput='b', changeOutput='a3', maxBlock=100)
		self.assertEqual(state._balances, {'a3':2, 'b':25, 'c':33})

	def not_test_ltc_trading2(self):
		state = State.State(100, 'starthash')
		self.state = state

		state.applyTransaction('Burn', {'amount':10000 * milliCoin, 'destinationOutput':'a'})
		state.applyTransaction('Burn', {'amount':10000 * milliCoin, 'destinationOutput':'b'})

		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'a': 10000 * milliCoin, 'b': 10000 * milliCoin})

		details = Pack(sourceAccount='a', changeOutput='a', refundOutput='a', swapBillOffered=100 * milliCoin, exchangeRate=0x80000000, maxBlockOffset=0, receivingAddress='a_receive_ltc', maxBlock=200)
		state.applyTransaction('LTCBuyOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in a's balance to fund the offer, so the offer should be added, and the funding amount moved in to the offer
		self.assertEqual(state._balances['a'], 9900 * milliCoin)

		details = Pack(sourceAccount='b', changeOutput='b', receivingOutput='b', swapBillDesired=160 * milliCoin, exchangeRate=int(0.4 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		state.applyTransaction('LTCSellOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# there is enough in b's balance to fund the offer, so the offer should be added, and the deposit amount moved in to the offer
		self.assertEqual(state._balances['b'], 9990 * milliCoin)

		self.assertEqual(state._pendingExchanges, {}) ## the offers so far don't match
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# c has no balance to fund the offer, so this offer should not be added, with no effect on state
		details = Pack(sourceAccount='c', changeOutput='c', receivingOutput='c', swapBillDesired=320 * milliCoin, exchangeRate=int(0.6 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		result = state.checkTransaction('LTCSellOffer', details)
		self.assertEqual(result, (False, 'insufficient balance for deposit in source account (offer not posted)'))
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCSellOffer', details)

		# same for buy offers
		details = Pack(sourceAccount='c', changeOutput='c', refundOutput='c', swapBillOffered=100 * milliCoin, exchangeRate=0x80000000, maxBlockOffset=0, receivingAddress='c_receive_ltc', maxBlock=200)
		result = state.checkTransaction('LTCBuyOffer', details)
		self.assertEqual(result, (False, 'insufficient balance in source account (offer not posted)'))
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCBuyOffer', details)

		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# same if there is some swapbill in c's account, but not enough
		details = Pack(amount=10 * milliCoin, destinationOutput='c')
		state.applyTransaction('Burn', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		details = Pack(sourceAccount='c', changeOutput='c', receivingOutput='c', swapBillDesired=320 * milliCoin, exchangeRate=int(0.6 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCSellOffer', details)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# same for buy offers
		details = Pack(sourceAccount='c', changeOutput='c', refundOutput='c', swapBillOffered=100 * milliCoin, exchangeRate=0x80000000, maxBlockOffset=0, receivingAddress='c_receive_ltc', maxBlock=200)
		self.assertRaises(AssertionError, state.applyTransaction, 'LTCBuyOffer', details)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)

		# now add just enough to make the sell offer
		state.applyTransaction('Burn', {'amount':10 * milliCoin, 'destinationOutput':'c'})
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		details = Pack(sourceAccount='c', changeOutput='c', receivingOutput='c', swapBillDesired=320 * milliCoin, exchangeRate=int(0.6 * 0x100000000), maxBlockOffset=0, maxBlock=200)
		state.applyTransaction('LTCSellOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 2)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._pendingExchanges[0].__dict__,
				         {'expiry': 150, 'swapBillDeposit': 625000, 'ltc': 5499999, 'ltcReceiveAddress': 'a_receive_ltc', 'swapBillAmount': 10000000, 'buyerAddress': 'a', 'sellerReceivingAccount': 'c'})

		state.applyTransaction('Burn', {'amount':500 * milliCoin, 'destinationOutput':'d'})
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		details = Pack(sourceAccount='d', changeOutput='d', refundOutput='d', swapBillOffered=500 * milliCoin, exchangeRate=int(0.3 * 0x100000000), maxBlockOffset=0, receivingAddress='d_receive_ltc', maxBlock=200)
		state.applyTransaction('LTCBuyOffer', details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 3)
		self.assertEqual(state._pendingExchanges[1].__dict__,
				         {'expiry': 150, 'swapBillDeposit': 1375000, 'ltc': 9899999, 'ltcReceiveAddress': 'd_receive_ltc', 'swapBillAmount': 22000000, 'buyerAddress': 'd', 'sellerReceivingAccount': 'c'})

	def SellOffer(self, state, source, swapBillDesired, exchangeRate):
		details = {'sourceAccount':source, 'changeOutput':source, 'receivingOutput':source, 'swapBillDesired':swapBillDesired, 'exchangeRate':exchangeRate, 'maxBlockOffset':0, 'maxBlock':200}
		self.Apply_AssertSucceeds(state, 'LTCSellOffer', **details)
	def BuyOffer(self, state, source, swapBillOffered, exchangeRate):
		details = {'sourceAccount':source, 'changeOutput':source, 'refundOutput':source, 'receivingAddress':source + '_receive_ltc', 'swapBillOffered':swapBillOffered, 'exchangeRate':exchangeRate, 'maxBlockOffset':0, 'maxBlock':200}
		self.Apply_AssertSucceeds(state, 'LTCBuyOffer', **details)
	def Completion(self, state, pendingExchangeIndex, destinationOutput, destinationAmount):
		details = {'pendingExchangeIndex':pendingExchangeIndex, 'destinationOutput':destinationOutput, 'destinationAmount':destinationAmount}
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', **details)

	def not_test_small_sell_remainder_refunded(self):
		state = State.State(100, 'starthash')
		self.state = state
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'b'})
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.applyTransaction('Burn', {'amount':9900000, 'destinationOutput':'a'})
		self.BuyOffer(state, 'a', swapBillOffered=9900000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# b should be refunded 100000 // 10000000 of his depost = 6250
		# balance is the 9375000 + 6250
		self.assertEqual(state._balances, {'b': 9381250})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'a_receive_ltc', 9900000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 19900000})

	def not_test_small_buy_remainder_refunded(self):
		state = State.State(100, 'starthash')
		self.state = state
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'b'})
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.applyTransaction('Burn', {'amount':10100000, 'destinationOutput':'a'})
		self.BuyOffer(state, 'a', swapBillOffered=10100000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# a should be refunded 100000 remainder from buy offer
		self.assertEqual(state._balances, {'a': 100000, 'b': 9375000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'a': 100000, 'b': 20000000})

	def not_test_exact_match(self):
		state = State.State(100, 'starthash')
		self.state = state
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'b'})
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {'b': 9375000})
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'a'})
		self.BuyOffer(state, 'a', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 9375000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 20000000})

	def not_test_sell_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		self.state = state
		state.applyTransaction('Burn', {'amount':20000000, 'destinationOutput':'b'})
		self.SellOffer(state, 'b', swapBillDesired=20000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {'b': 18750000})
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'a'})
		self.BuyOffer(state, 'a', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 18750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1) ## half of sell offer is left outstanding
		self.Completion(state, 0, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded half his deposit, remaining deposit = 625000
		# and b now has all swapbill except deposit for outstanding sell offer
		self.assertEqual(state._balances, {'b': 29375000})
		# a goes on to buy the rest
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'a'})
		self.BuyOffer(state, 'a', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.Completion(state, 1, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'b': 40000000})

	def not_test_buy_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		self.state = state
		state.applyTransaction('Burn', {'amount':20000000, 'destinationOutput':'b'})
		self.SellOffer(state, 'b', swapBillDesired=20000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {'b': 18750000})
		state.applyTransaction('Burn', {'amount':30000000, 'destinationOutput':'a'})
		self.BuyOffer(state, 'a', swapBillOffered=30000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {'b': 18750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 1) ## half of buy offer is left outstanding
		self.assertEqual(state._LTCSells.size(), 0)
		self.Completion(state, 0, 'a_receive_ltc', 20000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded all his deposit, and receives payment in swapbill
		self.assertEqual(state._balances, {'b': 40000000})
		# b goes on to sell the rest
		state.applyTransaction('Burn', {'amount':10000000, 'destinationOutput':'b'})
		self.SellOffer(state, 'b', swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 1, 'a_receive_ltc', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {'b': 60000000})

	def not_test_state_transaction(self):
		state = State.State(100, 'starthash')
		self.state = state
		transactionType = 'Burneeheeyooo'
		transactionDetails = {'amount':1000, 'destinationOutput':'burnDestination'}
		self.assertRaises(State.InvalidTransactionType, state.checkTransaction, transactionType, transactionDetails)
		transactionType = 'Burn'
		transactionDetails = {'amount':1000, 'destinationOutput':'burnDestination', 'spuriousValue':'blah'}
		self.assertRaises(State.InvalidTransactionParameters, state.checkTransaction, transactionType, transactionDetails)
		transactionDetails = {'amount':1000, 'destinationOutput':'burnDestination'}
		result = state.checkTransaction(transactionType, transactionDetails)
		self.assertEqual(result, (True, ''))
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {})
		state.applyTransaction(transactionType, transactionDetails)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._balances, {'burnDestination': 1000})

## TODO tests for offer matching multiple other offers
## TODO test for fail to complete due to expiry
## TODO test for transactions failing max block limit
## TODO test with different change and refund accounts in the case of a buy offer, and different change and receive accounts in the case of a sell offer