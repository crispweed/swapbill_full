from __future__ import print_function
import unittest
from SwapBill import State
from SwapBill.State import OutputsSpecDoesntMatch, InvalidTransactionType, InvalidTransactionParameters

milliCoin = 100000

class Test(unittest.TestCase):
	outputsLookup = {
	    'Burn':('destination',),
	    'Pay':('change','destination'),
	    'LTCBuyOffer':('change','refund'),
	    'LTCSellOffer':('change','receiving'),
	    'LTCExchangeCompletion':(),
	    'Collect':('destination',),
	    'ForwardToFutureNetworkVersion':('change',)
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
		txID = self.TXID()
		state.applyTransaction(transactionType, txID=txID, outputs=outputs, transactionDetails=details)
		txOutputs = {}
		for i in range(len(outputs)):
			txOutputs[outputs[i]] = (txID, i + 1)
		return txOutputs

	def Apply_AssertFails(self, state, transactionType, **details):
		outputs = self.outputsLookup[transactionType]
		canApply, reason = state.checkTransaction(transactionType, outputs, details)
		self.assertEqual(canApply, False)
		self.assertRaises(AssertionError, state.applyTransaction, transactionType, txID='AssertFails_TXID', outputs=outputs, transactionDetails=details)
		return reason


	def test_burn(self):
		state = State.State(100, 'mockhash')
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Burn', (), {'amount':0})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Burn', ('madeUpOutput',), {'amount':0})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Burn', ('destination','destination'), {'amount':0})
		succeeds, reason = state.checkTransaction('Burn', ('destination',), {'amount':0})
		self.assertEqual(succeeds, False)
		self.assertEqual(reason, 'zero amount not permitted')
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

	def test_forwarding(self):
		state = State.State(100, 'mockhash')
		self.state = state
		burn = self.Burn(100000000)
		self.assertEqual(state._balances, {burn:100000000})
		details = {'sourceAccount':burn, 'amount':1, 'maxBlock':200}
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'ForwardToFutureNetworkVersion', (), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'ForwardToFutureNetworkVersion', ('madeUpOutput'), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'ForwardToFutureNetworkVersion', ('change', 'madeUpOutput'), details)
		outputs = self.Apply_AssertSucceeds(state, 'ForwardToFutureNetworkVersion', **details)
		change = outputs['change']
		self.assertEqual(state._balances, {change:99999999})
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._totalForwarded, 1)
		details = {'sourceAccount':change, 'amount':1, 'maxBlock':200}
		details['amount'] = 100000000
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', **details)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		details['amount'] = 0
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', **details)
		self.assertEqual(reason, 'zero amount not permitted')
		details['amount'] = 1
		details['maxBlock'] = 99
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', **details)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', **details)
		details['maxBlock'] = 100
		details['sourceAccount'] = 'madeUpSourceAccount'
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', **details)
		self.assertEqual(reason, 'source account does not exist' )
		self.assertEqual(state._balances, {change:99999999})
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(state._totalForwarded, 1)

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

		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Pay', (), {'sourceAccount':('tx3',1), 'amount':0, 'maxBlock':200})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Pay', ('madeUpOutput',), {'sourceAccount':('tx3',1), 'amount':0, 'maxBlock':200})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Pay', ('destination','change'), {'sourceAccount':('tx3',1), 'amount':0, 'maxBlock':200})

		# zero amount
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx3',1), amount=0, maxBlock=200)
		self.assertEqual(reason, 'zero amount not permitted')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})

		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=('tx3',1), amount=20, maxBlock=200)
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# can't repeat the same transaction (output has been consumed)
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx3',1), amount=20, maxBlock=200)
		self.assertEqual(reason, 'source account does not exist')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# can't pay from a nonexistant account
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx12',2), amount=20, maxBlock=200)
		self.assertEqual(reason, 'source account does not exist')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# pay transaction fails and has no affect on state if there is not enough balance for payment
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=('tx1',1), amount=11, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# (but reduce by one and this should go through)
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=('tx1',1), amount=10, maxBlock=200)
		self.assertEqual(state._balances, {('tx2',1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

		# transaction with maxBlock before current block
		canApply, reason = state.checkTransaction('Pay', ('change','destination'), {'sourceAccount':('tx2',1), 'amount':10, 'maxBlock':99})
		self.assertEqual(canApply, True)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances, {('tx2',1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})
		payTX = self.TXID()
		state.applyTransaction('Pay', payTX, ('change','destination'), {'sourceAccount':('tx2',1), 'amount':10, 'maxBlock':99})
		self.assertEqual(state._balances, {(payTX,1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

		# but maxBlock exactly equal to current block is ok
		self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=('tx5',2), amount=10, maxBlock=100)
		self.assertEqual(state._balances, {(payTX,1):20, ('tx4',1):10, ('tx4',2):20, ('tx7',2):10})

	def test_burn_and_collect(self):
		state = State.State(100, 'mockhash')
		self.state = state
		output1 = self.Burn(10)
		self.assertEqual(state._balances, {output1:10})
		output2 = self.Burn(20)
		self.assertEqual(state._balances, {output1:10, output2:20})
		output3 = self.Burn(30)
		self.assertEqual(state._balances, {output1:10, output2:20, output3:30})
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})
		sourceAccounts = [('tx1',1),('tx2',1),('tx3',1)]
		# bad output specs
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Collect', (), {'sourceAccounts':sourceAccounts})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Collect', ('madeUpOutput'), {'sourceAccounts':sourceAccounts})
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'Collect', ('destination', 'madeUpOutput'), {'sourceAccounts':sourceAccounts})
		# no max block limit parameter
		self.assertRaises(InvalidTransactionParameters, state.checkTransaction, 'Collect', ('destination'), {'sourceAccounts':sourceAccounts, 'maxBlock':200})
		self.assertRaises(InvalidTransactionParameters, state.applyTransaction, 'Collect', 'madeUpTXID', ('destination'), {'sourceAccounts':sourceAccounts, 'maxBlock':200})
		# bad source account
		reason = self.Apply_AssertFails(state, 'Collect', sourceAccounts=[('tx1',1),('tx2',1),('madeUpTX',1)])
		self.assertEqual(reason, 'at least one source account does not exist')
		self.assertEqual(state._balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})
		# successful transaction
		self.Apply_AssertSucceeds(state, 'Collect', sourceAccounts=sourceAccounts)
		self.assertEqual(state._balances, {('tx4',1):60})

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

	def test_ltc_trading1(self):
		# this test adds tests against the ltc transaction types, and also runs through a simple exchange scenario
		# let's give out some real money, and then try again
		state = State.State(100, 'mockhash')
		self.state = state
		burnA = self.Burn(100000000)
		burnB = self.Burn(200000000)
		burnC = self.Burn(200000000)
		self.assertEqual(state._balances, {burnA:100000000, burnB:200000000, burnC:200000000})

		# A wants to buy

		details = {
		    'sourceAccount':burnA,
		    'swapBillOffered':30000000, 'exchangeRate':0x80000000,
		    'maxBlock':100, 'maxBlockOffset':0,
		    'receivingAddress':'a_receive'
		}

		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCBuyOffer', (), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCBuyOffer', ('madeUpOutput'), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCBuyOffer', ('refund', 'change'), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCBuyOffer', ('change', 'refund', 'extraOutput'), details)

		# nonexistant source account
		details['sourceAccount'] = 'madeUpAccount'
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', **details)
		details['sourceAccount'] = burnA
		self.assertEqual(reason, 'source account does not exist')

		# bad max block
		details['maxBlock'] = 99
		canApply, reason = state.checkTransaction('LTCBuyOffer', ('change','refund'), details)
		self.assertEqual(canApply, True)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances, {burnA:100000000, burnB:200000000, burnC:200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		expiredBuyOfferChange = (self.TXID(), 1)
		state.applyTransaction('LTCBuyOffer', expiredBuyOfferChange[0], ('change','refund'), details)
		self.assertEqual(state._balances, {expiredBuyOfferChange:100000000, burnB:200000000, burnC:200000000})
		self.assertEqual(state._LTCBuys.size(), 0)
		details['maxBlock'] = 100
		details['sourceAccount'] = expiredBuyOfferChange

		# try offering more than available
		details['swapBillOffered'] = 3000000000
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', **details)
		self.assertEqual(reason, 'insufficient balance in source account (offer not posted)')

		# zero amount not permitted
		details['swapBillOffered'] = 0
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', **details)
		self.assertEqual(reason, 'zero amount not permitted')

		self.assertEqual(state._balances, {expiredBuyOfferChange:100000000, burnB:200000000, burnC:200000000})
		self.assertEqual(state._LTCBuys.size(), 0)

		# reasonable buy offer that should go through
		details['swapBillOffered'] = 30000000
		details['maxBlock'] = 0xfffffff0 # these two details changed to add test coverage for expiry overflow
		details['maxBlockOffset'] = 400
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', **details)
		changeA = outputs['change']
		refundA = outputs['refund']
		self.assertEqual(state._balances, {changeA:70000000, burnB:200000000, burnC:200000000, refundA:0})
		self.assertEqual(state._LTCBuys.size(), 1)

		# refund account can't be spent yet (locked and zero balance)
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=refundA, amount=1, maxBlock=200)
		self.assertEqual(reason, 'insufficient balance in source account (transaction ignored)')
		self.assertEqual(state._balances, {changeA:70000000, burnB:200000000, burnC:200000000, refundA:0})

		# B wants to sell

		details = {
		    'sourceAccount':burnB,
		    'swapBillDesired':40000000, 'exchangeRate':0x80000000,
		    'maxBlock':200, 'maxBlockOffset':0
		}

		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCSellOffer', (), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCSellOffer', ('madeUpOutput'), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCSellOffer', ('receiving', 'change'), details)
		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCSellOffer', ('change', 'receiving', 'extraOutput'), details)

		# nonexistant source account
		details['sourceAccount'] = 'madeUpAccount'
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', **details)
		details['sourceAccount'] = burnB
		self.assertEqual(reason, 'source account does not exist')

		# bad max block
		details['maxBlock'] = 99
		canApply, reason = state.checkTransaction('LTCSellOffer', ('change','receiving'), details)
		self.assertEqual(canApply, True)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances, {changeA:70000000, burnB:200000000, burnC:200000000, refundA:0})
		self.assertEqual(state._LTCSells.size(), 0)
		expiredSellOfferChange = (self.TXID(), 1)
		state.applyTransaction('LTCSellOffer', expiredSellOfferChange[0], ('change','receiving'), details)
		self.assertEqual(state._balances, {changeA:70000000, expiredSellOfferChange:200000000, burnC:200000000, refundA:0})
		self.assertEqual(state._LTCSells.size(), 0)
		details['maxBlock'] = 100
		details['sourceAccount'] = expiredSellOfferChange

		#details['maxBlock'] = 99
		#reason = self.Apply_AssertFails(state, 'LTCSellOffer', **details)
		#details['maxBlock'] = 100
		#self.assertEqual(reason, 'max block for transaction has been exceeded' )

		# try offering more than available
		details['swapBillDesired'] = 40000000000
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', **details)
		self.assertEqual(reason, 'insufficient balance for deposit in source account (offer not posted)')
		self.assertEqual(state._balances, {changeA:70000000, expiredSellOfferChange:200000000, burnC:200000000, refundA:0})

		# zero amount
		details['swapBillDesired'] = 0
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', **details)
		self.assertEqual(reason, 'zero amount not permitted')
		self.assertEqual(state._balances, {changeA:70000000, expiredSellOfferChange:200000000, burnC:200000000, refundA:0})

		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 0)

		# reasonable sell offer that should go through (and match)
		details['swapBillDesired'] = 40000000
		details['maxBlock'] = 0xfffffff0 # these two details changed to add test coverage for expiry overflow
		details['maxBlockOffset'] = 400
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', **details)
		changeB = outputs['change']
		receivingB = outputs['receiving']
		self.assertEqual(state._balances, {changeA:70000000, changeB:197500000, burnC:200000000, refundA:0, receivingB:0})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# B must now complete with appropriate ltc payment

		details = {'pendingExchangeIndex':1, 'destinationAddress':'a_receive', 'destinationAmount':20000000}

		self.assertRaises(OutputsSpecDoesntMatch, state.checkTransaction, 'LTCExchangeCompletion', ('madeUpOutput'), details)

		# bad pending exchange index
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', **details)
		self.assertEqual(reason, 'no pending exchange with the specified index (transaction ignored)')
		# no state change
		self.assertEqual(state._balances, {changeA:70000000, changeB:197500000, burnC:200000000, refundA:0, receivingB:0})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# bad receive address
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='randomAddress', destinationAmount=20000000)
		self.assertEqual(reason, 'destination account does not match destination for pending exchange with the specified index (transaction ignored)')
		# no state change
		self.assertEqual(state._balances, {changeA:70000000, changeB:197500000, burnC:200000000, refundA:0, receivingB:0})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# insufficient payment
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='a_receive', destinationAmount=14999999)
		self.assertEqual(reason, 'amount is less than required payment amount (transaction ignored)')
		# no state change (b just loses these ltc)
		self.assertEqual(state._balances, {changeA:70000000, changeB:197500000, burnC:200000000, refundA:0, receivingB:0})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# pays amount offered for sale, not the amount
		# state should warn us about the ltc overpay, but allow the transaction to go through
		details= {'pendingExchangeIndex':0, 'destinationAddress':'a_receive', 'destinationAmount':20000000}
		canApply, warning = state.checkTransaction('LTCExchangeCompletion', outputs=(), transactionDetails=details)
		self.assertEqual(canApply, True)
		self.assertEqual(warning, 'amount is greater than required payment amount (exchange completes, but with ltc overpay)')

		# pays actual amount required for match with A's buy offer
		# (well formed completion transaction which should go through)
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='a_receive', destinationAmount=15000000)
		# B gets
		# payment of the 30000000 offered by A
		# plus fraction of deposit for the amount matched (=1875000)
		# (the rest of the deposit is left with an outstanding remainder sell offer)
		self.assertEqual(state._balances, {changeA:70000000, changeB:197500000, burnC:200000000, refundA:0, receivingB:31875000})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 0)

	def SellOffer(self, state, source, swapBillDesired, exchangeRate):
		details = {'sourceAccount':source, 'swapBillDesired':swapBillDesired, 'exchangeRate':exchangeRate, 'maxBlockOffset':0, 'maxBlock':200}
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', **details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		return outputs['change'], outputs['receiving']
	def BuyOffer(self, state, source, receiveAddress, swapBillOffered, exchangeRate):
		details = {'sourceAccount':source, 'receivingAddress':receiveAddress, 'swapBillOffered':swapBillOffered, 'exchangeRate':exchangeRate, 'maxBlockOffset':0, 'maxBlock':200}
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', **details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		return outputs['change'], outputs['refund']
	def Completion(self, state, pendingExchangeIndex, destinationAddress, destinationAmount):
		details = {'pendingExchangeIndex':pendingExchangeIndex, 'destinationAddress':destinationAddress, 'destinationAmount':destinationAmount}
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', **details)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

	def test_small_sell_remainder_refunded(self):
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(10000000)
		changeB, receiveB = self.SellOffer(state, burnB, swapBillDesired=10000000, exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {changeB:9375000, receiveB:0})
		burnA = self.Burn(9900000)
		changeA, refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=9900000, exchangeRate=0x80000000)
		# b should be refunded 100000 // 10000000 of his depost = 6250
		self.assertEqual(state._balances, {changeB:9375000, receiveB:6250, refundA:0})
		self.assertEqual(len(state._pendingExchanges), 1)
		# but receiving account can't be spent yet as this is locked until exchange completed
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=receiveB, amount=1, maxBlock=200)
		self.assertEqual(reason, "source account is linked to an outstanding trade offer or pending exchange and can't be spent until the trade is completed or expires")
		self.assertEqual(state._balances, {changeB:9375000, receiveB:6250, refundA:0})
		self.Completion(state, 0, 'receiveLTC', 9900000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b gets the rest of his depost refunded
		self.assertEqual(state._balances, {changeB:9375000, receiveB:10525000, refundA:0}) # TODO clean up the refund account
		# and the receiving account *can* now be used
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=receiveB, amount=1, maxBlock=200)
		payDestination = outputs['destination']
		payChange = outputs['change']
		self.assertEqual(state._balances, {changeB:9375000, payChange:10524999, payDestination:1, refundA:0}) # TODO clean up the refund account

	def test_small_buy_remainder_refunded(self):
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(10000000)
		changeB, receiveB = self.SellOffer(state, burnB, swapBillDesired=10000000, exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {changeB:9375000, receiveB:0})
		burnA = self.Burn(10100000)
		changeA, refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=10100000, exchangeRate=0x80000000)
		# a should be refunded 100000 remainder from buy offer
		self.assertEqual(state._balances, {changeB:9375000, receiveB:0, refundA:100000})
		self.assertEqual(len(state._pendingExchanges), 1)
		# but refund account can't be spent yet as this is locked until exchange completed
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=refundA, amount=1, maxBlock=200)
		self.assertEqual(reason, "source account is linked to an outstanding trade offer or pending exchange and can't be spent until the trade is completed or expires")
		self.assertEqual(state._balances, {changeB:9375000, receiveB:0, refundA:100000})
		self.Completion(state, 0, 'receiveLTC', 10000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {changeB:9375000, refundA:100000, receiveB:10625000})
		# and the refund account *can* now be used
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=refundA, amount=1, maxBlock=200)
		payDestination = outputs['destination']
		payChange = outputs['change']
		self.assertEqual(state._balances, {changeB:9375000, payChange:99999, payDestination:1, receiveB:10625000})

	def test_exact_match(self):
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(10000000)
		changeB, receiveB = self.SellOffer(state, burnB, swapBillDesired=10000000, exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances, {changeB: 9375000, receiveB:0})
		burnA = self.Burn(10000000)
		changeA, refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=10000000, exchangeRate=0x80000000)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {changeB:9375000, receiveB:0, refundA:0})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'receiveLTC', 10000000 // 2)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {changeB:9375000, receiveB:10625000, refundA:0}) # TODO clean up refund account after offers expire!

	def test_sell_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(20000000)
		changeB, receiveB = self.SellOffer(state, burnB, swapBillDesired=20000000, exchangeRate=0x80000000)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {changeB:18750000, receiveB:0})
		burnA = self.Burn(10000000)
		changeA, refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=10000000, exchangeRate=0x80000000)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {changeB:18750000, receiveB:0, refundA:0})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1) ## half of sell offer is left outstanding
		self.Completion(state, 0, 'receiveLTC', 10000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded half his deposit = 625000, plus payment of 10000000
		# (and b now has all swapbill except deposit for outstanding sell offer = 625000)
		self.assertEqual(state._balances, {changeB:18750000, receiveB:10625000, refundA:0})
		# but receiving account can't be spent yet as this is locked until exchange completed
		reason = self.Apply_AssertFails(state, 'Pay', sourceAccount=receiveB, amount=1, maxBlock=200)
		self.assertEqual(reason, "source account is linked to an outstanding trade offer or pending exchange and can't be spent until the trade is completed or expires")
		self.assertEqual(state._balances, {changeB:18750000, receiveB:10625000, refundA:0})
		# a goes on to buy the rest
		burnA2 = self.Burn(10000000)
		changeA2, refundA2 = self.BuyOffer(state, burnA2, 'receiveLTC2', swapBillOffered=10000000, exchangeRate=0x80000000)
		self.Completion(state, 1, 'receiveLTC2', 10000000 // 2)
		# other second payment counterparty + second half of deposit are credited to b's receive account
		self.assertEqual(state._balances, {changeB:18750000, receiveB:21250000, refundA:0, refundA2:0})
		# and the receive account *can* now be used
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccount=receiveB, amount=1, maxBlock=200)
		payDestination = outputs['destination']
		payChange = outputs['change']
		self.assertEqual(state._balances, {changeB:18750000, payChange:21250000-1, payDestination:1, refundA:0, refundA2:0})

	def test_buy_remainder_outstanding(self):
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(20000000)
		changeB, receiveB = self.SellOffer(state, burnB, swapBillDesired=20000000, exchangeRate=0x80000000)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances, {changeB:18750000, receiveB:0})
		burnA = self.Burn(30000000)
		changeA, refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=30000000, exchangeRate=0x80000000)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances, {changeB:18750000, receiveB:0, refundA:0})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 1) ## half of buy offer is left outstanding
		self.assertEqual(state._LTCSells.size(), 0)
		self.Completion(state, 0, 'receiveLTC', 20000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded all his deposit, and receives payment in swapbill
		self.assertEqual(state._balances, {changeB:18750000, receiveB:21250000, refundA:0})
		# b goes on to sell the rest
		burnB2 = self.Burn(10000000)
		changeB2, receiveB2 = self.SellOffer(state, burnB2, swapBillDesired=10000000, exchangeRate=0x80000000)
		self.assertEqual(state._balances, {changeB:18750000, receiveB:21250000, refundA:0, changeB2:9375000, receiveB2:0})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 1, 'receiveLTC', 10000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances, {changeB:18750000, receiveB:21250000, refundA:0, changeB2:9375000, receiveB2:10625000})

# TODO tests for offer matching multiple other offers
# TODO test for fail to complete due to expiry
# TODO test for transactions failing max block limit
