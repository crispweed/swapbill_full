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
	for offer in state._ltcBuys.getSortedOffers():
		result += offer._swapBillOffered
	for offer in state._ltcSells.getSortedOffers():
		result += offer._swapBillDeposit + Constraints.minimumSwapBillBalance
		if offer.isBacked:
			result += offer.backingSwapBill
	for key in state._pendingExchanges:
		exchange = state._pendingExchanges[key]
		result += exchange.swapBillAmount
		result += exchange.swapBillDeposit
	for key in state._ltcSellBackers:
		backer = state._ltcSellBackers[key]
		result += backer.backingAmount
	result += state._totalForwarded
	return result

class Test(unittest.TestCase):
	outputsLookup = {
	    'Burn':('destination',),
	    'Pay':('change','destination'),
	    'LTCBuyOffer':('ltcBuy',),
	    'LTCSellOffer':('ltcSell',),
	    'BackLTCSells':('ltcSellBacker',),
	    'BackedLTCSellOffer':('sellerReceive',),
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

	def Apply_AssertSucceeds(self, state, transactionType, sourceAccounts=None, **details):
		outputs = self.outputsLookup[transactionType]
		# following should not throw if succeeds
		state.checkTransaction(transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		txID = self.TXID()
		error = state.applyTransaction(transactionType, txID=txID, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertIsNone(error)
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
		#outputAccounts = []
		#for i in range(len(outputs)):
			#outputAccounts.append((txID, i + 1))
		#return outputAccounts
		txOutputs = {}
		for i in range(len(outputs)):
			txOutputs[outputs[i]] = (txID, i + 1)
		return txOutputs

	def Apply_AssertFails(self, state, transactionType, expectedError, sourceAccounts=None, **details):
		outputs = self.outputsLookup[transactionType]
		# TODO - implement a proper state copy and comparison!
		expectedBalances = state._balances.balances.copy()
		exchangesBefore = len(state._pendingExchanges)
		try:
			state.checkTransaction(transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		except (State.BadlyFormedTransaction, State.TransactionFailsAgainstCurrentState, State.InsufficientFundsForTransaction):
			failsWithUserFacingException = True
		else:
			failsWithUserFacingException = False
		self.assertTrue(failsWithUserFacingException)

		self.assertDictEqual(state._balances.balances, expectedBalances)
		self.assertEqual(exchangesBefore, len(state._pendingExchanges))
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

		swapBillInput = 0
		atLeastOneReferenced = False
		if sourceAccounts is not None:
			for account in sourceAccounts:
				if account in expectedBalances:
					swapBillInput += expectedBalances[account]
					expectedBalances[account] = 0
					if state._balances.isReferenced(account):
						atLeastOneReferenced = True
					else:
						expectedBalances.pop(account)

		txID = self.TXID()

		changeAccount = (txID, 1)
		if atLeastOneReferenced:
			expectedBalances[changeAccount] = 0
		if swapBillInput != 0:
			expectedBalances[changeAccount] = swapBillInput

		error = state.applyTransaction(transactionType, txID=txID, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
		self.assertIsNotNone(error)
		self.assertEqual(error, expectedError)

		self.assertDictEqual(state._balances.balances, expectedBalances)
		self.assertEqual(exchangesBefore, len(state._pendingExchanges))
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
		return (txID, 1)

	def Apply_AssertInsufficientFunds(self, state, transactionType, sourceAccounts=None, **details):
		return self.Apply_AssertFails(state, transactionType, sourceAccounts=sourceAccounts, expectedError='insufficient funds', **details)

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
		state = State.State(100, 'mockhash')
		self.assertRaises(InvalidTransactionType, state.checkTransaction, 'Burnee', outputs=('destination',), transactionDetails={'amount':1}, sourceAccounts=[])
		self.assertRaises(TypeError, state.checkTransaction, 'Burn', outputs=('destination',), transactionDetails={}, sourceAccounts=[])
		self.assertRaises(TypeError, state.checkTransaction, 'Burn', outputs=('destination',), transactionDetails={'amount':0, 'spuriousAdditionalDetail':0}, sourceAccounts=[])
		# note that setting sourceAccounts to None currently has the effect of changing transaction type for the purpose of error reporting
		self.assertRaises(InvalidTransactionType, state.checkTransaction, 'Burn', sourceAccounts=None, outputs=('destination',), transactionDetails={'amount':1})
		state.checkTransaction('Burn', outputs=('destination',), transactionDetails={'amount':1}, sourceAccounts=[])

	def test_burn(self):
		Constraints.minimumSwapBillBalance = 10
		state = State.State(100, 'mockhash')
		# bad outputs specs
		self.assertRaises(AssertionError, state.checkTransaction, 'Burn', outputs=(), transactionDetails={'amount':0}, sourceAccounts=[])
		self.assertRaises(AssertionError, state.checkTransaction, 'Burn', outputs=('madeUpOutput',), transactionDetails={'amount':0}, sourceAccounts=[])
		self.assertRaises(AssertionError, state.checkTransaction, 'Burn', outputs=('destination','destination'), transactionDetails={'amount':0}, sourceAccounts=[])
		# control with good output specs
		self.Apply_AssertFails(state, 'Burn', 'burn output is below minimum balance', sourceAccounts=[], amount=0)
		self.Apply_AssertFails(state, 'Burn', 'burn output is below minimum balance', sourceAccounts=[], amount=9)
		state.checkTransaction('Burn', outputs=('destination',), transactionDetails={'amount':10}, sourceAccounts=[])
		burn = self.TXID()
		error = state.applyTransaction(transactionType='Burn', txID=burn, outputs=('destination',), transactionDetails={'amount':10}, sourceAccounts=[])
		self.assertIsNone(error)
		self.assertEqual(state._balances.balances, {(burn,1):10})
		# bad transaction just forwards any inputs to change (none here)
		state.applyTransaction('Burn', 'badTX', outputs=('destination',), transactionDetails={'amount':0}, sourceAccounts=[])
		self.assertEqual(state._balances.balances, {(burn,1):10})
		burn2 = self.TXID()
		state.applyTransaction(transactionType='Burn', txID=burn2, outputs=('destination',), transactionDetails={'amount':20}, sourceAccounts=[])
		self.assertEqual(state._balances.balances, {(burn,1):10, (burn2,1):20})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_forwarding(self):
		Constraints.minimumSwapBillBalance = 10
		state = State.State(100, 'mockhash')
		self.state = state
		burn = self.Burn(100000000)
		self.assertEqual(state._balances.balances, {burn:100000000})
		details = {'amount':10, 'maxBlock':200}
		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'ForwardToFutureNetworkVersion', outputs=(), transactionDetails=details, sourceAccounts=[burn])
		self.assertRaises(AssertionError, state.checkTransaction, 'ForwardToFutureNetworkVersion', outputs=('madeUpOutput'), transactionDetails=details, sourceAccounts=[burn])
		self.assertRaises(AssertionError, state.checkTransaction, 'ForwardToFutureNetworkVersion', outputs=('change', 'madeUpOutput'), transactionDetails=details, sourceAccounts=[burn])
		# control with good output specs
		outputs = self.Apply_AssertSucceeds(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[burn], **details)
		change = outputs['change']
		self.assertEqual(state._balances.balances, {change:99999990})
		self.assertEqual(state._totalForwarded, 10)
		details = {'amount':10, 'maxBlock':200}
		details['amount'] = 100000000
		change2 = self.Apply_AssertInsufficientFunds(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[change], **details)
		self.assertEqual(state._balances.balances, {change2:99999990})
		details['amount'] = 0
		change3 = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[change2], expectedError='amount is below minimum balance', **details)
		details['amount'] = 9
		change4 = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[change3], expectedError='amount is below minimum balance', **details)
		details['amount'] = 10
		self.Apply_AssertInsufficientFunds(state, 'ForwardToFutureNetworkVersion', sourceAccounts=['madeUpSourceAccount'], **details)
		self.assertEqual(state._totalForwarded, 10)
		self.assertEqual(state._balances.balances, {change4:99999990})
		details['maxBlock'] = 99
		change5 = self.Apply_AssertFails(state, 'ForwardToFutureNetworkVersion', expectedError='max block for transaction has been exceeded', sourceAccounts=[change4], **details)
		details['maxBlock'] = 100
		self.assertEqual(state._totalForwarded, 10)
		# if forwarding transactions expire, amount has to be paid back as change
		# (for same reason as other transactions such as pay - we've used the source account, and any balance left associated with this account becomes unredeemable)
		self.assertEqual(state._balances.balances, {change5:99999990})
		burn2 = self.Burn(20)
		self.assertEqual(state._balances.balances, {change5:99999990, burn2:20})
		details = {'amount':11, 'maxBlock':200}
		# transaction would generate change output with change amount below minimum balance
		change4 = self.Apply_AssertInsufficientFunds(state, 'ForwardToFutureNetworkVersion', sourceAccounts=[burn2], **details)
		self.assertEqual(state._balances.balances, {change5:99999990, change4:20})
		self.assertEqual(state._totalForwarded, 10)

	def test_burn_and_pay(self):
		Constraints.minimumSwapBillBalance = 10
		state = State.State(100, 'mockhash')
		self.state = state
		output1 = self.Burn(10)
		self.assertEqual(state._balances.balances, {output1:10})
		output2 = self.Burn(20)
		self.assertEqual(state._balances.balances, {output1:10, output2:20})
		output3 = self.Burn(30)
		self.assertEqual(state._balances.balances, {output1:10, output2:20, output3:30})
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, ('tx3',1):30})
		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'Pay', outputs=(), transactionDetails={'amount':0, 'maxBlock':200}, sourceAccounts=[('tx3',1)])
		self.assertRaises(AssertionError, state.checkTransaction, 'Pay', outputs=('madeUpOutput',), transactionDetails={'amount':0, 'maxBlock':200}, sourceAccounts=[('tx3',1)])
		self.assertRaises(AssertionError, state.checkTransaction, 'Pay', outputs=('destination','change'), transactionDetails={'amount':0, 'maxBlock':200}, sourceAccounts=[('tx3',1)])
		# destination amount below minimum balance
		output3 = self.Apply_AssertFails(state, 'Pay', amount=0, maxBlock=200, sourceAccounts=[output3], expectedError='amount is below minimum balance')
		self.assertEqual(state._balances.balances, {('tx1',1):10, ('tx2',1):20, output3:30})
		output3 = self.Apply_AssertFails(state, 'Pay', amount=9, maxBlock=200, sourceAccounts=[output3], expectedError='amount is below minimum balance')
		# change amount below minimum balance
		output2 = self.Apply_AssertInsufficientFunds(state, 'Pay', amount=11, maxBlock=200, sourceAccounts=[('tx2',1)])

		self.assertEqual(state._balances.balances, {('tx1',1):10, output2:20, output3:30})

		self.Apply_AssertSucceeds(state, 'Pay', amount=20, maxBlock=200, sourceAccounts=[output3])
		self.assertEqual(state._balances.balances, {('tx1',1):10, output2:20, ('tx7',1):10, ('tx7',2):20})

		# can't repeat the same transaction (output has been consumed)
		self.Apply_AssertInsufficientFunds(state, 'Pay', amount=20, maxBlock=200, sourceAccounts=[output3])
		self.assertEqual(state._balances.balances, {('tx1',1):10, output2:20, ('tx7',1):10, ('tx7',2):20})

		# can't pay from a nonexistant account
		self.Apply_AssertInsufficientFunds(state, 'Pay', amount=20, maxBlock=200, sourceAccounts=[('tx12',2)])
		self.assertEqual(state._balances.balances, {('tx1',1):10, output2:20, ('tx7',1):10, ('tx7',2):20})

		# not enough balance for payment
		failedPayChange2 = self.Apply_AssertInsufficientFunds(state, 'Pay', amount=11, maxBlock=200, sourceAccounts=[('tx1',1)])
		self.assertEqual(state._balances.balances, {failedPayChange2:10, output2:20, ('tx7',1):10, ('tx7',2):20})

		# (but reduce and this should go through)
		outputs = self.Apply_AssertSucceeds(state, 'Pay', amount=10, maxBlock=200, sourceAccounts=[failedPayChange2])
		payDest = outputs['destination']
		self.assertEqual(state._balances.balances, {output2:20, ('tx7',1):10, ('tx7',2):20, payDest:10})

		# transaction with maxBlock before current block
		self.assertRaisesRegexp(State.TransactionFailsAgainstCurrentState, 'max block for transaction has been exceeded', state.checkTransaction, 'Pay', outputs=('change','destination'), transactionDetails={'amount':10, 'maxBlock':99}, sourceAccounts=[('tx2',1)])
		self.assertEqual(state._balances.balances, {output2:20, ('tx7',1):10, ('tx7',2):20, payDest:10})
		payTX = self.TXID()
		state.applyTransaction('Pay', payTX, outputs=('change','destination'), transactionDetails={'amount':10, 'maxBlock':99}, sourceAccounts=[output2])
		self.assertEqual(state._balances.balances, {(payTX,1):20, ('tx7',1):10, ('tx7',2):20, payDest:10})

		# but maxBlock exactly equal to current block is ok
		outputs = self.Apply_AssertSucceeds(state, 'Pay', amount=10, maxBlock=100, sourceAccounts=[(payTX,1)])
		pay2Change = outputs['change']
		pay2Dest = outputs['destination']
		self.assertEqual(state._balances.balances, {pay2Dest:10, pay2Change:10, ('tx7',1):10, ('tx7',2):20, payDest:10})

	def test_pay_from_multiple(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'mockhash')
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
		change = self.Apply_AssertFails(state, 'LTCBuyOffer', expectedError='does not satisfy minimum exchange amount', sourceAccounts=[burnOutput], swapBillOffered=100, exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		self.assertEqual(state._balances.balances, {change:10000})
		change2 = self.Apply_AssertFails(state, 'LTCSellOffer', expectedError='does not satisfy minimum exchange amount', sourceAccounts=[change], ltcOffered=100//2, exchangeRate=0x80000000, maxBlock=200)
		self.assertEqual(state._balances.balances, {change2:10000})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)
	def test_minimum_exchange_amount2(self):
		Constraints.minimumSwapBillBalance = 1*e(7)
		state = State.State(100, 'mockhash')
		self.state = state
		burnOutput = self.Burn(2*e(7))
		# cannot post buy or sell offers, because of minimum exchange amount constraint
		change = self.Apply_AssertFails(state, 'LTCBuyOffer', expectedError='does not satisfy minimum exchange amount', sourceAccounts=[burnOutput], swapBillOffered=1*e(7)-1, exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		self.Apply_AssertFails(state, 'LTCSellOffer', expectedError='does not satisfy minimum exchange amount', sourceAccounts=[change], ltcOffered=1*e(7)//2-1, exchangeRate=0x80000000, maxBlock=200)

	def test_trade_offers_leave_less_than_minimum_balance(self):
		Constraints.minimumSwapBillBalance = 1*e(7)
		state = State.State(100, 'mockhash')
		self.state = state
		burn = self.Burn(2*e(7))
		# can't leave less than minimum balance as change
		change = self.Apply_AssertInsufficientFunds(state, 'LTCBuyOffer', sourceAccounts=[burn], swapBillOffered=12*e(6), exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		# but all swapbill input can now be spent by the transaction
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[change], swapBillOffered=2*e(7), exchangeRate=0x80000000, receivingAddress='a_receive', maxBlock=200)
		buy = outputs['ltcBuy']
		self.assertEqual(state._balances.balances, {buy:0}) # this account is kept open with zero balance for possible future trade payments
		burn2 = self.Burn(3*e(7))
		# note that sell offers consume minimum balance, as well as deposit
		# can't leave less than minimum balance as change
		deposit = 12*e(6)
		ltc = deposit*Constraints.depositDivisor//2
		change2 = self.Apply_AssertInsufficientFunds(state, 'LTCSellOffer', sourceAccounts=[burn2], ltcOffered=ltc, exchangeRate=0x80000000, maxBlock=200)
		# but all swapbill input can now be spent by the transaction
		deposit = 2*e(7)
		ltc = deposit*Constraints.depositDivisor//2
		self.assertEqual(state._balances.balances, {buy:0, change2:3*e(7)})
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccounts=[change2], ltcOffered=ltc, exchangeRate=0x80000000, maxBlock=200)
		sell = outputs['ltcSell']
		self.assertEqual(state._balances.balances, {buy:0, sell:0})

	def test_ltc_trading1(self):
		# this test adds tests against the ltc transaction types, and also runs through a simple exchange scenario
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'mockhash')
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
		expiredBuyOfferChange = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccounts=[burnA], expectedError='max block for transaction has been exceeded', **details)
		details['maxBlock'] = 100
		expectedBalances[expiredBuyOfferChange] = expectedBalances.pop(burnA)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)

		# try offering more than available
		details['swapBillOffered'] = 3000000000
		failedBuyChange = self.Apply_AssertInsufficientFunds(state, 'LTCBuyOffer', sourceAccounts=[expiredBuyOfferChange], **details)
		expectedBalances[failedBuyChange] = expectedBalances.pop(expiredBuyOfferChange)
		self.assertEqual(state._balances.balances, expectedBalances)

		# zero amount
		details['swapBillOffered'] = 0
		failedBuyChange2 = self.Apply_AssertFails(state, 'LTCBuyOffer', sourceAccounts=[failedBuyChange], expectedError='does not satisfy minimum exchange amount', **details)
		expectedBalances[failedBuyChange2] = expectedBalances.pop(failedBuyChange)
		self.assertEqual(state._balances.balances, expectedBalances)

		self.assertEqual(state._ltcBuys.size(), 0)

		# reasonable buy offer that should go through
		details['swapBillOffered'] = 30000000
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[failedBuyChange2], **details)
		refundA = outputs['ltcBuy']
		expectedBalances.pop(failedBuyChange2)
		expectedBalances[refundA]=70000000
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 1)

		# refund account *can* now be completely spent while still referenced by the trade
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[refundA], amount=expectedBalances[refundA], maxBlock=200)
		changeA = outputs['change']
		payTargetA = outputs['destination']
		expectedBalances[payTargetA] = expectedBalances.pop(refundA)
		expectedBalances[changeA] = 0 # trade reference passes to change account, and so this is kept alive with zero balance
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
		expiredSellOfferChange = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccounts=[burnB], expectedError='max block for transaction has been exceeded', **details)
		details['maxBlock'] = 100
		expectedBalances[expiredSellOfferChange] = expectedBalances.pop(burnB)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcSells.size(), 0)

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
		zeroAmountChange = self.Apply_AssertFails(state, 'LTCSellOffer', sourceAccounts=[offerTooHighChange], expectedError='does not satisfy minimum exchange amount', **details)
		expectedBalances[zeroAmountChange] = expectedBalances.pop(offerTooHighChange)
		self.assertEqual(state._balances.balances, expectedBalances)

		self.assertEqual(state._ltcBuys.size(), 1)
		self.assertEqual(state._ltcSells.size(), 0)

		# reasonable sell offer that should go through (and match)
		details['ltcOffered'] = 40000000//2
		outputs = self.Apply_AssertSucceeds(state, 'LTCSellOffer', sourceAccounts=[zeroAmountChange], **details)
		receivingB = outputs['ltcSell']
		expectedBalances[receivingB] = expectedBalances.pop(zeroAmountChange)-2500000-1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# B must now complete with appropriate ltc payment

		details = {'pendingExchangeIndex':1, 'destinationAddress':'a_receive', 'destinationAmount':20000000}

		# bad output specs
		self.assertRaises(AssertionError, state.checkTransaction, 'LTCExchangeCompletion', outputs=('madeUpOutput'), transactionDetails=details, sourceAccounts=None)

		# bad pending exchange index
		self.Apply_AssertFails(state, 'LTCExchangeCompletion', expectedError='no pending exchange with the specified index', **details)
		# no state change
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# bad receive address
		self.Apply_AssertFails(state, 'LTCExchangeCompletion', expectedError='destination account does not match destination for pending exchange with the specified index', pendingExchangeIndex=0, destinationAddress='randomAddress', destinationAmount=20000000)
		# no state change
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# insufficient payment
		self.Apply_AssertFails(state, 'LTCExchangeCompletion', expectedError='amount is less than required payment amount', pendingExchangeIndex=0, destinationAddress='a_receive', destinationAmount=14999999)
		# no state change (b just loses these ltc)
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertTrue(0 in state._pendingExchanges)

		# pays amount offered for sale, not the amount
		# state should warn us about the ltc overpay, but allow the transaction to go through
		details= {'pendingExchangeIndex':0, 'destinationAddress':'a_receive', 'destinationAmount':20000000}
		self.assertRaisesRegexp(State.TransactionFailsAgainstCurrentState, 'amount is greater than required payment amount', state.checkTransaction, 'LTCExchangeCompletion', outputs=(), transactionDetails=details, sourceAccounts=None)

		# pays actual amount required for match with A's buy offer
		# (well formed completion transaction which should go through)
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', pendingExchangeIndex=0, destinationAddress='a_receive', destinationAmount=15000000)
		# B gets
		# payment of the 3*e(7) offered by A
		# plus fraction of deposit for the amount matched (=1875000)
		# (the rest of the deposit is left with an outstanding remainder sell offer)
		expectedBalances[receivingB] += 3*e(7) + 1875000
		expectedBalances.pop(changeA) # trade completes, so referenced zero balance account is cleaned up here
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 0)

	def test_ltc_buy_change_added_to_refund(self):
		Constraints.minimumSwapBillBalance = 1*e(8)
		state = State.State(100, 'starthash')
		self.state = state
		burn = self.Burn(22*e(7))
		refund = self.BuyOffer(state, burn, 'madeUpReceiveAddress', swapBillOffered=1*e(8), exchangeRate=0x80000000)
		self.assertEqual(state._balances.balances, {refund:12*e(7)})
	def test_ltc_sell_change_added_to_receiving(self):
		Constraints.minimumSwapBillBalance = 1*e(8)
		state = State.State(100, 'starthash')
		self.state = state
		burn = self.Burn(32*e(7))
		receive = self.SellOffer(state, burn, ltcOffered=3*16*e(7)//2, exchangeRate=0x80000000)
		# deposit is 3*16*e(7) // 16
		# seed amount is 1*e(8)
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
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-deposit-1})
		burnA = self.Burn(99*e(5)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=99*e(5), exchangeRate=0x80000000)
		# the offers can't match, because of small (sell) remainder
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-deposit-1, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._ltcBuys.size(), 1)
		self.assertEqual(state._ltcSells.size(), 1)
		# *can* now spend whole balance, even though referenced by the sell offer
		self.assertTrue(state._balances.accountHasBalance(receiveB))
		self.assertTrue(state._balances.isReferenced(receiveB))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[receiveB], amount=1*e(7)-deposit-1, maxBlock=200)
		changeB = outputs['change']
		payB = outputs['destination']
		self.assertEqual(state._balances.balances, {payB:1*e(7)-deposit-1, changeB:0, refundA:1})
		self.assertTrue(state._balances.accountHasBalance(changeB))
		self.assertTrue(state._balances.isReferenced(changeB))
		# and same for buy refund account
		self.assertTrue(state._balances.accountHasBalance(refundA))
		self.assertTrue(state._balances.isReferenced(refundA))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[refundA], amount=1, maxBlock=200)
		changeA = outputs['change']
		payA = outputs['destination']
		self.assertEqual(state._balances.balances, {payB:1*e(7)-deposit-1, changeB:0, payA:1, changeA:0})
		# sell should be matched by this larger offer
		burnC = self.Burn(4*e(8))
		refundC = self.BuyOffer(state, burnC, 'receiveLTC2', swapBillOffered=1*e(8), exchangeRate=0x80000000)
		self.assertEqual(state._balances.balances, {payB:1*e(7)-deposit-1, changeB:1, payA:1, changeA:0, refundC:3*e(8)})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._ltcBuys.size(), 2)
		self.assertEqual(state._ltcSells.size(), 0)
		# completion
		self.Completion(state, 0, 'receiveLTC2', 1*e(7)//2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b gets deposit refunded, plus swapbill payment
		self.assertEqual(state._balances.balances, {payB:1*e(7)-deposit-1, changeB:1+deposit+1*e(7), payA:1, changeA:0, refundC:3*e(8)})
		# and the receiving account is no longer referenced
		self.assertTrue(state._balances.accountHasBalance(changeB))
		self.assertFalse(state._balances.isReferenced(changeB))

	def test_small_buy_remainder(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
		# deposit is 1*e(7) // 16
		depositB = 625000
		expectedBalances = {receiveB:1*e(7)-depositB-1}
		self.assertEqual(state._balances.balances, expectedBalances)
		burnA = self.Burn(10100001)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=10100000, exchangeRate=0x80000000)
		# the offers can't match, because of small (buy) remainder
		expectedBalances[refundA] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._ltcBuys.size(), 1)
		self.assertEqual(state._ltcSells.size(), 1)
		# refund account *can* now be spent completely although still referenced by the trade offer
		self.assertTrue(state._balances.accountHasBalance(refundA))
		self.assertTrue(state._balances.isReferenced(refundA))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[refundA], amount=1, maxBlock=200)
		changeA = outputs['change']
		payA = outputs['destination']
		expectedBalances[payA] = expectedBalances.pop(refundA)
		expectedBalances[changeA] = 0
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertTrue(state._balances.isReferenced(changeA))
		self.assertFalse(state._balances.isReferenced(payA))
		# but buy should be matched by this larger offer
		burnC = self.Burn(4*e(8))
		receiveC = self.SellOffer(state, burnC, ltcOffered=2*e(8), exchangeRate=0x80000000)
		# deposit is 4*e(8) // 16
		depositC = 25000000
		expectedBalances[receiveC] = 4*e(8)-depositC-1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 2)
		# completion
		self.Completion(state, 0, 'receiveLTC', 10100000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		depositPart = depositC * 10100000 // (4*e(8))
		expectedBalances[receiveC] += 10100000+depositPart
		expectedBalances.pop(changeA) # trade completed, so this account is no longer referenced, and therefore cleaned up
		self.assertEqual(state._balances.balances, expectedBalances)

	def test_exact_match(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=5*e(6), exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000-1})
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# no match, but seed amount locked up in sell offer is refunded
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-625000, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)+1*e(7), refundA:1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_pending_exchange_expires(self):
		# based on test_exact_match, but with pending exchange left to expire
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000-1})
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# seed amount (minimum balance) locked up in the sell offer is refunded here
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-625000, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		for i in range(50):
			state.advanceToNextBlock()
		self.assertEqual(len(state._pendingExchanges), 1)
		state.advanceToNextBlock()
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertRaisesRegexp(State.TransactionFailsAgainstCurrentState, 'no pending exchange with the specified index', self.Completion, state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(state._balances.balances, {receiveB:1*e(7)-625000, refundA:1*e(7)+625000+1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_offers_dont_meet(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//4, exchangeRate=0x40000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000-1})
		burnA = self.Burn(10000001)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# no match, no refunds, but minimum balance seeded in a's refund accounts
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000-1, refundA:1})
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
		expectedBalances = {receiveB:2*e(7)-deposit-1}
		self.assertEqual(state._balances.balances, expectedBalances)
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		expectedBalances[refundA] = 1
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1) ## half of sell offer is left outstanding
		self.Completion(state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded half his deposit = 625000, plus payment of 10000000
		# (and b now has all swapbill except deposit for outstanding sell offer = 625000)
		expectedBalances[receiveB] += 1*e(7)+625000
		self.assertEqual(state._balances.balances, expectedBalances)
		# receiving account *can* now be completely spent even though referenced by exchange
		self.assertTrue(state._balances.accountHasBalance(receiveB))
		self.assertTrue(state._balances.isReferenced(receiveB))
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[receiveB], amount=expectedBalances[receiveB], maxBlock=200)
		changeB = outputs['change']
		payB = outputs['destination']
		expectedBalances[payB] = expectedBalances.pop(receiveB)
		expectedBalances[changeB] = 0
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertTrue(state._balances.isReferenced(changeB))
		self.assertFalse(state._balances.isReferenced(payB))
		# a goes on to buy the rest
		burnA2 = self.Burn(1*e(7)+1)
		refundA2 = self.BuyOffer(state, burnA2, 'receiveLTC2', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		expectedBalances[refundA2] = 1
		expectedBalances[changeB] += 1 # b gets seed amount (locked up in the sell offer) refunded
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
		self.assertEqual(state._balances.balances, {receiveB:18750000-1})
		burnA = self.Burn(30000001)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=30000000, exchangeRate=0x80000000)
		# sell offer is consumed completely, so seed amount locked up in this is refunded
		self.assertEqual(state._balances.balances, {receiveB:18750000, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertEqual(state._ltcBuys.size(), 1) # half of buy offer is left outstanding
		self.assertEqual(state._ltcSells.size(), 0)
		self.Completion(state, 0, 'receiveLTC', 20000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		# b should be refunded all his deposit, and receives payment in swapbill
		# refund account for a, is still locked by the buy offer
		self.assertEqual(state._balances.balances, {receiveB:18750000+21250000, refundA:1})
		# b goes on to sell the rest
		burnB2 = self.Burn(10000000)
		receiveB2 = self.SellOffer(state, burnB2, ltcOffered=10000000//2, exchangeRate=0x80000000)
		# refund account for a, is still referenced now by the pending exchange
		self.assertEqual(state._balances.balances, {receiveB:18750000+21250000, receiveB2:9375000, refundA:1})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 1, 'receiveLTC', 10000000 // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances.balances, {receiveB:18750000+21250000, receiveB2:9375000+10625000, refundA:1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_trade_offers_expire(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		burnB = self.Burn(1*e(7))
		receiveB = self.SellOffer(state, burnB, ltcOffered=1*e(7)//2, exchangeRate=0x80000000, maxBlock=101)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000-1})
		state.advanceToNextBlock()
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)-625000-1})
		self.assertEqual(state._ltcSells.size(), 1)
		state.advanceToNextBlock()
		self.assertEqual(state._ltcSells.size(), 0)
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7)})
		burnA = self.Burn(1*e(7)+1)
		refundA = self.BuyOffer(state, burnA, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000, maxBlock=105)
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7), refundA:1})
		state.advanceToNextBlock()
		state.advanceToNextBlock()
		state.advanceToNextBlock()
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7), refundA:1})
		self.assertEqual(state._ltcBuys.size(), 1)
		state.advanceToNextBlock()
		self.assertEqual(state._balances.balances, {receiveB: 1*e(7), refundA:1*e(7)+1})
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_buy_matches_multiple_sells(self):
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		receiveOutputs = []
		expectedBalances = {}
		for i in range(4):
			burn = self.Burn(1*e(7))
			receiveOutput = self.SellOffer(state, burn, ltcOffered=1*e(7)//2, exchangeRate=0x80000000)
			receiveOutputs.append(receiveOutput)
			# deposit is 10000000 // 16 = 625000
			expectedBalances[receiveOutput] = 1*e(7)-625000-1
		self.assertEqual(state._balances.balances, expectedBalances)
		burn = self.Burn(3*e(7))
		self.assertEqual(state._ltcSells.size(), 4)
		self.assertEqual(state._ltcBuys.size(), 0)
		refund = self.BuyOffer(state, burn, 'receiveLTC', swapBillOffered=25*e(6), exchangeRate=0x80000000)
		# 2 sellers matched completely (and get seeded amount refunded)
		# 1 seller partially matched
		expectedBalances[refund] = 5*e(6)
		expectedBalances[receiveOutputs[0]] += 1
		expectedBalances[receiveOutputs[1]] += 1
		self.assertEqual(state._ltcSells.size(), 2)
		self.assertEqual(state._ltcBuys.size(), 0)
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
		# at this point, refund account should still be referenced for the trade
		self.assertTrue(state._balances.isReferenced(refund))
		# go ahead and complete last pending exchange
		self.Completion(state, 2, 'receiveLTC', 25*e(5))
		# matched seller gets deposit refund + swapbill counterparty payment
		expectedBalances[receiveOutputs[2]] += 5*e(6) + 312500
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._pendingExchanges), 0)
		# and refund account can now be spent
		self.assertFalse(state._balances.isReferenced(refund))

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
		self.assertEqual(state._ltcBuys.size(), 4)
		self.assertEqual(state._ltcSells.size(), 0)
		receive = self.SellOffer(state, burn, ltcOffered=25*e(6)//2, exchangeRate=0x80000000)
		# deposit is 25*e(6) // 16
		# 2 buyers matched completely
		# 1 buyer partially matched
		expectedBalances[receive] = 1
		self.assertEqual(state._ltcBuys.size(), 2)
		self.assertEqual(state._ltcSells.size(), 0)
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
		outputs = self.Apply_AssertSucceeds(state, 'Pay', sourceAccounts=[receive], amount=expectedBalances[receive], maxBlock=200)
		change = outputs['change']
		pay = outputs['destination']
		self.assertTrue(state._balances.accountHasBalance(change))
		self.assertTrue(state._balances.isReferenced(change))
		self.assertTrue(state._balances.accountHasBalance(pay))
		self.assertFalse(state._balances.isReferenced(pay))
		expectedBalances[pay] = expectedBalances.pop(receive)
		expectedBalances[change] = 0
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

	def test_bad_back_ltc_sells(self):
		state = State.State(100, 'mockhash')
		self.state = state
		active = self.Burn(1*e(10))
		details = {'backingAmount':1*e(10), 'transactionsBacked':100, 'commission':0x8000000, 'ltcReceiveAddress':'madeUpAddress', 'maxBlock':100}
		# bad outputs specs
		self.assertRaises(AssertionError, state.checkTransaction, 'BackLTCSells', outputs=(), transactionDetails=details, sourceAccounts=[active])
		self.assertRaises(AssertionError, state.checkTransaction, 'BackLTCSells', outputs=('madeUpOutput',), transactionDetails=details, sourceAccounts=[active])
		self.assertRaises(AssertionError, state.checkTransaction, 'BackLTCSells', outputs=('ltcSellBacker','extraOutput'), transactionDetails=details, sourceAccounts=[active])
		# attempt to commit more than available
		details['backingAmount'] = 2*e(10)
		active = self.Apply_AssertInsufficientFunds(state, 'BackLTCSells', sourceAccounts=[active], **details)
		# change amount below minimum balance
		details['backingAmount'] = 1*e(10)-1
		active = self.Apply_AssertInsufficientFunds(state, 'BackLTCSells', sourceAccounts=[active], **details)
		details['backingAmount'] = 1*e(10)
		# can't pay from nonexistant account
		self.Apply_AssertInsufficientFunds(state, 'BackLTCSells', sourceAccounts=['madeUpOutput'], **details)
		self.assertDictEqual(state._balances.balances, {active:1*e(10)})
		self.assertFalse(state._balances.isReferenced(active))
		# transaction with maxBlock before current block
		details['maxBlock'] = 99
		active = self.Apply_AssertFails(state, 'BackLTCSells', sourceAccounts=[active], expectedError='max block for transaction has been exceeded', **details)
		details['maxBlock'] = 100
		self.assertDictEqual(state._balances.balances, {active:1*e(10)})
		self.assertFalse(state._balances.isReferenced(active))
		self.assertEqual(len(state._ltcSellBackers), 0)
		# control transaction which succeeds
		outputs = self.Apply_AssertSucceeds(state, 'BackLTCSells', sourceAccounts=[active], **details)
		refund = outputs['ltcSellBacker']
		active = refund
		self.assertDictEqual(state._balances.balances, {active:0})
		self.assertTrue(state._balances.isReferenced(active))
		self.assertEqual(len(state._ltcSellBackers), 1)
		self.assertDictEqual(state._ltcSellBackers[0].__dict__, {'backingAmount': 1*e(10), 'commission': 134217728, 'expiry': 100, 'ltcReceiveAddress': 'madeUpAddress', 'refundAccount': refund, 'transactionMax': 1*e(8)})
		# but then expires (and is refunded)
		state.advanceToNextBlock()
		self.assertFalse(state._balances.isReferenced(active))
		self.assertEqual(len(state._ltcSellBackers), 0)
		self.assertDictEqual(state._balances.balances, {active:1*e(10)})

	def test_input_credited_during_transaction_regression(self):
		# copied from exact match case, but modified to use single active output throughout
		Constraints.minimumSwapBillBalance = 1
		state = State.State(100, 'starthash')
		self.state = state
		active = self.Burn(2*e(7)+1)
		active = self.SellOffer(state, active, ltcOffered=5*e(6), exchangeRate=0x80000000)
		# deposit is 10000000 // 16 = 625000
		self.assertEqual(state._balances.balances, {active:2*e(7)+1-625000-1})
		active = self.BuyOffer(state, active, 'receiveLTC', swapBillOffered=1*e(7), exchangeRate=0x80000000)
		# no match, but seed amount locked up in sell offer is refunded
		self.assertEqual(state._balances.balances, {active:1*e(7)+1-625000})
		self.assertEqual(len(state._pendingExchanges), 1)
		self.Completion(state, 0, 'receiveLTC', 1*e(7) // 2)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(state._balances.balances, {active:2*e(7)+1})
		self.assertEqual(totalAccountedFor(state), state._totalCreated)

	def test_backed_ltc_sell(self):
		state = State.State(100, 'mockhash')
		self.state = state
		# backer commits funds
		burn = self.Burn(4*e(12))
		details = {'backingAmount':4*e(12), 'transactionsBacked':1000, 'commission':0x20000000, 'ltcReceiveAddress':'backerLTCReceivePKH', 'maxBlock':200}
		outputs = self.Apply_AssertSucceeds(state, 'BackLTCSells', sourceAccounts=[burn], **details)
		backer = outputs['ltcSellBacker']
		expectedBalances = {backer:0}
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(len(state._ltcSellBackers), 1)
		expectedBackerState = {
		    'backingAmount': 4*e(12), 'commission': 536870912,
		    'expiry': 200,
		    'ltcReceiveAddress': 'backerLTCReceivePKH', 'refundAccount': backer, 'transactionMax': 4*e(9)
		}
		self.assertDictEqual(state._ltcSellBackers[0].__dict__, expectedBackerState)
		# normal buy offer
		burn = self.Burn(3*e(7))
		details = {
		    'swapBillOffered':3*e(7), 'exchangeRate':0x80000000,
		    'maxBlock':100,
		    'receivingAddress':'buyerReceivePKH'
		}
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[burn], **details)
		buy = outputs['ltcBuy']
		expectedBalances[buy]=0
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 1)
		# backed sell offer
		ltcOffered = 4*e(7)//2
		details = {
		    'backerIndex':0,
		    'backerLTCReceiveAddress':'backerLTCReceivePKH',
		    'ltcOfferedPlusCommission':ltcOffered + ltcOffered//8, 'exchangeRate':0x80000000
		}
		outputs = self.Apply_AssertSucceeds(state, 'BackedLTCSellOffer', sourceAccounts=[], **details)
		sell = outputs['sellerReceive']
		expectedBalances[sell] = 3*e(7) # we get paid straight away!
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertDictEqual(state._pendingExchanges[0].__dict__, {'backerIndex':0, 'buyerAccount':buy, 'buyerLTCReceive':'buyerReceivePKH', 'expiry':150, 'ltc':3*e(7)//2, 'sellerAccount':backer, 'swapBillAmount':3*e(7), 'swapBillDeposit':3*e(7)//Constraints.depositDivisor})
		self.assertEqual(len(state._ltcSellBackers), 1)
		expectedBackerState['backingAmount'] -= 4*e(7)
		expectedBackerState['backingAmount'] -= 4*e(7)//Constraints.depositDivisor
		expectedBackerState['backingAmount'] -= Constraints.minimumSwapBillBalance
		self.assertDictEqual(state._ltcSellBackers[0].__dict__, expectedBackerState)
		# backer is then responsable for completing the exchange with the buyer
		details = {'pendingExchangeIndex':0, 'destinationAddress':'buyerReceivePKH', 'destinationAmount':3*e(7)//2}
		self.Apply_AssertSucceeds(state, 'LTCExchangeCompletion', **details)
		# and backer now gets
		# payment of the 3*e(7) offered by A
		# plus fraction of deposit for the amount matched (=1875000)
		# (the rest of the deposit is left with an outstanding remainder sell offer)
		expectedBackerState['backingAmount'] += 3*e(7)
		expectedBackerState['backingAmount'] += 3*e(7)//Constraints.depositDivisor
		self.assertDictEqual(state._ltcSellBackers[0].__dict__, expectedBackerState)
		expectedBalances.pop(buy) # trade completes, so referenced zero balance account is cleaned up here
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 1)
		self.assertEqual(len(state._pendingExchanges), 0)
		self.assertEqual(len(state._ltcSellBackers), 1)
		# another buy, to match the outstanding sell remainder
		burn = self.Burn(1*e(7))
		details = {
		    'swapBillOffered':1*e(7), 'exchangeRate':0x80000000,
		    'maxBlock':100,
		    'receivingAddress':'buyerReceivePKH2'
		}
		outputs = self.Apply_AssertSucceeds(state, 'LTCBuyOffer', sourceAccounts=[burn], **details)
		buy2 = outputs['ltcBuy']
		# (matches straight away)
		expectedBalances[buy2] = 0
		expectedBalances[sell] += 1*e(7) # seller is paid straight away
		expectedBalances[backer] += Constraints.minimumSwapBillBalance # TODO get this sent back to backer object
		self.assertEqual(state._ltcBuys.size(), 0)
		self.assertEqual(state._ltcSells.size(), 0)
		self.assertEqual(len(state._pendingExchanges), 1)
		self.assertDictEqual(state._pendingExchanges[1].__dict__, {'backerIndex':0, 'buyerAccount':buy2, 'buyerLTCReceive':'buyerReceivePKH2', 'expiry':150, 'ltc':1*e(7)//2, 'sellerAccount':backer, 'swapBillAmount':1*e(7), 'swapBillDeposit':1*e(7)//Constraints.depositDivisor})
		self.assertEqual(state._balances.balances, expectedBalances)
		self.assertDictEqual(state._ltcSellBackers[0].__dict__, expectedBackerState)
