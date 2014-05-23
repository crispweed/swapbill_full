from __future__ import print_function
import unittest, sys, shutil, os
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from os import path
from SwapBill import ClientMain
from SwapBillTest.MockHost import MockHost
from SwapBill.Amounts import e
from SwapBill.BuildHostedTransaction import InsufficientFunds
from SwapBill.ClientMain import TransactionNotSuccessfulAgainstCurrentState
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

def GetOwnerBalances(host, ownerList, balances):
	result = {}
	ownerAtStart = host._getOwner()
	for owner in ownerList:
		host._setOwner(owner)
		output, info = RunClient(host, ['get_balance'])
		if info['total'] != 0:
			result[owner] = info['total']
	host._setOwner(ownerAtStart)
	return result
def GetOwnerActiveAccountBalances(host, ownerList, balances):
	result = {}
	ownerAtStart = host._getOwner()
	for owner in ownerList:
		host._setOwner(owner)
		output, info = RunClient(host, ['get_balance'])
		if info['active'] != 0:
			result[owner] = info['active']
	host._setOwner(ownerAtStart)
	return result

def GetOwnerBackingAmounts(host, ownerList, balances):
	result = {}
	ownerAtStart = host._getOwner()
	for owner in ownerList:
		host._setOwner(owner)
		unspent = host.getUnspent()
		ownerTotal = 0
		for entry in unspent:
			account = (entry['txid'], entry['vout'])
			key = host.formatAccountForEndUser(account)
			if not key in balances:
				ownerTotal += entry['amount']
		if ownerTotal > 0:
			result[owner] = ownerTotal
	host._setOwner(ownerAtStart)
	return result

dataDirectory = 'dataDirectoryForTests'

def InitHost():
	if path.exists(dataDirectory):
		assert path.isdir(dataDirectory)
		shutil.rmtree(dataDirectory)
	os.mkdir(dataDirectory)
	return MockHost()

def RunClient(host, args):
	convertedArgs = []
	for arg in args:
		convertedArgs.append(str(arg))
	assert path.isdir(dataDirectory)
	ownerDir = path.join(dataDirectory, host._getOwner())
	if not path.exists(ownerDir):
		os.mkdir(ownerDir)
	fullArgs = ['--datadir', ownerDir] + convertedArgs
	out = io.StringIO()
	result = ClientMain.Main(startBlockIndex=0, startBlockHash=host.getBlockHash(0), useTestNet=True, commandLineArgs=fullArgs, host=host, out=out)
	return out.getvalue(), result

def GetStateInfo(host, includePending=False):
	args = ['get_state_info']
	if includePending:
		args.append('-i')
	output, info = RunClient(host, args)
	#CheckEachBalanceHasUnspent(host, info['balances'])
	return info

