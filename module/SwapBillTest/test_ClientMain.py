from __future__ import print_function
import unittest, sys, shutil, os, random
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
from SwapBill.HardCodedProtocolConstraints import Constraints

class MockKeyGenerator(object):
	def __init__(self):
		self._next = 0
	def generatePrivateKey(self):
		result = str(self._next) + '-' * 31
		self._next += 1
		result = result[:32]
		return result.encode('ascii')
	def privateKeyToPubKeyHash(self, privateKey):
		s = privateKey.decode('ascii').strip('-')
		i = int(s)
		result = str(i) + 'i' * 19
		result = result[:20]
		return result.encode('ascii')
keyGenerator = MockKeyGenerator()

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

def GetBackingAmount(host, balances):
	result = 0
	unspent = host.getUnspent()
	for entry in unspent:
		account = (entry['txid'], entry['vout'])
		key = host.formatAccountForEndUser(account)
		if not key in balances:
			result += entry['amount']
	return result

dataDirectory = 'dataDirectoryForTests'

def InitHost():
	if path.exists(dataDirectory):
		assert path.isdir(dataDirectory)
		shutil.rmtree(dataDirectory)
	os.mkdir(dataDirectory)
	return MockHost(keyGenerator=keyGenerator)

def RunClient(host, args):
	convertedArgs = []
	for arg in args:
		convertedArgs.append(str(arg))
	assert path.isdir(dataDirectory)
	ownerDir = path.join(dataDirectory, host._getOwner())
	if not path.exists(ownerDir):
		os.mkdir(ownerDir)
	fullArgs = ['--dataDir', ownerDir] + convertedArgs
	out = io.StringIO()
	assert host.getBlockHashAtIndexOrNone(0) is not None
	result = ClientMain.Main(startBlockIndex=0, startBlockHash=host.getBlockHashAtIndexOrNone(0), useTestNet=True, commandLineArgs=fullArgs, host=host, keyGenerator=keyGenerator, out=out)
	return out.getvalue(), result

def GetStateInfo(host, includePending=False, forceRescan=False):
	args = []
	if forceRescan:
		args.append('--forceRescan')
	args.append('get_state_info')
	if includePending:
		args.append('-i')
	output, info = RunClient(host, args)
	#CheckEachBalanceHasUnspent(host, info['balances'])
	return info

