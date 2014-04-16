from __future__ import print_function
import unittest, random
#from collections import deque
from SwapBill import TransactionTypes, State, TransactionFee, LTCTrading
from SwapBill.Amounts import FromSatoshis, ToSatoshis
from SwapBill.BuildHostedTransaction import InsufficientFunds, Build_FundedByAccount, Build_WithSourceAddress

class MockHostLayer(object):
	def __init__(self):
		self._unspent = []
		self._nextLTC = 0
		self._nextUnspent = 0
		self._transactionsToBeDecoded = []
		self._sourceAddressLookup = {}
	def addUnspent(self, amount, pubKeyHash=None):
		if pubKeyHash is None:
			pubKeyHash = b'ltc' + str(self._nextLTC).encode('ascii')
			self._nextLTC += 1
		else:
			assert type(pubKeyHash) == type(b'')
			if pubKeyHash.startswith(b'SWB'):
				pubKeyHash = b'unspendable'
		d = {}
		d['scriptPubKey'] = 'script pub key for ' + pubKeyHash.decode('ascii') ## only expect to use ascii in pub keys for testing purposes
		i = self._nextUnspent
		self._nextUnspent += 1
		d['txid'] = 'tx' + str(i)
		d['vout'] = random.randrange(0, 6)
		d['amount'] = FromSatoshis(amount)
		d['address'] = 'address for ' + pubKeyHash.decode('ascii') ## only expect to use ascii in pub keys for testing purposes
		self._unspent.append(d)
	def printUnspent(self):
		for d in self._unspent:
			print(d['address'], ':', d['amount'])
	def pubKeyHashFromAddress(self, address):
		prefix = 'address for '
		assert address.startswith(prefix)
		return  address[len(prefix):].encode('ascii')
	def AllNonSwapBill(self, swapBillBalances):
		amounts = []
		asInputs = []
		for output in self._unspent:
			pubKeyHash = self.pubKeyHashFromAddress(output['address'])
			if pubKeyHash == b'unspendable':
				continue
			if not pubKeyHash in swapBillBalances:
				amounts.append(ToSatoshis(output['amount']))
				asInputs.append((output['txid'], output['vout'], output['scriptPubKey']))
		return amounts, asInputs
	def SingleForAddress(self, pubKeyHash):
		for output in self._unspent:
			if output['address'] == 'address for unspendable':
				continue
			if output['address'] == 'address for ' + pubKeyHash.decode('ascii'):
				amount = ToSatoshis(output['amount'])
				asInput = (output['txid'], output['vout'], output['scriptPubKey'])
				return amount, asInput
		return None
	def _consumeInput(self, txID, vOut):
		unspentAfter = []
		found = None
		for output in self._unspent:
			if txID == output['txid'] and vOut == output['vout']:
				assert found is None
				found = output
			else:
				unspentAfter.append(output)
		assert not found is None
		self._unspent = unspentAfter
		pubKeyHash = self.pubKeyHashFromAddress(found['address'])
		self._sourceAddressLookup[(found['txid'], found['vout'])] = pubKeyHash
		return ToSatoshis(found['amount'])
	def sendTX(self, hostTX):
		sumOfInputs = 0
		for i in range(hostTX.numberOfInputs()):
			txID = hostTX.inputTXID(i)
			vOut = hostTX.inputVOut(i)
			sumOfInputs += self._consumeInput(txID, vOut)
		sumOfOutputs = 0
		for i in range(hostTX.numberOfOutputs()):
			amount = hostTX.outputAmount(i)
			assert amount >= TransactionFee.dustLimit
			self.addUnspent(amount, hostTX.outputPubKeyHash(i))
			sumOfOutputs += amount
		TransactionFee.baseFee = sumOfInputs - sumOfOutputs
		## note that the following is just a sanity check
		## can't test here that transaction fee is actually sufficient, because we don't have the transaction byte size
		assert TransactionFee.baseFee >= TransactionFee.baseFee
		## TODO go through create raw transaction, decode raw transaction, at this point?
		## (if decode raw transaction is changed to not require RPC)
		self._transactionsToBeDecoded.append(hostTX)

	def getDecodedTransactions(self):
		self._transactionsToBeDecoded.reverse()
		result = self._transactionsToBeDecoded
		self._transactionsToBeDecoded = []
		return result
	def sync(self, state):
		decodedHostTransactions = self.getDecodedTransactions()
		sourceLookup = SourceLookup(self._sourceAddressLookup)
		for hostTX in decodedHostTransactions:
			decodedTX = TransactionTypes.Decode(sourceLookup, hostTX)
			decodedTX.apply(state)
		state.advanceToNextBlock()

