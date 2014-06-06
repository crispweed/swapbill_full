from __future__ import print_function
import unittest
from SwapBill import State
from SwapBill.State import InvalidTransactionType, InvalidTransactionParameters
from SwapBill.HardCodedProtocolConstraints import Constraints
from SwapBill.Amounts import e

def totalAccountedFor(state):
	result = 0
	for key in state._balances.balances:
		result += state._balances.balances[key]
	for offer in state._LTCBuys.getSortedOffers():
		result += offer._swapBillOffered
	for offer in state._LTCSells.getSortedOffers():
		result += offer._swapBillDeposit
	for key in state._pendingExchanges:
		exchange = state._pendingExchanges[key]
		result += exchange.swapBillAmount
		result += exchange.swapBillDeposit
	result += state._totalForwarded
	return result

class Test(unittest.TestCase):
	outputsLookup = {
	    'Burn':('destination',),
	    'Pay':('change','destination'),
	    'LTCBuyOffer':('ltcBuy',),
	    'LTCSellOffer':('ltcSell',),
	    'LTCExchangeCompletion':(),
	    'ForwardToFutureNetworkVersion':('change',)
	    }

	@classmethod
	def setUpClass(cls):
		cls._stored_minimumSwapBillBalance = Constraints.minimumSwapBillBalance
	@classmethod
	def tearDownClass(cls):
		Constraints.minimumSwapBillBalance = cls._stored_minimumSwapBillBalance

	def __init__(self, *args, **kwargs):
		super(Test, self).__init__(*args, **kwargs)
		self._nextTX = 0

	def TXID(self):
		self._nextTX += 1
		return 'tx' + str(self._nextTX)

	def Burn(self, amount):
		txID = self.TXID()
		self.state.applyFundedTransaction(transactionType='Burn', txID=txID, outputs=('destination',), transactionDetails={'amount':amount}, sourceAccounts=[])
		return (txID, 1)

	def Apply_AssertSucceeds(self, state, transactionType, expectedError='', sourceAccounts=None, **details):
		outputs = self.outputsLookup[transactionType]
		canApply, reason = state.checkTransaction(transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertEqual(reason, expectedError)
		self.assertEqual(canApply, True)
		txID = self.TXID()
		state.applyTransaction(transactionType, txID=txID, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
		txOutputs = {}
		for i in range(len(outputs)):
			txOutputs[outputs[i]] = (txID, i + 1)
		return txOutputs

	def Apply_AssertFails(self, state, transactionType, sourceAccounts=None, **details):
		outputs = self.outputsLookup[transactionType]
		# TODO - implement a proper state copy and comparison!
		balancesBefore = state._balances.balances.copy()
		exchangesBefore = len(state._pendingExchanges)
		canApply, reason = state.checkTransaction(transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertEqual(canApply, False)
		state.applyTransaction(transactionType, txID='AssertFails_TXID', outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertDictEqual(state._balances.balances, balancesBefore)
		self.assertEqual(exchangesBefore, len(state._pendingExchanges))
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
		return reason

	def Apply_AssertInsufficientFunds(self, state, transactionType, sourceAccounts=None, **details):
		outputs = self.outputsLookup[transactionType]
		self.assertRaises(State.InsufficientFundsForTransaction, state.checkTransaction, transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		txID = self.TXID()
		state.applyTransaction(transactionType, txID, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
		return (txID, 1)

	def SellOffer(self, state, source, ltcOffered, exchangeRate, maxBlock=200):
		details = {'ltcOffered':ltcOffered, 'exchangeRate':exchangeRate, 'maxBlock':maxBlock}
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccounts=[source], **details)
		return outputs['ltcSell']
	def BuyOffer(self, state, source, receiveAddress, swapBillOffered, exchangeRate, maxBlock=200):
		details = {'receivingAddress':receiveAddress, 'swapBillOffered':swapBillOffered, 'exchangeRate':exchangeRate, 'maxBlock':maxBlock}
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[source], **details)
		return outputs['ltcBuy']
	def Completion(self, state, pendingExchangeIndex, destinationAddress, destinationAmount):
		details = {'pendingExchangeIndex':pendingExchangeIndex, 'destinationAddress':destinationAddress, 'destinationAmount':destinationAmount}
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', **details)


	def test_state_setup(self):
		Constraints.minimumSwapBillBalance = Test._stored_minimumSwapBillBalance
		state = State.State(100, 'mockhash')
		assert state.startBlockMatches('mockhash')
		assert not state.startBlockMatches('mockhosh')

	def test_bad_transactions(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'mochhash')
		self.assertRaises(InvalidTransactionType, state.checkTransaction, 'Burnee', ('destination',), {'amount':1}, sourceAccounts=[])
		self.assertRaises(InvalidTransactionParameters, state.checkTransaction, 'Burn', ('destination',), {}, sourceAccounts=[])
		self.assertRaises(InvalidTransactionParameters, state.checkTransaction, 'Burn', ('destination',), {'amount':0, 'spuriousAdditionalDetail':0}, sourceAccounts=[])
		# note that not including sourceAccounts currently has the effect of changing transaction type for the purpose of error reporting
		self.assertRaises(InvalidTransactionType, state.checkTransaction, 'Burn', ('destination',), {'amount':1})
		canApply, reason = state.checkTransaction('Burn', ('destination',), {'amount':1}, sourceAccounts=[])
		self.assertTrue(canApply)
		self.assertEqual(reason, '')

	def test_burn(self):
		Constraints.minimumSwapBillBalance = 10
		state = State.State(100, 'mockhash')
		# bad outputs specs
		self.assertRaises(AssertionError, state.checkTransaction, 'Burn', (), {'amount':0}, sourceAccounts=[])
		self.assertRaises(AssertionError, state.checkTransaction, 'Burn', ('madeUpOutput',), {'amount':0}, sourceAccounts=[])
		self.assertRaises(AssertionError, state.checkTransaction, 'Burn', ('destination','destination'), {'amount':0}, sourceAccounts=[])
		# control with good output specs
		succeeds, reason = state.checkTransaction('Burn', ('destination',), {'amount':0}, sourceAccounts=[])
		self.assertEqual(succeeds, False)
		self.assertEqual(reason, 'burn output is below minimum balance')
		succeeds, reason = state.checkTransaction('Burn', ('destination',), {'amount':9}, sourceAccounts=[])
		self.assertEqual(succeeds, False)
		self.assertEqual(reason, 'burn output is below minimum balance')
		succeeds, reason = state.checkTransaction('Burn', ('destination',), {'amount':10}, sourceAccounts=[])
		self.assertEqual(succeeds, True)
		self.assertEqual(reason, '')
		state.applyTransaction(transactionType='Burn', txID=self.TXID(), outputs=('destination',), transactionDetails={'amount':10}, sourceAccounts=[])
		self.assertEqual(state._balances.balances, {('tx1',1):10})
		# state should assert if you try to apply a bad transaction, and exit without any effect
		self.assertRaises(AssertionError, state.applyTransaction, 'Burn', 'badTX', ('destination',), {'amount':0}, sourceAccounts=[])
		self.assertEqual(state._balances.balances, {('tx1',1):10})
		state.applyTransaction(transactionType='Burn', txID=self.TXID(), outputs=('destination',), transactionDetails={'amount':20}, sourceAccounts=[])
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_forwarding(self):
		Constraints.minimumSwapBillBalance = 10
		state = State.State(100, 'mochhash')
		self.state = state
		burn = self.Burn(100000000)
		self.assertEqual(state._balances.balances, {burn:100000000})
		details = {'amount':10, 'maxBlock':200}
		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'ForwardToFutureNetworkVersion', (), details, sourceAccounts=[burn])
		self.assertRaises(AssertionError, state.checkTransaction, 'ForwardToFutureNetworkVersion', ('madeUpOutput'), details, sourceAccounts=[burn])
		self.assertRaises(AssertionError, state.checkTransaction, 'ForwardToFutureNetworkVersion', ('change', 'madeUpOutput'), details, sourceAccounts=[burn])
		# control with good output specs
		outputs = self.Apply_AssertSucceeds(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[burn], **details)
		change = outputs['change']
		self.assertEqual(state._balances.balances, {change:99999990})
		self.assertEqual(state._totalForwarded, 10)
		details = {'amount':10, 'maxBlock':200}
		details['amount'] = 100000000
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[change], **details)
		self.assertEqual(reason, 'insufficient swapbill input')
		details['amount'] = 0
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[change], **details)
		self.assertEqual(reason, 'amount is below minimum balance')
		details['amount'] = 9
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[change], **details)
		self.assertEqual(reason, 'amount is below minimum balance')
		details['amount'] = 10
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=['madeUpSourceAccount'], **details)
		self.assertEqual(reason, 'insufficient swapbill input' )
		self.assertEqual(state._totalForwarded, 10)
		details['maxBlock'] = 99
		outputs = self.Apply_AssertSucceeds(state, 'ForwardToFutureNetworkVersion', expectedError='max block for transaction has been exceeded', sourceAccounts=[change], **details)
		change2 = outputs['change']
		details['maxBlock'] = 100
		# if forwarding transactions expire, amount has to be paid back as change
		# (for same reason as other transactions such as pay - we've used the source account, and any balance left associated with this account becomes unredeemable)
		self.assertEqual(state._balances.balances, {change2:99999990})
		burn2 = self.Burn(20)
		self.assertEqual(state._balances.balances, {change2:99999990, burn2:20})
		details = {'amount':11, 'maxBlock':200}
		reason = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[burn2], **details)
		self.assertEqual(reason, 'transaction would generate change output with change amount below minimum balance')

	def test_burn_and_pay(self):
		Constraints.minimumSwapBillBalance = 10
		state = State.State(100, 'mochhash')
		self.state = state
		output1 = self.Burn(10)
		self.assertEqual(state._balances.balances, {output1:10})
		output2 = self.Burn(20)
		self.assertEqual(state._balances.balances, {output1:10, output2:20})
		output3 = self.Burn(30)
		self.assertEqual(state._balances.balances, {output1:10, output2:20, output3:30})
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})
		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'Pay', (), {'amount':0, 'maxBlock':200}, sourceAccounts=[('tx3',1)])
		self.assertRaises(AssertionError, state.checkTransaction, 'Pay', ('madeUpOutput',), {'amount':0, 'maxBlock':200}, sourceAccounts=[('tx3',1)])
		self.assertRaises(AssertionError, state.checkTransaction, 'Pay', ('destination','change'), {'amount':0, 'maxBlock':200}, sourceAccounts=[('tx3',1)])
		# destination amount below minimum balance
		reason = self.Apply_AssertFails(state, 'Pay', amount=0, maxBlock=200, sourceAccounts=[('tx3',1)])
		self.assertEqual(reason, 'amount is below minimum balance')
		reason = self.Apply_AssertFails(state, 'Pay', amount=9, maxBlock=200, sourceAccounts=[('tx3',1)])
		self.assertEqual(reason, 'amount is below minimum balance')
		# change amount below minimum balance
		reason = self.Apply_AssertFails(state, 'Pay', amount=11, maxBlock=200, sourceAccounts=[('tx2',1)])
		self.assertEqual(reason, 'transaction would generate change output with change amount below minimum balance')

		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})

		self.Apply_AssertSucceeds(state, 'Pay', amount=20, maxBlock=200, sourceAccounts=[('tx3',1)])
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# can't repeat the same transaction (output has been consumed)
		reason = self.Apply_AssertFails(state, 'Pay', amount=20, maxBlock=200, sourceAccounts=[('tx3',1)])
		self.assertEqual(reason, 'insufficient swapbill input')
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# can't pay from a nonexistant account
		reason = self.Apply_AssertFails(state, 'Pay', amount=20, maxBlock=200, sourceAccounts=[('tx12',2)])
		self.assertEqual(reason, 'insufficient swapbill input')
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# pay transaction fails and has no affect on state if there is not enough balance for payment
		reason = self.Apply_AssertFails(state, 'Pay', amount=11, maxBlock=200, sourceAccounts=[('tx1',1)])
		self.assertEqual(reason, 'insufficient swapbill input')
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx4',1):10, ('tx4',2):20})

		# (but reduce by one and this should go through)
		self.Apply_AssertSucceeds(state, 'Pay', amount=10, maxBlock=200, sourceAccounts=[('tx1',1)])
		self.assertEqual(state._balances.balances, {('tx2',1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

		# transaction with maxBlock before current block
		canApply, reason = state.checkTransaction('Pay', ('change','destination'), { 'amount':10, 'maxBlock':99}, sourceAccounts=[('tx2',1)])
		self.assertEqual(canApply, True)
		self.assertEqual(reason, 'max block for transaction has been exceeded')
		self.assertEqual(state._balances.balances, {('tx2',1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})
		payTX = self.TXID()
		state.applyTransaction('Pay', payTX, ('change','destination'), {'amount':10, 'maxBlock':99}, sourceAccounts=[('tx2',1)])
		self.assertEqual(state._balances.balances, {(payTX,1):20, ('tx4',1):10, ('tx4',2):20, ('tx5',2):10})

		# but maxBlock exactly equal to current block is ok
		self.Apply_AssertSucceeds(state, 'Pay', amount=10, maxBlock=100, sourceAccounts=[('tx5',2)])
		self.assertEqual(state._balances.balances, {(payTX,1):20, ('tx4',1):10, ('tx4',2):20, ('tx7',2):10})

	def test_pay_from_multiple(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'mochhash')
		self.state = state
		output1 = self.Burn(10)
		self.assertEqual(state._balances.balances, {output1:10})
		output2 = self.Burn(20)
		self.assertEqual(state._balances.balances, {output1:10, output2:20})
		output3 = self.Burn(30)
		self.assertEqual(state._balances.balances, {output1:10, output2:20, output3:30})
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})
		self.Apply_AssertSucceeds(state, 'Pay', amount=59, maxBlock=100, sourceAccounts=[('tx1',1),('tx2',1),('tx3',1)])
		self.assertEqual(state._balances.balances, {('tx4', 2): 59, ('tx4', 1): 1})

	def test_minimum_exchange_amount(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'mockhash')
		self.state = state
		burnOutput = self.Burn(10000)
		self.assertEqual(state._balances.balances, {burnOutput:10000})
		# cannot post buy or sell offers, because of minimum exchange amount constraint
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccounts=[burnOutput], swapBillOffered=100, exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount')
		self.assertEqual(state._balances.balances, {burnOutput:10000})
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccounts=[burnOutput], ltcOffered=100//2, exchangeRate=0x80000000, maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount')
		self.assertEqual(state._balances.balances, {burnOutput:10000})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
	def test_minimum_exchange_amount2(self):
		Constraints.minimumSwapBillBalance = 1*e(7)
		state = State.State(100, 'mockhash')
		self.state = state
		burnOutput = self.Burn(2*e(7))
		# cannot post buy or sell offers, because of minimum exchange amount constraint
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccounts=[burnOutput], swapBillOffered=1*e(7)-1, exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount')
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccounts=[burnOutput], ltcOffered=1*e(7)//2-1, exchangeRate=0x80000000, maxBlock=200)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount')

	def test_trade_offers_leave_less_than_minimum_balance(self):
		Constraints.minimumSwapBillBalance = 1*e(7)
		state = State.State(100, 'mockhash')
		self.state = state
		burnOutput = self.Burn(1*e(7))
		changeOutput = self.Apply_AssertInsufficientFunds(state, 'LTCBuyOffer', sourceAccounts=[burnOutput], swapBillOffered=1*e(7), exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		self.assertEqual(state._balances.balances, {changeOutput:1*e(7)})
		changeOutput = self.Apply_AssertInsufficientFunds(state, 'LTCSellOffer', sourceAccounts=[changeOutput], ltcOffered=1*e(7)//2, exchangeRate=0x80000000, maxBlock=200)
		self.assertEqual(state._balances.balances, {changeOutput:1*e(7)})

	def test_ltc_trading1(self):
		# this test adds tests against the ltc transaction types, and also runs through a simple exchange scenario
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'mochhash')
		self.state = state
		burnA = self.Burn(100000000)
		burnB = self.Burn(200000000)
		burnC = self.Burn(200000000)
		expectedBalances = {burnA:100000000, burnB:200000000, burnC:200000000}
		self.assertEqual(state._balances.balances, expectedBalances)

		# A wants to buy

		details = {
		    'swapBillOffered':30000000, 'exchangeRate':0x80000000,
		    'maxBlock':100,
		    'receivingAddress':'a_receive'
		}

		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCBuyOffer', outputs=(), transactionDetails=details, sourceAccounts=[burnA])
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCBuyOffer', outputs=('madeUpOutput'), transactionDetails=details, sourceAccounts=[burnA])
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCBuyOffer', outputs=('ltcBuy', 'change'), transactionDetails=details, sourceAccounts=[burnA])
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCBuyOffer', outputs=('change', 'ltcBuy', 'extraOutput'), transactionDetails=details, sourceAccounts=[burnA])

		# nonexistant source account
		self.Apply_AssertInsufficientFunds(state, 'LTCBuyOffer', sourceAccounts=['madeUpAccount'], **details)
		self.assertEqual(state._balances.balances, expectedBalances)

		# bad max block
		details['maxBlock'] = 99
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[burnA], expectedError='max block for transaction has been exceeded', **details)
		details['maxBlock'] = 100
		expiredBuyOfferChange = outputs['ltcBuy']
		expectedBalances[expiredBuyOfferChange] = expectedBalances.pop(burnA)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCBuys.size(), 0)

		# try offering more than available
		details['swapBillOffered'] = 3000000000
		failedBuyChange = self.Apply_AssertInsufficientFunds(state, 'LTCBuyOffer', sourceAccounts=[expiredBuyOfferChange], **details)
		expectedBalances[failedBuyChange] = expectedBalances.pop(expiredBuyOfferChange)
		self.assertEqual(state._balances.balances, expectedBalances)

		# zero amount
		details['swapBillOffered'] = 0
		reason = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccounts=[failedBuyChange], **details)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount')
		self.assertEqual(state._balances.balances, expectedBalances)

		self.assertEqual(state._LTCBuys.size(), 0)

		# reasonable buy offer that should go through
		details['swapBillOffered'] = 30000000
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[failedBuyChange], **details)
		refundA = outputs['ltcBuy']
		expectedBalances.pop(failedBuyChange)
		expectedBalances[refundA]=70000000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCBuys.size(), 1)

		# refund account can't be completely spent yet as it is referenced by the trade
		changeA = self.Apply_AssertInsufficientFunds(state, 'Pay', sourceAccounts=[refundA], amount=expectedBalances[refundA], maxBlock=200)
		expectedBalances[changeA] = expectedBalances.pop(refundA)
		self.assertEqual(state._balances.balances, expectedBalances)

		# B wants to sell

		details = {
		    'ltcOffered':40000000//2, 'exchangeRate':0x80000000,
		    'maxBlock':200
		}

		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCSellOffer', outputs=(), transactionDetails=details, sourceAccounts=[burnB])
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCSellOffer', outputs=('madeUpOutput'), transactionDetails=details, sourceAccounts=[burnB])
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCSellOffer', outputs=('ltcSell', 'change'), transactionDetails=details, sourceAccounts=[burnB])
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCSellOffer', outputs=('change', 'ltcSell', 'extraOutput'), transactionDetails=details, sourceAccounts=[burnB])

		# nonexistant source account

		self.Apply_AssertInsufficientFunds(state, 'LTCSellOffer', sourceAccounts=['madeUpAccount'], **details)
		self.assertEqual(state._balances.balances, expectedBalances)

		# expired max block
		details['maxBlock'] = 99
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccounts=[burnB], expectedError='max block for transaction has been exceeded', **details)
		details['maxBlock'] = 100
		expiredSellOfferChange = outputs['ltcSell']
		expectedBalances[expiredSellOfferChange] = expectedBalances.pop(burnB)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCSells.size(), 0)

		#details['maxBlock'] = 99
		#reason = self.Apply_AssertFails(state, 'LTCSellOffer', **details)
		#details['maxBlock'] = 100
		#self.assertEqual(reason, 'max block for transaction has been exceeded' )

		# try offering more than available
		details['ltcOffered'] = 40000000000//2
		offerTooHighChange = self.Apply_AssertInsufficientFunds(state, 'LTCSellOffer', sourceAccounts=[expiredSellOfferChange], **details)
		expectedBalances[offerTooHighChange] = expectedBalances.pop(expiredSellOfferChange)
		self.assertEqual(state._balances.balances, expectedBalances)

		# zero amount
		details['ltcOffered'] = 0
		reason = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccounts=[expiredSellOfferChange], **details)
		self.assertEqual(reason, 'does not satisfy minimum exchange amount')
		self.assertEqual(state._balances.balances, expectedBalances)

		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 0)

		# reasonable sell offer that should go through (and match)
		details['ltcOffered'] = 40000000//2
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccounts=[offerTooHighChange], **details)
		receivingB = outputs['ltcSell']
		expectedBalances[receivingB] = expectedBalances.pop(offerTooHighChange) - 2500000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# B must now complete with appropriate ltc payment

		details = {'pendingExchangeIndex':1, 'destinationAddress':'a_receive', 'destinationAmount':20000000}

		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCExchangeCompletion', outputs=('madeUpOutput'), transactionDetails=details, sourceAccounts=None)

		# bad pending exchange index
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', **details)
		self.assertEqual(reason, 'no pending exchange with the specified index')
		# no state change
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# bad receive address
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='randomAddress', destinationAmount=20000000)
		self.assertEqual(reason, 'destination account does not match destination for pending exchange with the specified index')
		# no state change
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# insufficient payment
		reason = self.Apply_AssertFails(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='a_receive', destinationAmount=14999999)
		self.assertEqual(reason, 'amount is less than required payment amount')
		# no state change (b just loses these ltc)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# pays amount offered for sale, not the amount
		# state should warn us about the ltc overpay, but allow the transaction to go through
		details= {'pendingExchangeIndex':0, 'destinationAddress':'a_receive', 'destinationAmount':20000000}
		canApply, warning = state.checkTransaction('LTCExchangeCompletion', outputs=(), transactionDetails=details, sourceAccounts=None)
		self.assertEqual(canApply, True)
		self.assertEqual(warning, 'amount is greater than required payment amount')

		# pays actual amount required for match with A's buy offer
		# (well formed completion transaction which should go through)
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='a_receive', destinationAmount=15000000)
		# B gets
		# payment of the 3*e(7) offered by A
		# plus fraction of deposit for the amount matched (=1875000)
		# (the rest of the deposit is left with an outstanding remainder sell offer)
		expectedBalances[receivingB] += 3*e(7) + 1875000
		self.assertEqual(state._balances.balances, expectedBalances)
		#self.assertEqual(state._balances.balances, {changeA:70000000-1, changeB:197500000-1, burnC:200000000, refundA:1, receivingB:1})
		#self.assertEqual(state._balances.balances, {changeA:70000000-1, changeB:197500000-1, burnC:200000000, refundA:1, receivingB:31875000+1})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 0)

	def test_ltc_buy_change_added_to_refund(self):
		Constraints.minimumSwapBillBalance = 1*e(8)
		state = State.State(100, 'starthash')
		self.state = state
		burn = self.Burn(22*e(7))
		change, refund = self.BuyOffer(state, burn, 'madeUpReceiveAddress', swapBillOffered=1*e(8), exchangeRate=0x80000000)
		self.assertEqual(state._balances.balances, {refund:12*e(7)})
	def test_ltc_sell_change_added_to_receiving(self):
		Constraints.minimumSwapBillBalance = 1*e(8)
		state = State.State(100, 'starthash')
		self.state = state
		burn = self.Burn(22*e(7))
		change, receive = self.SellOffer(state, burn, ltcOffered=3*16*e(7)//2, exchangeRate=0x80000000)
		# deposit is 3*16*e(7) // 16
		self.assertEqual(state._balances.balances, {receive:19*e(7)})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_small_sell_remainder(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
		# deposit is 10000000 // 16
		deposit = 625000
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-deposit})
		burnA = self.Burn(99*e(5)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=99*e(5), exchangeRate=0x80000000)
		# the offers can't match, because of small (sell) remainder
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-deposit, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# cannot spend whole balance, because this is referenced by the sell offer
		self.assertTrue(state._balances.accountHasBalance(receiveB))
		self.assertTrue(state._balances.isReferenced(receiveB))
		changeB = self.Apply_AssertInsufficientFunds(state, 'Pay', sourceAccounts=[receiveB], amount=1*e(7)-deposit, maxBlock=200)
		self.assertEqual(state._balances.balances, {changeB:1*e(7)-deposit, refundA:1})
		# but can spend leaving just minimum balance
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[changeB], amount=1*e(7)-deposit-1, maxBlock=200)
		changeB2 = outputs['change']
		payOutput = outputs['destination']
		self.assertEqual(state._balances.balances, {changeB2:1, payOutput:1*e(7)-deposit-1, refundA:1})
		# same for buy refund account
		self.assertTrue(state._balances.accountHasBalance(refundA))
		self.assertTrue(state._balances.isReferenced(refundA))
		changeA = self.Apply_AssertInsufficientFunds(state, 'Pay', sourceAccounts=[refundA], amount=1, maxBlock=200)
		self.assertEqual(state._balances.balances, {changeB2:1, payOutput:1*e(7)-deposit-1, changeA:1})
		# but sell should be matched by this larger offer
		burnC = self.Burn(4*e(8))
		refundC = self.BuyOffer(state, burnC, 'receiveLTC2', swapBillOffered=1*e(8), exchangeRate=0x80000000)
		self.assertEqual(state._balances.balances, {changeB2:1, payOutput:1*e(7)-deposit-1, changeA:1, refundC:3*e(8)})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 2)
		self.assertEqual(state._LTCSells.size(), 0)
		# completion
		self.Completion(state, 0, 'receiveLTC2', 1*e(7)//2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b gets deposit refunded, plus swapbill payment
		self.assertEqual(state._balances.balances, {changeB2:1+deposit+1*e(7), payOutput:1*e(7)-deposit-1, changeA:1, refundC:3*e(8)})
		# and the receiving account *can* now be spent, completely
		self.assertTrue(state._balances.accountHasBalance(changeB2))
		self.assertFalse(state._balances.isReferenced(changeB2))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[changeB2], amount=1+deposit+1*e(7), maxBlock=200)
		payDestination = outputs['destination']
		payChange = outputs['change']
		self.assertEqual(state._balances.balances, {payDestination:1+deposit+1*e(7), payOutput:1*e(7)-deposit-1, changeA:1, refundC:3*e(8)})

	def test_small_buy_remainder(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
		# deposit is 1*e(7) // 16
		depositB = 625000
		expectedBalances = {receiveB:1*e(7)-depositB}
		self.assertEqual(state._balances.balances, expectedBalances)
		burnA = self.Burn(10100001)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=10100000, exchangeRate=0x80000000)
		# the offers can't match, because of small (buy) remainder
		expectedBalances[refundA] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCSells.size(), 1)
		# refund account can't be spent completely as this is still referenced by the trade offer
		# (different tests for not being able to spend completely follow)
		self.assertTrue(state._balances.accountHasBalance(refundA))
		self.assertTrue(state._balances.isReferenced(refundA))
		changeA = self.Apply_AssertInsufficientFunds(state, 'Pay', sourceAccounts=[refundA], amount=1, maxBlock=200)
		expectedBalances.pop(refundA)
		expectedBalances[changeA] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		details = {'amount':1, 'maxBlock':200}
		changeA2 = self.Apply_AssertInsufficientFunds(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[changeA], **details)
		expectedBalances.pop(changeA)
		expectedBalances[changeA2] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		# (end of bunch of tests for stuff not being able to use refund account)
		# but buy should be matched by this larger offer
		burnC = self.Burn(4*e(8))
		receiveC = self.SellOffer(state, burnC, ltcOffered=2*e(8), exchangeRate=0x80000000)
		# deposit is 4*e(8) // 16
		depositC = 25000000
		expectedBalances[receiveC] = 4*e(8)-depositC
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 2)
		# completion
		self.Completion(state, 0, 'receiveLTC', 10100000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		depositPart = depositC * 10100000 // (4*e(8))
		expectedBalances[receiveC] += 10100000+depositPart
		self.assertEqual(state._balances.balances, expectedBalances)
		# and the refund account *can* now be used
		self.assertTrue(state._balances.accountHasBalance(changeA2))
		self.assertFalse(state._balances.isReferenced(changeA2))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[changeA2], amount=1, maxBlock=200)
		payDestination = outputs['destination']
		payChange = outputs['change']
		expectedBalances.pop(changeA2)
		expectedBalances[payDestination] = 1
		self.assertEqual(state._balances.balances, expectedBalances)

	def test_exact_match(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=5*e(6), exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {changeB: 1*e(7)-625000-1, receiveB:1})
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances.balances, {changeB:1*e(7)-625000-1, receiveB:1, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances.balances, {changeB:1*e(7)-625000-1, receiveB:1*e(7)+625000+1, refundA:1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_pending_exchange_expires(self):
		# based on test_exact_match, but with pending exchange left to expire
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {changeB: 1*e(7)-625000-1, receiveB:1})
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances.balances, {changeB:1*e(7)-625000-1, receiveB:1, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		for i in range(50):
			state.advanceToNextBlock()
		self.assertEqual(len(state._pendingExchanges), 1)
		state.advanceToNextBlock()
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertRaisesRegexp(AssertionError, 'no pending exchange with the specified index', self.Completion, state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(state._balances.balances, {changeB:1*e(7)-625000-1, receiveB:1, refundA:1*e(7)+625000+1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_offers_dont_meet(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//4, exchangeRate=0x40000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {changeB: 1*e(7)-625000-1, receiveB:1})
		burnA = self.Burn(10000001)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# nothing refunded, no change to balances (except minimum balance seeded in a's refund accounts)
		self.assertEqual(state._balances.balances, {changeB: 1*e(7)-625000-1, receiveB:1, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_sell_remainder_outstanding(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(2*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=2*e(7)//2, exchangeRate=0x80000000)
		# deposit is 2*e(7) // 16
		deposit = 1250000
		expectedBalances = {receiveB:2*e(7)-deposit}
		self.assertEqual(state._balances.balances, expectedBalances)
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		expectedBalances[refundA] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(state._LTCSells.size(), 1) ## half of sell offer is left outstanding
		self.Completion(state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded half his deposit = 625000, plus payment of 10000000
		# (and b now has all swapbill except deposit for outstanding sell offer = 625000)
		expectedBalances[receiveB] += 1*e(7)+625000
		self.assertEqual(state._balances.balances, expectedBalances)
		# but receiving account can't be completely spent yet as this is locked until exchange completed
		self.assertTrue(state._balances.accountHasBalance(receiveB))
		self.assertTrue(state._balances.isReferenced(receiveB))
		changeB = self.Apply_AssertInsufficientFunds(state, 'Pay', sourceAccounts=[receiveB], amount=expectedBalances[receiveB], maxBlock=200)
		expectedBalances[changeB] = expectedBalances.pop(receiveB)
		self.assertEqual(state._balances.balances, expectedBalances)
		# (reference is transfered to the new change output)
		self.assertTrue(state._balances.accountHasBalance(changeB))
		self.assertTrue(state._balances.isReferenced(changeB))
		# a goes on to buy the rest
		burnA2 = self.Burn(1*e(7)+1)
		refundA2 = self.BuyOffer(state, burnA2, 'receiveLTC2', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		expectedBalances[refundA2] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.Completion(state, 1, 'receiveLTC2', 10000000 // 2)
		# other second payment counterparty + second half of deposit are credited to b's receive account
		expectedBalances[changeB] += 1*e(7)+625000
		self.assertEqual(state._balances.balances, expectedBalances)
		# and the (forwarded) receive account *can* now be spent fully
		self.assertTrue(state._balances.accountHasBalance(changeB))
		self.assertFalse(state._balances.isReferenced(changeB))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[changeB], amount=expectedBalances[changeB], maxBlock=200)
		payDestination = outputs['destination']
		expectedBalances[payDestination ] = expectedBalances.pop(changeB)
		self.assertEqual(state._balances.balances, expectedBalances)

	def test_buy_remainder_outstanding(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(20000000)
		receiveB = self.SellOffer(state, burnB, ltcOffered=20000000//2, exchangeRate=0x80000000)
		# deposit is 20000000 // 16 = 1250000
		self.assertEqual(state._balances.balances, {changeB:18750000-1, receiveB:1})
		burnA = self.Burn(30000001)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=30000000, exchangeRate=0x80000000)
		# nothing refunded, no change to balances
		self.assertEqual(state._balances.balances, {changeB:18750000-1, receiveB:1, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._LTCBuys.size(), 1) ## half of buy offer is left outstanding
		self.assertEqual(state._LTCSells.size(), 0)
		self.Completion(state, 0, 'receiveLTC', 20000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded all his deposit, and receives payment in swapbill
		# refund account for a, is still locked by the buy offer
		self.assertEqual(state._balances.balances, {changeB:18750000-1, receiveB:21250000+1, refundA:1})
		# b goes on to sell the rest
		burnB2 = self.Burn(10000000)
		changeB2, receiveB2 = self.SellOffer(state, burnB2, ltcOffered=10000000//2, exchangeRate=0x80000000)
		# refund account for a, with zero amount, is still locked, now by the pending exchange
		self.assertEqual(state._balances.balances, {changeB:18750000-1, receiveB:21250000+1, changeB2:9375000-1, receiveB2:1, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 1, 'receiveLTC', 10000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances.balances, {changeB:18750000-1, receiveB:21250000+1, changeB2:9375000-1, receiveB2:10625000+1, refundA:1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_trade_offers_expire(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000, maxBlock=101)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000})
		state.advanceToNextBlock()
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000})
		self.assertEqual(state._LTCSells.size(), 1)
		state.advanceToNextBlock()
		self.assertEqual(state._LTCSells.size(), 0)
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)})
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000, maxBlock=105)
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7), refundA:1})
		state.advanceToNextBlock()
		state.advanceToNextBlock()
		state.advanceToNextBlock()
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7), refundA:1})
		self.assertEqual(state._LTCBuys.size(), 1)
		state.advanceToNextBlock()
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7), refundA:1*e(7)+1})
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_buy_matches_multiple_sells(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		changeOutputs = []
		receiveOutputs = []
		expectedBalances = {}
		for i in range(4):
			burn = self.Burn(1*e(7))
			changeOutput, receiveOutput = self.SellOffer(state, burn, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
			changeOutputs.append(changeOutput)
			receiveOutputs.append(receiveOutput)
			# deposit is 10000000 // 16 = 625000
			expectedBalances[changeOutput] = 1*e(7)-625000-1
			expectedBalances[receiveOutput] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		burn = self.Burn(3*e(7)+1)
		self.assertEqual(state._LTCSells.size(), 4)
		self.assertEqual(state._LTCBuys.size(), 0)
		change, refund = self.BuyOffer(state, burn, 'receiveLTC', swapBillOffered=25*e(6), exchangeRate=0x80000000)
		# 2 sellers matched completely
		# 1 seller partially matched
		expectedBalances[change] = 5*e(6)
		expectedBalances[refund] = 1
		self.assertEqual(state._LTCSells.size(), 2)
		self.assertEqual(state._LTCBuys.size(), 0)
		self.assertEqual(len(state._pendingExchanges), 3)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.Completion(state, 0, 'receiveLTC', 5*e(6))
		# matched seller gets deposit refund + swapbill counterparty payment
		expectedBalances[receiveOutputs[0]] += 1*e(7) + 625000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 2)
		self.Completion(state, 1, 'receiveLTC', 5*e(6))
		# matched seller gets deposit refund + swapbill counterparty payment
		expectedBalances[receiveOutputs[1]] += 1*e(7) + 625000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 1)
		# at this point, refund account should still be locked for the trade
		reason = self.Apply_AssertFails(state, 'Pay', amount=1, maxBlock=200, sourceAccounts=[refund])
		self.assertEqual(reason, 'insufficient swapbill input')
		# go ahead and complete last pending exchange
		self.Completion(state, 2, 'receiveLTC', 25*e(5))
		# matched seller gets deposit refund + swapbill counterparty payment
		expectedBalances[receiveOutputs[2]] += 5*e(6) + 312500
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 0)
		# and refund account can now be spent
		self.Apply_AssertSucceeds(state, 'Pay', amount=1, maxBlock=200, sourceAccounts=[refund])
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_sell_matches_multiple_buys(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		refundOutputs = []
		expectedBalances = {}
		for i in range(4):
			burn = self.Burn(1*e(7) + 1)
			refundOutput = self.BuyOffer(state, burn, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
			refundOutputs.append(refundOutput)
			expectedBalances[refundOutput] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		burn = self.Burn(25*e(6)//16 + 1)
		self.assertEqual(state._LTCBuys.size(), 4)
		self.assertEqual(state._LTCSells.size(), 0)
		receive = self.SellOffer(state, burn, ltcOffered=25*e(6)//2, exchangeRate=0x80000000)
		# deposit is 25*e(6) // 16
		# 2 buyers matched completely
		# 1 buyer partially matched
		expectedBalances[receive] = 1
		self.assertEqual(state._LTCBuys.size(), 2)
		self.assertEqual(state._LTCSells.size(), 0)
		self.assertEqual(len(state._pendingExchanges), 3)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.Completion(state, 0, 'receiveLTC', 5*e(6))
		# seller gets deposit refund + swapbill counterparty payment for this trade
		expectedBalances[receive] += 1*e(7) + 625000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 2)
		self.Completion(state, 1, 'receiveLTC', 5*e(6))
		# seller gets deposit refund + swapbill counterparty payment for this trade
		expectedBalances[receive] += 1*e(7) + 625000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 1)
		# at this point, receive account should still be referenced for the trade
		self.assertTrue(state._balances.accountHasBalance(receive))
		self.assertTrue(state._balances.isReferenced(receive))
		change = self.Apply_AssertInsufficientFunds(state, 'Pay', sourceAccounts=[receive], amount=expectedBalances[receive], maxBlock=200)
		self.assertTrue(state._balances.accountHasBalance(change))
		self.assertTrue(state._balances.isReferenced(change))
		expectedBalances[change] = expectedBalances.pop(receive)
		# go ahead and complete last pending exchange
		self.Completion(state, 2, 'receiveLTC', 25*e(5))
		# seller gets deposit refund + swapbill counterparty payment for this trade
		expectedBalances[change] += 5*e(6) + 312500
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 0)
		# and receive account can now be spent
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[change], amount=expectedBalances[change], maxBlock=200)
		payDestination = outputs['destination']
		expectedBalances[payDestination] = expectedBalances.pop(change)
		self.assertEqual(state._balances.balances, expectedBalances)