class Test(unittest.TestCase):
	def assertBalancesEqual(self, host, expected, includePending=False):
		info = GetStateInfo(host, includePending)
		self.assertSetEqual(set(info['balances'].values()), set(expected))

	def test_basic(self):
		host = InitHost()
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', 2*e(7)])
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', 2*e(7)])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 2*e(7)})
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nStarting from block 0\n'))
		RunClient(host, ['burn', '--quantity', 35*e(6)])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 2*e(7), "03:1": 35*e(6)})
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nStarting from block 0\n'))
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 2*e(7), '04:2': 1*e(7), '04:1': 25*e(6)})

	def test_minimum_balance(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(TransactionNotSuccessfulAgainstCurrentState, 'burn amount is below minimum balance', RunClient, host, ['burn', '--quantity', 1*e(7)-1])
		RunClient(host, ['burn', '--quantity', 2*e(7)])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		self.assertRaisesRegexp(TransactionNotSuccessfulAgainstCurrentState, 'amount is below minimum balance', RunClient, host, ['pay', '--quantity', 1*e(7)-1, '--toAddress', payTargetAddress])
		self.assertRaisesRegexp(TransactionNotSuccessfulAgainstCurrentState, 'transaction includes change output, with change amount below minimum balance', RunClient, host, ['pay', '--quantity', 1*e(7)+1, '--toAddress', payTargetAddress])
		# but can split exactly
		RunClient(host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 1*e(7), 'active': 1*e(7)})
		# or transfer full output amount
		RunClient(host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 0, 'active': 0})

	def test_ltc_sell_missing_unspent_regression(self):
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '100000000'])
		burnTarget = "02:1"
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {burnTarget:100000000})
		RunClient(host, ['post_ltc_sell', '--quantity', '30000000', '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		RunClient(host, ['post_ltc_buy', '--quantity', '30000000', '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', '0'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'04:1': 48125000, '04:2': 1*e(7), '03:2': 41875000})

	def test_refund_account_locked_during_trade(self):
		host = InitHost()
		host._setOwner('1')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '100000000'])
		RunClient(host, ['post_ltc_sell', '--quantity', '30000000', '--exchangeRate', '0.5'])
		output, result = RunClient(host, ['get_balance'])
		# receiving account is created, with minimumBalance, here
		self.assertDictEqual(result, {'total': 98125000, 'active': 88125000})
		host._setOwner('2')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '200000000'])
		RunClient(host, ['post_ltc_buy', '--quantity', '29900000', '--exchangeRate', '0.5'])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 170100000, 'active': 160100000})
		# 1 gets partially refunded, as offers don't match exactly, and remainder is below minimum threshold
		host._setOwner('1')
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 98131250, 'active': 88125000})
		# but the refund account is locked, because it may need to be credited with other amounts depending on how the trade plays out
		# so can't spend or collect this yet
		self.assertRaisesRegexp(ExceptionReportedToUser, 'There are currently less than two spendable swapbill outputs', RunClient, host, ['collect'])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner('1')
		# change output (active account) can be spent
		RunClient(host, ['pay', '--quantity', '88125000', '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 10006250, 'active': 10006250})
		# but not the refund
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No active swapbill balance currently available', RunClient, host, ['pay', '--quantity', '6250', '--toAddress', payTargetAddress])
	def test_receiving_account_locked_during_trade(self):
		host = InitHost()
		host._setOwner('1')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '100000000'])
		RunClient(host, ['post_ltc_sell', '--quantity', '29900000', '--exchangeRate', '0.5'])
		output, result = RunClient(host, ['get_balance'])
		# refund account is created, with minimumBalance, here
		self.assertDictEqual(result, {'total': 98131250, 'active': 88131250})
		host._setOwner('2')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '200000000'])
		RunClient(host, ['post_ltc_buy', '--quantity', '30000000', '--exchangeRate', '0.5'])
		output, result = RunClient(host, ['get_balance'])
		# 2 gets partially refunded straight away, as offers don't match exactly, and remainder is below minimum threshold
		self.assertDictEqual(result, {'total': 170100000, 'active': 160000000})
		# but the refund account is locked, because it may need to be credited with other amounts depending on how the trade plays out
		# so can't spend or collect this yet
		self.assertRaisesRegexp(ExceptionReportedToUser, 'There are currently less than two spendable swapbill outputs', RunClient, host, ['collect'])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner('2')
		# change output (active account) can be spent
		RunClient(host, ['pay', '--quantity', '160000000', '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 10100000, 'active': 10100000})
		# but not the refund
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No active swapbill balance currently available', RunClient, host, ['pay', '--quantity', '100000', '--toAddress', payTargetAddress])

	def test_burn_less_than_dust_limit(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Burn amount is below dust limit', RunClient, host, ['burn', '--quantity', '1000'])

	def test_simultaneous_collect_and_pay(self):
		# attempted to trigger potential issue with consume failing if one of the inputs is already spent,
		# but it turns out the host blockchain takes care of this for us
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '10000000'])
		RunClient(host, ['burn', '--quantity', '20000000'])
		RunClient(host, ['burn', '--quantity', '30000000'])
		self.assertBalancesEqual(host, [10000000,20000000,30000000])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		# we have to 'hide' the mem pool, otherwise the collect knows that one of the outputs is no longer available
		host.hideMemPool = True
		# but then, there is an attempted double spend on one of the inputs
		# (which would be detected by real host, also)
		self.assertRaisesRegexp(ExceptionReportedToUser, 'no unspent found for input, maybe already spent', RunClient, host, ['collect'])
	def test_simultaneous_collect_and_pay2(self):
		# as above, but mem pool is not hidden
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '10000000'])
		RunClient(host, ['burn', '--quantity', '20000000'])
		RunClient(host, ['burn', '--quantity', '30000000'])
		self.assertBalancesEqual(host, [10000000,20000000,30000000])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		RunClient(host, ['collect'])
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['total'], 50000000)

	def test_expired_pay(self):
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '30000000'])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		self.assertBalancesEqual(host, [30000000])
		RunClient(host, ['pay', '--quantity', '10000000', '--toAddress', payTargetAddress, '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True
		# two blocks advanced so far, one for burn, one for pay
		self.assertEqual(host._nextBlock, 2)
		# max block for the pay is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		# so this should be 6
		host._advance(4)
		self.assertEqual(host._nextBlock, 6)
		# so didn't expire yet, on block 6
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 20000000)
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 10000000)
		host._setOwner(host.defaultOwner)
		host._advance(1)
		self.assertEqual(host._nextBlock, 7)
		# but expires on block 7
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 30000000)
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 0)
		host._setOwner(host.defaultOwner)
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['total'], 30000000)
		self.assertEqual(host._nextBlock, 8)
	def test_expired_ltc_buy(self):
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', 4*e(7)])
		RunClient(host, ['post_ltc_buy', '--quantity', 3*e(7), '--exchangeRate', '0.5', '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True
		# two blocks advanced so far, one for burn, one for sell offer
		host._advance(4)
		self.assertEqual(host._nextBlock, 6)
		# max block for the pay is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		# so this should be 6
		# so didn't expire yet, on block 6
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 1*e(7))
		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15*e(6), 'mine': True, 'swapbill offered': 3*e(7)})])
		host._advance(1)
		self.assertEqual(host._nextBlock, 7)
		# but expires on block 7
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 4*e(7))
		self.assertEqual(result['active'], 4*e(7))
		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [])
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['total'], 4*e(7))
		self.assertEqual(result['active'], 4*e(7))
		self.assertEqual(host._nextBlock, 8)
		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [])
	def test_expired_ltc_sell(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--quantity', 3*e(7)])
		RunClient(host, ['post_ltc_sell', '--quantity', 3*e(7), '--exchangeRate', '0.5', '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True
		# two blocks advanced so far, one for burn, one for sell offer
		host._advance(4)
		self.assertEqual(host._nextBlock, 6)
		# max block for the pay is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		# so this should be 6
		# so didn't expire yet, on block 6
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 28125000)
		output, result = RunClient(host, ['get_sell_offers', '-i'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15*e(6), 'mine': True, 'swapbill desired': 3*e(7), 'deposit paid': 1875000})])
		host._advance(1)
		self.assertEqual(host._nextBlock, 7)
		# but expires on block 7
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['total'], 3*e(7))
		output, result = RunClient(host, ['get_sell_offers', '-i'])
		self.assertEqual(result, [])
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['total'], 3*e(7))
		self.assertEqual(host._nextBlock, 8)
		output, result = RunClient(host, ['get_sell_offers'])
		self.assertEqual(result, [])

	def test_burn_funding(self):
		host = InitHost()
		# dustLimit = 100000
		# transactionFee = 100000
		# burn requires burnAmount for control + 1 dust for dest + transactionFee
		# so burn of 1111111 will require 111111 + 100000 + 100000 = 311111
		# so burn of 1*e(7) will require 10000000 + 100000 + 100000 = 10200000
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', 1*e(7)])
		host._addUnspent(1*e(7))
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', 1*e(7)])
		host._addUnspent(100000)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', 1*e(7)])
		host._addUnspent(99999)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', 1*e(7)])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		host._addUnspent(1)
		RunClient(host, ['burn', '--quantity', 1*e(7)])
		burnTarget = "05:1"
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {burnTarget:1*e(7)})

	def test_bad_invocations(self):
		host = InitHost()
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No pending exchange with the specified ID', RunClient, host, ['complete_ltc_sell', '--pending_exchange_id', '123'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'The following path [(]specified for data directory parameter[)] is not a valid path to an existing directory', RunClient, host, ['--datadir=dontMakeADirectoryCalledThis', 'get_balance'])

	def test_burn_and_pay(self):
		host = InitHost()
		nextTX = 1
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--quantity', 1*e(7)])
		firstBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7)})
		RunClient(host, ['burn', '--quantity', 15*e(6)])
		secondBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6)})
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--quantity', 26*e(6)])
		thirdBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6), thirdBurnTarget:26*e(6)})
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		self.assertRaisesRegexp(ClientMain.BadAddressArgument, 'An address argument is not valid', RunClient, host, ['pay', '--quantity', 12*e(6), '--toAddress', 'madeUpAddress'])
		RunClient(host, ['pay', '--quantity', 12*e(6), '--toAddress', payTargetAddress])
		payChange = "0" + str(nextTX) + ":1"
		payTarget = "0" + str(nextTX) + ":2"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6), payTarget:12*e(6), payChange:14*e(6)})
		host._setOwner('recipient')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'active': 12*e(6), 'total': 12*e(6)})
		host._setOwner(host.defaultOwner)
		# and this should not submit because there is no single output large enough for the payment
		self.assertRaises(TransactionNotSuccessfulAgainstCurrentState, RunClient, host, ['pay', '--quantity', 16*e(6), '--toAddress', payTargetAddress])

	def test_burn_and_collect(self):
		host = InitHost()
		nextTX = 1
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--quantity', 1*e(7)])
		firstBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7)})
		RunClient(host, ['burn', '--quantity', 15*e(6)])
		secondBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6)})
		host._addUnspent(6*e(6))
		nextTX += 1
		RunClient(host, ['burn', '--quantity', 16*e(6)])
		thirdBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6), thirdBurnTarget:16*e(6)})
		RunClient(host, ['collect'])
		collectOutput = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {collectOutput:41*e(6)})
		# and should not submit again because there is now only one owned output
		self.assertRaisesRegexp(ExceptionReportedToUser, 'There are currently less than two spendable swapbill outputs.', RunClient, host, ['collect'])

	def test_non_swapbill_transactions(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '10000000'])
		# just some randon transaction taken off the litecoin testnet
		# so, inputs will not be valid for our fake blockchain, but we depend on that not being checked for the purpose of this test
		host._addTransaction("6bc0c859176a50540778c03b6c8f28268823a68cd1cd75d4afe2edbcf50ea8d1", "0100000001566b10778dc28b7cc82e43794bfb26c47ab54a85e1f8e9c8dc04f261024b108c000000006b483045022100aaf6244b7df18296917f430dbb9fa42e159eb79eb3bad8e15a0dfbe84830e08c02206ff81a4cf2cdcd7910c67c13a0694064aec91ae6897d7382dc1e9400b2193bb5012103475fb57d448091d9ca790af2d6d9aca798393199aa70471f38dc359f9f30b50cffffffff0264000000000000001976a914e512a5846125405e009b6f22ac274289f69e185588acb83e5c02000000001976a9147cc3f7daeffe2cfb39630310fad6d0a9fbb4b6aa88ac00000000")
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':10000000})

	def test_double_spend(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', 5*e(7)])
		host.holdNewTransactions = True
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 5*e(7)})
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 5*e(7)})
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No active swapbill balance currently available', RunClient, host, ['pay', '--quantity', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'03:1': 4*e(7), '03:2':1*e(7)})
		# once the first pay transaction goes through, we can make another one
		RunClient(host, ['pay', '--quantity', 15*e(6), '--toAddress', payTargetAddress])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'04:1': 25*e(6), '04:2':15*e(6), '03:2':1*e(7)})

	def test_include_pending(self):
		host = InitHost()
		host._addUnspent(100000000)
		host.holdNewTransactions = True
		RunClient(host, ['burn', '--quantity', '10000000'])
		RunClient(host, ['burn', '--quantity', '20000000'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		output, info = RunClient(host, ['get_state_info', '--includepending'])
		self.assertEqual(info['balances'], {'02:1': 10000000, '03:1': 20000000})
		output, info = RunClient(host, ['get_state_info', '-i'])
		self.assertEqual(info['balances'], {'02:1': 10000000, '03:1': 20000000})
		output, info = RunClient(host, ['get_state_info'])
		self.assertEqual(info['balances'], {})

	def test_two_owners(self):
		host = InitHost()
		host._setOwner('1')
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '10000000'])
		host._setOwner('2')
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '20000000'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':10000000, '04:1':20000000})
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'active': 20000000, 'total': 20000000})
		host._setOwner('1')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'active': 10000000, 'total': 10000000})

	def test_expected_dust_and_fees(self):
		host = InitHost()
		ownerList = ('alice', 'bob', 'clive', 'dave')
		host._setOwner('alice')
		expectedDustAndFees = 200000
		host._addUnspent(3*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--quantity', 3*e(7)])
		host._setOwner('bob')
		host._addUnspent(2*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--quantity', 2*e(7)])
		host._setOwner('clive')
		host._addUnspent(5*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--quantity', 5*e(7)])
		host._setOwner('dave')
		host._addUnspent(6*e(7) + expectedDustAndFees + 100000) ## will have 100000 backing funds left over
		RunClient(host, ['burn', '--quantity', 6*e(7)])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 2*e(7), 'clive': 5*e(7), 'alice': 3*e(7), 'dave': 6*e(7)})
		backingAmounts = GetOwnerBackingAmounts(host, ownerList, info['balances'])
		self.assertDictEqual(backingAmounts, {'dave': 100000})

	def test_ltc_trading(self):
		host = InitHost()
		ownerList = ('alice', 'bob', 'clive', 'dave')
		for owner in ownerList:
			host._setOwner(owner)
			host._addUnspent(2*e(8))
		# initialise some account balances
		host._setOwner('alice')
		RunClient(host, ['burn', '--quantity', 4*e(7)])
		host._setOwner('bob')
		RunClient(host, ['burn', '--quantity', 3*e(7)])
		host._setOwner('clive')
		RunClient(host, ['burn', '--quantity', 6*e(7)])
		host._setOwner('dave')
		RunClient(host, ['burn', '--quantity', 7*e(7)])
		# alice and bob both want to buy LTC
		# clive and dave both want to sell
		# alice makes buy offer
		host._setOwner('alice')
		RunClient(host, ['post_ltc_buy', '--quantity', 3*e(7), '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 3*e(7), 'clive': 6*e(7), 'dave': 7*e(7)})
		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': True, 'swapbill offered': 30000000})])
		# bob makes better offer, but with smaller amount
		host._setOwner('bob')
		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': False, 'swapbill offered': 30000000})])
		RunClient(host, ['post_ltc_buy', '--quantity', 1*e(7), '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 6*e(7), 'dave': 7*e(7)})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		output, result = RunClient(host, ['get_buy_offers'])
		expectedResult = [
		    ('exchange rate', 0.25, {'ltc equivalent': 2500000, 'mine': True, 'swapbill offered': 10000000}),
			('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': False, 'swapbill offered': 30000000})
		]
		self.assertEqual(result, expectedResult)
		# clive makes a sell offer, matching bob's buy exactly
		host._setOwner('clive')
		host._addUnspent(100000000)
		RunClient(host, ['post_ltc_sell', '--quantity', '10000000', '--exchangeRate', '0.25'])
		cliveCompletionPaymentExpiry = host._nextBlock + 50 # note that RunClient posts the transaction, and then the transaction will go through in the next block
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 6*e(7)-625000, 'dave': 7*e(7)})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		output, result = RunClient(host, ['get_sell_offers'])
		self.assertEqual(result, []) # (got matched immediately)
		output, result = RunClient(host, ['get_pending_exchanges'])
		expectedResult = [
		    ('pending exchange index', 0, {
		        'I am seller (and need to complete)': True,
		        'outstanding ltc payment amount': 2500000,
		        'swap bill paid by buyer': 10000000,
		        'expires on block': 57,
		        'I am buyer (and waiting for payment)': False,
		        'deposit paid by seller': 625000
		    })]
		self.assertEqual(result, expectedResult)
		# dave and bob make overlapping offers that 'cross over'
		host._setOwner('bob')
		output, result = RunClient(host, ['get_pending_exchanges'])
		# (as above, but identifies bob as buyer instead of seller)
		expectedResult = [
		    ('pending exchange index', 0, {
		        'I am seller (and need to complete)': False,
		        'outstanding ltc payment amount': 2500000,
		        'swap bill paid by buyer': 10000000,
		        'expires on block': 57,
		        'I am buyer (and waiting for payment)': True,
		        'deposit paid by seller': 625000
		    })]
		self.assertEqual(result, expectedResult)
		# we now need enough to fund the offer, + minimum balance in refund account
		activeAccountBalances = GetOwnerActiveAccountBalances(host, ownerList, info['balances'])
		self.assertDictEqual(activeAccountBalances , {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 5*e(7)-625000, 'dave': 7*e(7)})
		self.assertRaisesRegexp(TransactionNotSuccessfulAgainstCurrentState, 'insufficient balance in source account', RunClient, host, ['post_ltc_buy', '--quantity', 1*e(7), '--exchangeRate', '0.25'])
		# can't collect, because one output is locked for trade
		self.assertRaisesRegexp(ExceptionReportedToUser, 'There are currently less than two spendable swapbill outputs', RunClient, host, ['collect'])
		# so burn some more
		RunClient(host, ['burn', '--quantity', 1*e(7)])
		RunClient(host, ['collect'])
		activeAccountBalances = GetOwnerActiveAccountBalances(host, ownerList, info['balances'])
		self.assertDictEqual(activeAccountBalances , {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 5*e(7)-625000, 'dave': 7*e(7)})
		RunClient(host, ['post_ltc_buy', '--quantity', 1*e(7), '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 5*e(7)-625000+1*e(7), 'dave': 7*e(7)})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		host._setOwner('dave')
		RunClient(host, ['post_ltc_sell', '--quantity', 2*e(7), '--exchangeRate', '0.26953125', '--blocksUntilExpiry', '100'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 5*e(7)-625000+1*e(7), 'dave': 7*e(7) - 1250000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		output, result = RunClient(host, ['get_buy_offers'])
		expectedResult = [('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': False, 'swapbill offered': 30000000})]
		self.assertEqual(result, expectedResult)
		output, result = RunClient(host, ['get_sell_offers'])
		expectedResult = [('exchange rate', 0.26953125, {'deposit paid': 625000, 'ltc equivalent': 2695312, 'mine': True, 'swapbill desired': 10000000})]
		self.assertEqual(result, expectedResult)
		assert cliveCompletionPaymentExpiry > host._nextBlock
		host._advance(cliveCompletionPaymentExpiry - host._nextBlock)
		# GetStateInfo will advance to the expiry block
		# but the exchange doesn't expire until the end of that block
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		host._advance(1)
		#clive failed to make his payment within the required block clount!
		#the pending exchange expires
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		#bob is credited his offer amount (which was locked up for the exchange) + clive's deposit
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 3*e(7)+625000, 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000})
		#dave is more on the ball, and makes his completion payment
		host._setOwner('dave')
		RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', '1'])
		info = GetStateInfo(host)
		#dave gets credited bob's exchange funds, and is also refunded his exchange deposit
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 3*e(7)+625000, 'clive': 6*e(7)-625000, 'dave': 8*e(7)-1250000+625000})
		activeAccountBalances = GetOwnerActiveAccountBalances(host, ownerList, info['balances'])
		self.assertDictEqual(activeAccountBalances , {'alice': 1*e(7), 'bob': 2*e(7)+625000, 'clive': 5*e(7)-625000, 'dave': 6*e(7)-1250000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