class Test(unittest.TestCase):
	def assertBalancesEqual(self, host, expected, includePending=False):
		info = GetStateInfo(host, includePending)
		self.assertSetEqual(set(info['balances'].values()), set(expected))

	def test_burn_pay_and_sync_output(self):
		host = InitHost()
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--amount', 2*e(7)])
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', 2*e(7)])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 2*e(7)})
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nState update starting from block 0\n'))
		RunClient(host, ['burn', '--amount', 35*e(6)])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 2*e(7), "03:1": 35*e(6)})
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nState update starting from block 0\n'))
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"03:1": 35*e(6), '04:2': 1*e(7), '04:1': 1*e(7)})
		self.assertEqual(info['syncOutput'].count('in memory: Burn'), 2)
		self.assertEqual(info['syncOutput'].count('in memory: Pay'), 1)
		self.assertEqual(info['syncOutput'], 'Loaded cached state data successfully\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Burn\n - 20000000 swapbill output added\nin memory: Burn\n - 35000000 swapbill output added\nin memory: Pay\n - 20000000 swapbill output consumed\n - 10000000 swapbill output added\nIn memory state updated to end of block 3\n')
		host._setOwner('recipient')
		info = GetStateInfo(host)
		self.assertEqual(info['syncOutput'].count('in memory: Burn'), 0)
		self.assertEqual(info['syncOutput'].count('in memory: Pay'), 1)
		# ** following changed since change to call get_receive_address for payTargetAddress
		# and get_receive_address then currently does a sync
		self.assertEqual(info['syncOutput'], 'Loaded cached state data successfully\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Pay\n - 10000000 swapbill output added\nIn memory state updated to end of block 3\n')
		#self.assertEqual(info['syncOutput'], 'Failed to load from cache, full index generation required (no cache file found)\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Pay\n - 10000000 swapbill output added\nIn memory state updated to end of block 3\n')
		host._setOwner('someoneElse')
		info = GetStateInfo(host)
		self.assertEqual(info['syncOutput'].count('in memory: Burn'), 0)
		self.assertEqual(info['syncOutput'].count('in memory: Pay'), 0)
		self.assertEqual(info['syncOutput'], 'Failed to load from cache, full index generation required (no cache file found)\nState update starting from block 0\nCommitted state updated to start of block 0\nIn memory state updated to end of block 3\n')

	def test_bad_control_address_prefix(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', 2*e(7)])
		RunClient(host, ['burn', '--amount', 3*e(7)])
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		RunClient(host, ['burn', '--amount', 4*e(7)])
		RunClient(host, ['pay', '--amount', 2*e(7), '--toAddress', payTargetAddress])
		corruptedMemPool = []
		for txID, txHex in host._memPool:
			assert txHex.count('5342') == 1
			corruptedTXHex = txHex.replace('5342', '5343')
			corruptedMemPool.append((txID, corruptedTXHex))
		host._memPool = corruptedMemPool
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		# 'corrupted' transactions have bad control address, and should just be ignored
		self.assertEqual(info['syncOutput'], 'Loaded cached state data successfully\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Burn\n - 20000000 swapbill output added\nin memory: Burn\n - 30000000 swapbill output added\nIn memory state updated to end of block 3\n')
		# add tests for other badly formed transactions?

	def test_start_block_not_reached(self):
		host = InitHost()
		ownerDir = path.join(dataDirectory, host._getOwner())
		if not path.exists(ownerDir):
			os.mkdir(ownerDir)
		args = ['--dataDir', ownerDir, 'get_balance']
		out = io.StringIO()
		startBlock = 5
		assert host.getBlockHashAtIndexOrNone(startBlock) is None
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Block chain has not reached the swapbill start block [(]5[)][.]', ClientMain.Main, startBlockIndex=startBlock, startBlockHash='madeUpBlockHash', useTestNet=True, commandLineArgs=args, host=host, out=out)

	def test_minimum_balance(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(TransactionNotSuccessfulAgainstCurrentState, 'burn output is below minimum balance', RunClient, host, ['burn', '--amount', 1*e(7)-1])
		RunClient(host, ['burn', '--amount', 2*e(7)])
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		self.assertRaisesRegexp(TransactionNotSuccessfulAgainstCurrentState, 'amount is below minimum balance', RunClient, host, ['pay', '--amount', 1*e(7)-1, '--toAddress', payTargetAddress])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Insufficient swapbill for transaction', RunClient, host, ['pay', '--amount', 1*e(7)+1, '--toAddress', payTargetAddress])
		# but can split exactly
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 1*e(7), 'spendable': 1*e(7)})
		# or transfer full output amount
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 0, 'spendable': 0})

	def test_ltc_sell_missing_unspent_regression(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 1*e(8)])
		burnTarget = "02:1"
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {burnTarget:1*e(8)})
		RunClient(host, ['post_ltc_sell', '--ltcOffered', 3*e(7)//2, '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		RunClient(host, ['complete_ltc_sell', '--pendingExchangeID', '0'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'04:1': 1*e(8)})

	def test_refund_account_locked_during_trade(self):
		host = InitHost()
		host._setOwner('1')
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 1*e(8)])
		RunClient(host, ['post_ltc_sell', '--ltcOffered', 3*e(7)//2, '--exchangeRate', '0.5', '--blocksUntilExpiry', 20])
		deposit = 3*e(7) // 16
		output, result = RunClient(host, ['get_balance'])
		# receiving account is created, with minimumBalance, here
		self.assertDictEqual(result, {'total': 1*e(8)-deposit, 'spendable': 9*e(7)-deposit})
		host._setOwner('2')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--amount', 2*e(8)])
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', '29900000', '--exchangeRate', '0.5'])
		# the offers can't match, because this would result in a remainder below minimum exchange
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 170100000, 'spendable': 160100000})
		host._setOwner('1')
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 1*e(8)-deposit, 'spendable': 9*e(7)-deposit})
		# and the refund account is locked, because it may need to be credited with other amounts depending on how the trade plays out
		# so can't spend this yet
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner('1')
		# change output (active account) can be spent
		RunClient(host, ['pay', '--amount', 9*e(7)-deposit, '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 1*e(7), 'spendable': 0})
		# but not the minimum balance amount seeded into refund account
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Insufficient swapbill for transaction', RunClient, host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
	def test_receiving_account_locked_during_trade(self):
		host = InitHost()
		host._setOwner('1')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--amount', '100000000'])
		RunClient(host, ['post_ltc_sell', '--ltcOffered', 29900000//2, '--exchangeRate', '0.5'])
		output, result = RunClient(host, ['get_balance'])
		# refund account is created, with minimumBalance, here
		self.assertDictEqual(result, {'total': 98131250, 'spendable': 88131250})
		host._setOwner('2')
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--amount', '200000000'])
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', '30000000', '--exchangeRate', '0.5'])
		output, result = RunClient(host, ['get_balance'])
		# the offers can't match, because this would result in a remainder below minimum exchange
		self.assertDictEqual(result, {'total': 170000000, 'spendable': 160000000})
		# and the refund account is then locked, because it may need to be credited, depending on how the trade plays out
		# so can't spend this yet
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner('2')
		# change output (active account) can be spent
		RunClient(host, ['pay', '--amount', '160000000', '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'total': 10000000, 'spendable': 0})
		# but not the minimum balance amount seeded into receive account
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Insufficient swapbill for transaction', RunClient, host, ['pay', '--amount', '10000000', '--toAddress', payTargetAddress])

	def test_burn_less_than_dust_limit(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Burn amount is below dust limit', RunClient, host, ['burn', '--amount', '1000'])

	def test_expired_pay(self):
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--amount', '30000000'])
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		self.assertBalancesEqual(host, [30000000])
		RunClient(host, ['pay', '--amount', '10000000', '--toAddress', payTargetAddress, '--blocksUntilExpiry', '4'])
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
		RunClient(host, ['burn', '--amount', 4*e(7)])
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.5', '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True


		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15*e(6), 'mine': True, 'swapbill offered': 3*e(7)})])

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
		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [])
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['total'], 4*e(7))
		self.assertEqual(host._nextBlock, 8)
		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [])
	def test_expired_ltc_sell(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 3*e(7)])
		RunClient(host, ['post_ltc_sell', '--ltcOffered', 3*e(7)//2, '--exchangeRate', '0.5', '--blocksUntilExpiry', '4'])
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
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc offered': 15*e(6), 'mine': True, 'swapbill equivalent': 3*e(7), 'deposit paid': 1875000})])
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
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--amount', 1*e(7)])
		host._addUnspent(1*e(7))
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--amount', 1*e(7)])
		host._addUnspent(100000)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--amount', 1*e(7)])
		host._addUnspent(99999)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--amount', 1*e(7)])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		host._addUnspent(1)
		RunClient(host, ['burn', '--amount', 1*e(7)])
		burnTarget = "05:1"
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {burnTarget:1*e(7)})

	def test_bad_invocations(self):
		host = InitHost()
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No pending exchange with the specified ID', RunClient, host, ['complete_ltc_sell', '--pendingExchangeID', '123'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'The following path [(]specified for data directory parameter[)] is not a valid path to an existing directory', RunClient, host, ['--dataDir=dontMakeADirectoryCalledThis', 'get_balance'])

	def test_burn_and_pay(self):
		host = InitHost()
		nextTX = 1
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--amount', 1*e(7)])
		firstBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7)})
		RunClient(host, ['burn', '--amount', 15*e(6)])
		secondBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6)})
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--amount', 26*e(6)])
		thirdBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6), thirdBurnTarget:26*e(6)})
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		self.assertRaisesRegexp(ClientMain.BadAddressArgument, 'An address argument is not valid', RunClient, host, ['pay', '--amount', 12*e(6), '--toAddress', 'madeUpAddress'])
		RunClient(host, ['pay', '--amount', 12*e(6), '--toAddress', payTargetAddress])
		payChange = "0" + str(nextTX) + ":1"
		payTarget = "0" + str(nextTX) + ":2"
		nextTX += 1
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'spendable': 39*e(6), 'total': 39*e(6)})
		host._setOwner('recipient')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'spendable': 12*e(6), 'total': 12*e(6)})
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {thirdBurnTarget:26*e(6), payTarget:12*e(6), payChange:13*e(6)})
		host._setOwner(host.defaultOwner)
		# and this should now work, now we can use more than one input per transaction
		RunClient(host, ['pay', '--amount', 16*e(6), '--toAddress', payTargetAddress])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'spendable': 23*e(6), 'total': 23*e(6)})
		host._setOwner('recipient')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'spendable': 28*e(6), 'total': 28*e(6)})

	def test_pay_from_multiple_outputs(self):
		host = InitHost()
		nextTX = 1
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--amount', 1*e(7)])
		firstBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7)})
		RunClient(host, ['burn', '--amount', 15*e(6)])
		secondBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6)})
		host._addUnspent(6*e(6))
		nextTX += 1
		RunClient(host, ['burn', '--amount', 16*e(6)])
		thirdBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:1*e(7), secondBurnTarget:15*e(6), thirdBurnTarget:16*e(6)})
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--amount', 41*e(6), '--toAddress', payTargetAddress])
		payChange = "0" + str(nextTX) + ":1"
		payTarget = "0" + str(nextTX) + ":2"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {payTarget:41*e(6)})

	def test_non_swapbill_transactions(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', '10000000'])
		# just some randon transaction taken off the litecoin testnet
		# so, inputs will not be valid for our fake blockchain, but we depend on that not being checked for the purpose of this test
		host._addTransaction("6bc0c859176a50540778c03b6c8f28268823a68cd1cd75d4afe2edbcf50ea8d1", "0100000001566b10778dc28b7cc82e43794bfb26c47ab54a85e1f8e9c8dc04f261024b108c000000006b483045022100aaf6244b7df18296917f430dbb9fa42e159eb79eb3bad8e15a0dfbe84830e08c02206ff81a4cf2cdcd7910c67c13a0694064aec91ae6897d7382dc1e9400b2193bb5012103475fb57d448091d9ca790af2d6d9aca798393199aa70471f38dc359f9f30b50cffffffff0264000000000000001976a914e512a5846125405e009b6f22ac274289f69e185588acb83e5c02000000001976a9147cc3f7daeffe2cfb39630310fad6d0a9fbb4b6aa88ac00000000")
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':10000000})

	def test_double_spend(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', 5*e(7)])
		host.holdNewTransactions = True
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 5*e(7)})
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 5*e(7)})
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Insufficient swapbill for transaction', RunClient, host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'03:1': 4*e(7), '03:2':1*e(7)})
		# once the first pay transaction goes through, we can make another one
		RunClient(host, ['pay', '--amount', 15*e(6), '--toAddress', payTargetAddress])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'04:1': 25*e(6), '04:2':15*e(6), '03:2':1*e(7)})

	def test_include_pending(self):
		host = InitHost()
		host._addUnspent(100000000)
		host.holdNewTransactions = True
		RunClient(host, ['burn', '--amount', '10000000'])
		RunClient(host, ['burn', '--amount', '20000000'])
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
		RunClient(host, ['burn', '--amount', '10000000'])
		host._setOwner('2')
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', '20000000'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':10000000, '04:1':20000000})
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'total': 20000000, 'spendable': 20000000})
		host._setOwner('1')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'total': 10000000, 'spendable': 10000000})

	def test_expected_dust_and_fees(self):
		host = InitHost()
		ownerList = ('alice', 'bob', 'clive', 'dave')
		host._setOwner('alice')
		expectedDustAndFees = 200000
		host._addUnspent(3*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--amount', 3*e(7)])
		host._setOwner('bob')
		host._addUnspent(2*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--amount', 2*e(7)])
		host._setOwner('clive')
		host._addUnspent(5*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--amount', 5*e(7)])
		host._setOwner('dave')
		host._addUnspent(6*e(7) + expectedDustAndFees + 100000) ## will have 100000 backing funds left over
		RunClient(host, ['burn', '--amount', 6*e(7)])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 2*e(7), 'clive': 5*e(7), 'alice': 3*e(7), 'dave': 6*e(7)})
		backingAmount = GetBackingAmount(host, info['balances'])
		self.assertEqual(backingAmount, 100000)

	def test_ltc_trading(self):
		host = InitHost()
		ownerList = ('alice', 'bob', 'clive', 'dave')
		for owner in ownerList:
			host._setOwner(owner)
			host._addUnspent(2*e(8))
		# initialise some account balances
		host._setOwner('alice')
		RunClient(host, ['burn', '--amount', 4*e(7)])
		host._setOwner('bob')
		RunClient(host, ['burn', '--amount', 3*e(7)])
		host._setOwner('clive')
		RunClient(host, ['burn', '--amount', 6*e(7)])
		host._setOwner('dave')
		RunClient(host, ['burn', '--amount', 7*e(7)])
		# alice and bob both want to buy LTC
		# clive and dave both want to sell
		# alice makes buy offer
		host._setOwner('alice')
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.5', '--blocksUntilExpiry', 100])
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
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', 1*e(7), '--exchangeRate', '0.25'])
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
		RunClient(host, ['post_ltc_sell', '--ltcOffered', 10000000//4, '--exchangeRate', '0.25'])
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
		# we now need enough to fund the offer with minimum balance in refund account
		# (which should now be possible without any new burns)
		RunClient(host, ['post_ltc_buy', '--swapBillOffered', 1*e(7), '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 5*e(7)-625000+1*e(7), 'dave': 7*e(7)})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		host._setOwner('dave')
		exchangeRate = 1157627904
		RunClient(host, ['post_ltc_sell', '--ltcOffered', 2*e(7) * exchangeRate // 0x100000000, '--exchangeRate_AsInteger', exchangeRate, '--blocksUntilExpiry', '100'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 5*e(7)-625000+1*e(7), 'dave': 7*e(7) - 1250000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		output, result = RunClient(host, ['get_buy_offers'])
		expectedResult = [('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': False, 'swapbill offered': 30000000})]
		self.assertEqual(result, expectedResult)
		output, result = RunClient(host, ['get_sell_offers'])
		# didn't check the exact calculations for this value, but seems about right
		# note that dave now *gets more swapbill*, in the case of overlapping offers, instead of *spending less litecoin*
		daveSwapBillReceived = 11125000
		daveDepositRemainder = 647645
		daveDepositMatched = 1250000 - daveDepositRemainder
		expectedResult = [('exchange rate', 0.26953125, {'deposit paid': daveDepositRemainder, 'ltc offered': 2792969, 'mine': True, 'swapbill equivalent': 10362319})]
		self.assertEqual(result, expectedResult)
		assert cliveCompletionPaymentExpiry > host._nextBlock
		host._advance(cliveCompletionPaymentExpiry - host._nextBlock)
		# GetStateInfo will advance to the expiry block
		# but the exchange doesn't expire until the end of that block
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000})
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
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7)+625000, 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000})
		#dave is more on the ball, and makes his completion payment
		host._setOwner('dave')
		RunClient(host, ['complete_ltc_sell', '--pendingExchangeID', '1'])
		info = GetStateInfo(host)
		#dave gets credited bob's exchange funds, and is also refunded the matched part of his exchange deposit
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7)+625000, 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000+1*e(7)+daveDepositMatched})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		host._setOwner('alice')
		info = GetStateInfo(host, includePending=False, forceRescan=True)
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCBuyOffer'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 0)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 0)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 0)
		host._setOwner('bob')
		info = GetStateInfo(host, includePending=False, forceRescan=True)
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCBuyOffer'), 2)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 2)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 1)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 1)
		host._setOwner('clive')
		info = GetStateInfo(host, includePending=False, forceRescan=True)
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 0)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 1)
		host._setOwner('dave')
		info = GetStateInfo(host, includePending=False, forceRescan=True)
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 1)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 0)

	def test_transaction_parameter_ranges(self):
		# following requires a long in python 2.7
		host = InitHost()
		host._addUnspent(2*e(19))
		RunClient(host, ['burn', '--amount', 1*e(19)])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'total': 1*e(19), 'spendable': 1*e(19)})
		# greater than 8 bytes
		host = InitHost()
		host._addUnspent(2*e(20))
		self.assertRaises(Exception, RunClient, host, ['burn', '--amount', 1*e(20)])
		host = InitHost()
		host._addUnspent(2*e(15))
		# note that we don't get an error from the point of encoding, because transactions are checked against state first
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Burn amount is below dust limit', RunClient, host, ['burn', '--amount', -1*e(7)])
		self.assertRaisesRegexp(ValueError, 'invalid literal', RunClient, host, ['burn', '--amount', 'lots'])
		# can burn amounts above 6 byte range, because this is not encoded in control address
		RunClient(host, ['burn', '--amount', 1*e(15)])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'total': 1*e(15), 'spendable': 1*e(15)})
		# but amounts for pay transaction (for example) *are* restricted
		host._setOwner('recipient')
		output, result = RunClient(host, ['get_receive_address'])
		payTargetAddress = result['receive_address']
		host._setOwner(host.defaultOwner)
		# this error comes from transaction encoding
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Transaction parameter value too big', RunClient, host, ['pay', '--amount', 1*e(15), '--toAddress', payTargetAddress])
		# but this error comes from state check transaction
		self.assertRaisesRegexp(ExceptionReportedToUser, 'amount is below minimum balance', RunClient, host, ['pay', '--amount', -1*e(7), '--toAddress', payTargetAddress])

	def test_back_ltc_sells(self):
		host = InitHost()
		host._addUnspent(2*e(12))
		RunClient(host, ['burn', '--amount', 1*e(12)+Constraints.minimumSwapBillBalance])
		RunClient(host, ['back_ltc_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', 1000, '--blocksUntilExpiry', 20, '--commission_AsInteger', 0x10000000])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'total': Constraints.minimumSwapBillBalance, 'spendable': 0})
		output, result = RunClient(host, ['get_ltc_sell_backers'])
		self.assertListEqual(result, [('ltc sell backer index', 0, {'backing amount': 1*e(12), 'I am backer': True, 'expires on block': 22, 'maximum per transaction': 1*e(9)})])