class SourceLookup(object):
	def __init__(self, d):
		self._d = d
	def getSourceFor(self, txID, vout):
		return self._d[(txID, vout)]

class Test(unittest.TestCase):

	def test_burns_and_transfers(self):
		hostLayer = MockHostLayer()
		state = State.State(100, 'mockhash')
		change = b'change'

		## *** Burn transactions

		tx = TransactionTypes.Burn()
		tx.init_FromUserRequirements(burnAmount=100000, target=b'firstBurnTarget')

		unspent = hostLayer.AllNonSwapBill(state._balances)
		self.assertRaises(InsufficientFunds, Build_FundedByAccount, TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		hostLayer.addUnspent(100000)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		self.assertRaises(InsufficientFunds, Build_FundedByAccount, TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		hostLayer.addUnspent(200000)
		hostLayer.addUnspent(300000)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		#print("unspent:", unspent)
		hostTX = Build_FundedByAccount(TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)
		#print("hostTX._inputs:", hostTX._inputs)
		#print("hostTX._outPubKeyHash:", hostTX._outPubKeyHash)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		#print('unspent after first burn:')
		#hostLayer.printUnspent()
		#print('balances after first burn:', state._balances)

		self.assertEqual(state._totalCreated, 100000)
		self.assertDictEqual(state._balances, {b'firstBurnTarget': 100000})

		tx.init_FromUserRequirements(burnAmount=600000, target=b'secondBurnTarget')
		TransactionFee.baseFee = TransactionFee.baseFee

		unspent = hostLayer.AllNonSwapBill(state._balances)
		self.assertRaises(InsufficientFunds, Build_FundedByAccount, TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		tx.init_FromUserRequirements(burnAmount=150000, target=b'secondBurnTarget')
		#print("unspent:", unspent)
		self.assertRaises(InsufficientFunds, Build_FundedByAccount, TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		hostLayer.addUnspent(600000)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		hostTX = Build_FundedByAccount(TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)
		#print("hostTX._inputs:", hostTX._inputs)
		#print("hostTX._outPubKeyHash:", hostTX._outPubKeyHash)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		#print('unspent after second burn:')
		#hostLayer.printUnspent()

		self.assertEqual(state._totalCreated, 250000)
		self.assertDictEqual(state._balances, {b'firstBurnTarget': 100000, b'secondBurnTarget': 150000})

		## can send this transaction again, after getting unspent for current host state
		unspent = hostLayer.AllNonSwapBill(state._balances)
		hostTX = Build_FundedByAccount(TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		#print('unspent after third burn:')
		#hostLayer.printUnspent()
		#print('balances after third burn:', state._balances)

		self.assertEqual(state._totalCreated, 400000)
		self.assertDictEqual(state._balances, {b'firstBurnTarget': 100000, b'secondBurnTarget': 300000})

		## but then we run out of funds
		unspent = hostLayer.AllNonSwapBill(state._balances)
		self.assertRaises(InsufficientFunds, Build_FundedByAccount, TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		## *** transfer transactions

		tx = TransactionTypes.Transfer()
		source = b'firstBurnTarget'
		tx.init_FromUserRequirements(source=source, amount=100, destination=b'transferTarget')

		## this following transaction would have enough funds if it didn't reseed the source address
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		self.assertRaises(InsufficientFunds, Build_WithSourceAddress, TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)
		### add enough funds for reseed, and it should go through
		hostLayer.addUnspent(100000)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)
		self.assertEqual(hostTX.numberOfOutputs(), 3)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertEqual(state._totalCreated, 400000)
		self.assertDictEqual(state._balances, {b'transferTarget': 100, b'firstBurnTarget': 99900, b'secondBurnTarget': 300000})

		## this transfer will be capped
		tx.init_FromUserRequirements(source=source, amount=100000, destination=b'transferTarget2')

		#print('host unspent:')
		#hostLayer.printUnspent()

		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		self.assertIsNotNone(sourceSingleUnspent)
		self.assertRaises(InsufficientFunds, Build_WithSourceAddress, TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)
		hostLayer.addUnspent(800000) ## more ltc backer funds required
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertEqual(state._totalCreated, 400000)
		self.assertDictEqual(state._balances, {b'transferTarget': 100, b'transferTarget2': 99900, b'secondBurnTarget': 300000})

	def test_ltc_trading(self):
		hostLayer = MockHostLayer()
		state = State.State(100, 'mockhash')
		change = b'change'

		## direct calls to initialise some account balances
		state.apply_Burn(ToSatoshis(0.3), b'alice')
		state.apply_Burn(ToSatoshis(0.2), b'bob')
		state.apply_Burn(ToSatoshis(0.5), b'clive')
		state.apply_Burn(ToSatoshis(0.6), b'dave')
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		## backing ltc
		hostLayer.addUnspent(ToSatoshis(0.1))

		## seed ltc
		hostLayer.addUnspent(TransactionFee.dustLimit, b'alice')
		hostLayer.addUnspent(TransactionFee.dustLimit, b'bob')
		hostLayer.addUnspent(TransactionFee.dustLimit, b'clive')
		hostLayer.addUnspent(TransactionFee.dustLimit, b'dave')

		## alice and bob both want to buy LTC
		## clive and dave both want to sell

		## alice makes buy offer

		source = b'alice'
		tx = TransactionTypes.LTCBuyOffer()
		tx.init_FromUserRequirements(source=source, swapBillAmountOffered=ToSatoshis(0.3), exchangeRate=0x80000000, receivingDestination=b'alice_LTC_Receive')
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertDictEqual(state._balances, {b'clive': 50000000, b'bob': 20000000, b'dave': 60000000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCBuys.currentBestExchangeRate(), 0x80000000)
		self.assertEqual(state._LTCBuys.currentBestExpiry(), 0xffffffff)
		buyDetails = state._LTCBuys.peekCurrentBest()
		self.assertDictEqual(buyDetails.__dict__, {'swapBillAmount': 30000000, 'ltcReceiveAddress': b'alice_LTC_Receive', 'swapBillAddress': b'alice'})
		self.assertEqual(state._LTCSells.size(), 0)
		self.assertEqual(len(state._pendingExchanges), 0)

		## bob makes better offer, but with smaller amount

		source = b'bob'
		tx.init_FromUserRequirements(source=source, swapBillAmountOffered=ToSatoshis(0.1), exchangeRate=0x40000000, receivingDestination=b'bob_LTC_Receive')
		#print('host unspent:')
		#hostLayer.printUnspent()
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		#print("unspent:", unspent)
		#print("sourceSingleUnspent:", sourceSingleUnspent)
		#print(tx.__dict__)
		#print(sourceSingleUnspent)
		#print(unspent)
		#print(change)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)
		#print('tx outputs:')
		#for i in range(hostTX.numberOfOutputs()):
			#print('  ', hostTX.outputPubKeyHash(i), hostTX.outputAmount(i))

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertDictEqual(state._balances, {b'bob': 10000000, b'clive': 50000000, b'dave': 60000000})
		self.assertEqual(state._LTCBuys.size(), 2)
		self.assertEqual(state._LTCBuys.currentBestExchangeRate(), 0x40000000)
		self.assertEqual(state._LTCBuys.currentBestExpiry(), 0xffffffff)
		buyDetails = state._LTCBuys.peekCurrentBest()
		#print(buyDetails.__dict__.__repr__())
		self.assertDictEqual(buyDetails.__dict__, {'swapBillAmount': 10000000, 'ltcReceiveAddress': b'bob_LTC_Receive', 'swapBillAddress': b'bob'})
		self.assertEqual(state._LTCSells.size(), 0)
		self.assertEqual(len(state._pendingExchanges), 0)

		## clive makes a sell offer, matching bob's buy exactly

		source = b'clive'
		tx = TransactionTypes.LTCSellOffer()
		tx.init_FromUserRequirements(source=source, swapBillDesired=ToSatoshis(0.1), exchangeRate=0x40000000)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertDictEqual(state._balances, {b'bob': 10000000, b'clive': 49375000, b'dave': 60000000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCBuys.currentBestExchangeRate(), 0x80000000)
		self.assertEqual(state._LTCBuys.currentBestExpiry(), 0xffffffff)
		buyDetails = state._LTCBuys.peekCurrentBest()
		#print(buyDetails.__dict__.__repr__())
		self.assertDictEqual(buyDetails.__dict__, {'swapBillAmount': 30000000, 'ltcReceiveAddress': b'alice_LTC_Receive', 'swapBillAddress': b'alice'})
		self.assertEqual(state._LTCSells.size(), 0)
		self.assertEqual(len(state._pendingExchanges), 1)
		exchangeDetails = state._pendingExchanges[0]
		self.assertDictEqual(exchangeDetails.__dict__, {'expiry': 152, 'swapBillDeposit': 625000, 'ltc': 2500000, 'ltcReceiveAddress': b'bob_LTC_Receive', 'swapBillAmount': 10000000, 'buyerAddress': b'bob', 'sellerAddress': b'clive'})

		## dave and bob make overlapping offers that 'cross over'
		## TODO: wanted to send these two offers together, but they may use the same unspent outputs
		##   - this is then also an issue to sort out for the client in general!

		source = b'bob'
		tx = TransactionTypes.LTCBuyOffer()
		tx.init_FromUserRequirements(source=source, swapBillAmountOffered=ToSatoshis(0.1), exchangeRate=0x40000000, receivingDestination=b'bob_LTC_Receive2')
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertDictEqual(state._balances, {b'clive': 49375000, b'dave': 60000000})
		self.assertEqual(state._LTCBuys.size(), 2)
		self.assertEqual(state._LTCBuys.currentBestExchangeRate(), 0x40000000)
		self.assertEqual(state._LTCSells.size(), 0)

		source = b'dave'
		tx = TransactionTypes.LTCSellOffer()
		tx.init_FromUserRequirements(source=source, swapBillDesired=ToSatoshis(0.2), exchangeRate=0x45000000)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		sourceSingleUnspent = hostLayer.SingleForAddress(source)
		hostTX = Build_WithSourceAddress(TransactionFee.dustLimit, TransactionFee.baseFee, tx, sourceSingleUnspent, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		self.assertDictEqual(state._balances, {b'clive': 49375000, b'dave': 58750000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCBuys.currentBestExchangeRate(), 0x80000000)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(state._LTCSells.currentBestExchangeRate(), 0x45000000)
		self.assertEqual(len(state._pendingExchanges), 2)
		exchangeDetails = state._pendingExchanges[1]
		self.assertDictEqual(exchangeDetails.__dict__, {'expiry': 154, 'swapBillDeposit': 625000, 'ltc': 2597656, 'ltcReceiveAddress': b'bob_LTC_Receive2', 'swapBillAmount': 10000000, 'buyerAddress': b'bob', 'sellerAddress': b'dave'})

		#clive fails to make his payment within the required block clount!
		while state._currentBlockIndex <= 152:
			state.advanceToNextBlock()

		#bob is credited his offer amount (which was locked up for the exchange) + clive's deposit
		self.assertDictEqual(state._balances, {b'bob': 10625000, b'clive': 49375000, b'dave': 58750000})
		self.assertEqual(len(state._pendingExchanges), 1)
		exchangeDetails = state._pendingExchanges[1]
		self.assertDictEqual(exchangeDetails.__dict__, {'expiry': 154, 'swapBillDeposit': 625000, 'ltc': 2597656, 'ltcReceiveAddress': b'bob_LTC_Receive2', 'swapBillAmount': 10000000, 'buyerAddress': b'bob', 'sellerAddress': b'dave'})

		#dave is more on the ball, and makes his completion payment
		#(actually made from 'communal' ltc unspent, in the case of this test)
		tx = TransactionTypes.LTCExchangeCompletion()
		tx.init_FromUserRequirements(ltcAmount=2597656, destination=b'bob_LTC_Receive2', pendingExchangeIndex=1)
		unspent = hostLayer.AllNonSwapBill(state._balances)
		hostTX = Build_FundedByAccount(TransactionFee.dustLimit, TransactionFee.baseFee, tx, unspent, change)

		hostLayer.sendTX(hostTX)
		hostLayer.sync(state)
		self.assertEqual(state.totalAccountedFor(), state._totalCreated)

		#dave gets credited bob's exchange funds, and is also refunded his exchange deposit
		self.assertDictEqual(state._balances, {b'bob': 10625000, b'dave': 69375000, b'clive': 49375000})
		self.assertEqual(state._LTCBuys.size(), 1)
		self.assertEqual(state._LTCBuys.currentBestExchangeRate(), 0x80000000)
		self.assertEqual(state._LTCSells.size(), 1)
		self.assertEqual(state._LTCSells.currentBestExchangeRate(), 0x45000000)
		self.assertEqual(len(state._pendingExchanges), 0)
