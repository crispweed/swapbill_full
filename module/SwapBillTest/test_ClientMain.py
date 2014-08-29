from __future__ import print_function
import unittest, sys, shutil, os, random, binascii
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from os import path
from SwapBill import ClientMain, Amounts, TransactionFee
from SwapBillTest.MockHost import MockHost
from SwapBillTest import hook_HostFromPrefsByProtocol
from SwapBill.Amounts import e
from SwapBill.BuildHostedTransaction import InsufficientFunds
from SwapBill.ClientMain import TransactionNotSuccessfulAgainstCurrentState
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser
from SwapBill.HardCodedProtocolConstraints import Constraints

def GetOwnerBalances(host, ownerList, balances):
	result = {}
	for owner in ownerList:
		output, info = RunClient(host, ['get_balance'], owner=owner)
		amount = Amounts.FromString(info['balance'])
		if amount != 0:
			result[owner] = amount
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
	return MockHost()

defaultOwner = '0'

def RunClient(host, args, hostBlockChain='litecoin', owner=None):
	if owner is None:
		owner = defaultOwner
	convertedArgs = []
	for arg in args:
		if type(arg) is not type(''):
			arg = Amounts.ToString(arg)
		convertedArgs.append(arg)
	assert path.isdir(dataDirectory)
	ownerDir = path.join(dataDirectory, owner)
	if not path.exists(ownerDir):
		os.mkdir(ownerDir)
	fullArgs = ['--dataDir', ownerDir, '--host', hostBlockChain] + convertedArgs
	out = io.StringIO()
	assert host.getBlockHashAtIndexOrNone(0) is not None
	hook_HostFromPrefsByProtocol.currentHostByProtocol[hostBlockChain] = host
	result = ClientMain.Main(overrideStartBlock=0, commandLineArgs=fullArgs, out=out)
	return out.getvalue(), result

def GetStateInfo(host, includePending=False, forceRescan=False, owner=None):
	if owner is None:
		owner = defaultOwner
	args = []
	if forceRescan:
		args.append('--forceRescan')
	args.append('get_state_info')
	if includePending:
		args.append('-i')
	output, info = RunClient(host, args, owner=owner)
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
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nState update starting from block 0\n'))
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"03:1": 35*e(6), '04:2': 1*e(7), '04:1': 1*e(7)})
		self.assertEqual(info['syncOutput'].count('in memory: Burn'), 2)
		self.assertEqual(info['syncOutput'].count('in memory: Pay'), 1)
		self.assertEqual(info['syncOutput'], 'Loaded cached state data successfully\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Burn\n - 0.2 swapbill output added\nin memory: Burn\n - 0.35 swapbill output added\nin memory: Pay\n - 0.2 swapbill output consumed\n - 0.1 swapbill output added\nIn memory state updated to end of block 3\n')
		info = GetStateInfo(host, owner='recipient')
		self.assertEqual(info['syncOutput'].count('in memory: Burn'), 0)
		self.assertEqual(info['syncOutput'].count('in memory: Pay'), 1)
		# ** following changed since change to call get_receive_address for payTargetAddress
		# and get_receive_address then currently does a sync
		self.assertEqual(info['syncOutput'], 'Loaded cached state data successfully\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Pay\n - 0.1 swapbill output added\nIn memory state updated to end of block 3\n')
		#self.assertEqual(info['syncOutput'], 'Failed to load from cache, full index generation required (no cache file found)\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Pay\n - 10000000 swapbill output added\nIn memory state updated to end of block 3\n')
		info = GetStateInfo(host, owner='someoneElse')
		self.assertEqual(info['syncOutput'].count('in memory: Burn'), 0)
		self.assertEqual(info['syncOutput'].count('in memory: Pay'), 0)
		self.assertEqual(info['syncOutput'], 'Failed to load from cache, full index generation required (no cache file found)\nState update starting from block 0\nCommitted state updated to start of block 0\nIn memory state updated to end of block 3\n')

	def test_bad_control_address_prefix(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', 2*e(7)])
		RunClient(host, ['burn', '--amount', 3*e(7)])
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		RunClient(host, ['burn', '--amount', 4*e(7)])
		RunClient(host, ['pay', '--amount', 2*e(7), '--toAddress', payTargetAddress])
		corruptedMemPool = []
		for txID, txData in host._memPool:
			txHex = binascii.hexlify(txData).decode('ascii')
			assert txHex.count('5342') == 1
			corruptedTXHex = txHex.replace('5342', '5343')
			corruptedTXData = binascii.unhexlify(corruptedTXHex.encode('ascii'))
			corruptedMemPool.append((txID, corruptedTXData))
		host._memPool = corruptedMemPool
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		# 'corrupted' transactions have bad control address, and should just be ignored
		self.assertEqual(info['syncOutput'], 'Loaded cached state data successfully\nState update starting from block 0\nCommitted state updated to start of block 0\nin memory: Burn\n - 0.2 swapbill output added\nin memory: Burn\n - 0.3 swapbill output added\nIn memory state updated to end of block 3\n')
		# add tests for other badly formed transactions?

	def test_start_block_not_reached(self):
		host = InitHost()
		ownerDir = path.join(dataDirectory, "0")
		if not path.exists(ownerDir):
			os.mkdir(ownerDir)
		args = ['--dataDir', ownerDir, 'get_balance']
		out = io.StringIO()
		hook_HostFromPrefsByProtocol.currentHostByProtocol['bitcoin'] = host
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Block chain has not reached the swapbill start block', ClientMain.Main, commandLineArgs=args, out=out)

	def test_minimum_balance(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Transaction does not meet protocol constraints: burn output is below minimum balance', RunClient, host, ['burn', '--amount', 1*e(7)-1])
		RunClient(host, ['burn', '--amount', 2*e(7)])
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Transaction does not meet protocol constraints: amount is below minimum balance', RunClient, host, ['pay', '--amount', 1*e(7)-1, '--toAddress', payTargetAddress])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Insufficient swapbill for transaction', RunClient, host, ['pay', '--amount', 1*e(7)+1, '--toAddress', payTargetAddress])
		# but can split exactly
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '0.1'})
		# or transfer full output amount
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '0'})

	def test_ltc_sell_missing_unspent_regression(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 1*e(8)])
		burnTarget = "02:1"
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {burnTarget:1*e(8)})
		RunClient(host, ['sell_offer', '--hostCoinOffered', 3*e(7)//2, '--exchangeRate', '0.5'])
		deposit = 3*e(7)//Constraints.depositDivisor
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'03:1': 1*e(8)-deposit-Constraints.minimumSwapBillBalance})
		RunClient(host, ['buy_offer', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'04:1': 1*e(8)-deposit-3*e(7)})
		RunClient(host, ['complete_sell', '--pendingExchangeID', '0'])
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 0)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		self.assertEqual(info['balances'], {'04:1': 1*e(8)})

	def test_refund_account_referenced_during_trade(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		owner = '1'
		RunClient(host, ['burn', '--amount', 1*e(8)], owner=owner)
		RunClient(host, ['sell_offer', '--hostCoinOffered', 3*e(7)//2, '--exchangeRate', '0.5', '--blocksUntilExpiry', '20'], owner=owner)
		deposit = 3*e(7) // 16
		output, result = RunClient(host, ['get_balance'], owner=owner)
		# receiving account is created, with minimumBalance, here
		self.assertDictEqual(result, {'balance': Amounts.ToString(1*e(8)-deposit-Constraints.minimumSwapBillBalance)})
		owner = '2'
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--amount', 2*e(8)], owner=owner)
		RunClient(host, ['buy_offer', '--swapBillOffered', 29900000, '--exchangeRate', '0.5'], owner=owner)
		# the offers can't match, because this would result in a remainder below minimum exchange
		output, result = RunClient(host, ['get_balance'], owner=owner)
		self.assertDictEqual(result, {'balance': '1.701'})
		owner = '1'
		output, result = RunClient(host, ['get_balance'], owner=owner)
		self.assertDictEqual(result, {'balance': Amounts.ToString(1*e(8)-deposit-Constraints.minimumSwapBillBalance)})
		# the refund account is referenced by the trade, but *can* now be spent
		owner = 'recipient'
		output, result = RunClient(host, ['get_receive_address'], owner=owner)
		payTargetAddress = result['receive_address']
		owner = '1'
		# change output (active account) can be spent
		RunClient(host, ['pay', '--amount', Amounts.ToString(1*e(8)-deposit-Constraints.minimumSwapBillBalance), '--toAddress', payTargetAddress], owner=owner)
		output, result = RunClient(host, ['get_balance'], owner=owner)
		self.assertDictEqual(result, {'balance': '0'})
		owner = 'recipient'
		output, result = RunClient(host, ['get_balance'], owner=owner)
		self.assertDictEqual(result, {'balance': Amounts.ToString((1*e(8)-deposit-Constraints.minimumSwapBillBalance))})
	def test_receiving_account_referenced_during_trade(self):
		host = InitHost()
		host._addUnspent(500000000)
		owner = '1'
		RunClient(host, ['burn', '--amount', 100000000], owner=owner)
		RunClient(host, ['sell_offer', '--hostCoinOffered', 29900000//2, '--exchangeRate', '0.5'], owner=owner)
		output, result = RunClient(host, ['get_balance'], owner=owner)
		# refund account is created, with minimumBalance, here
		self.assertDictEqual(result, {'balance': Amounts.ToString(98131250-Constraints.minimumSwapBillBalance)})
		host._addUnspent(500000000)
		owner = '2'
		RunClient(host, ['burn', '--amount', 200000000], owner=owner)
		RunClient(host, ['buy_offer', '--swapBillOffered', 30000000, '--exchangeRate', '0.5'], owner=owner)
		output, result = RunClient(host, ['get_balance'], owner=owner)
		# the offers can't match, because this would result in a remainder below minimum exchange
		self.assertDictEqual(result, {'balance': '1.7'})
		# the refund account is referenced by the trade, because it may need to be credited, depending on how the trade plays out
		# but *can* now be spent, nevertheless
		owner = 'recipient'
		output, result = RunClient(host, ['get_receive_address'], owner=owner)
		payTargetAddress = result['receive_address']
		owner = '2'
		RunClient(host, ['pay', '--amount', '1.7', '--toAddress', payTargetAddress], owner=owner)
		output, result = RunClient(host, ['get_balance'], owner=owner)
		self.assertDictEqual(result, {'balance': '0'})
		owner = 'recipient'
		output, result = RunClient(host, ['get_balance'], owner=owner)
		self.assertDictEqual(result, {'balance': '1.7'})

	def test_burn_less_than_dust_limit(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Burn amount is below dust limit', RunClient, host, ['burn', '--amount', 1000])

	def test_expired_pay(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 3*e(7)])
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		self.assertBalancesEqual(host, [3*e(7)])
		RunClient(host, ['pay', '--amount', 1*e(7), '--toAddress', payTargetAddress, '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True
		# two blocks advanced so far, one for burn, one for pay
		self.assertEqual(host._nextBlock, 2)
		# max block for the pay is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		# so this should be 6
		host._advance(4)
		self.assertEqual(host._nextBlock, 6)
		# so didn't expire yet, on block 6
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['balance'], '0.2')
		output, result = RunClient(host, ['get_balance', '-i'], owner='recipient')
		self.assertEqual(result['balance'], '0.1')
		host._advance(1)
		self.assertEqual(host._nextBlock, 7)
		# but expires on block 7
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['balance'], '0.3')
		output, result = RunClient(host, ['get_balance', '-i'], owner='recipient')
		self.assertEqual(result['balance'], '0')
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['balance'], '0.3')
		self.assertEqual(host._nextBlock, 8)
	def test_expired_ltc_buy(self):
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--amount', 4*e(7)])
		RunClient(host, ['buy_offer', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.5', '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True
		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15*e(6)), 'mine': True, 'swapbill offered': Amounts.ToString(3*e(7))})])
		# two blocks advanced so far, one for burn, one for sell offer
		host._advance(4)
		self.assertEqual(host._nextBlock, 6)
		# max block for the pay is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		# so this should be 6
		# so didn't expire yet, on block 6
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['balance'], Amounts.ToString(1*e(7)))
		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15*e(6)), 'mine': True, 'swapbill offered': Amounts.ToString(3*e(7))})])
		host._advance(1)
		self.assertEqual(host._nextBlock, 7)
		# but expires on block 7
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['balance'], Amounts.ToString(4*e(7)))
		output, result = RunClient(host, ['get_buy_offers', '-i'])
		self.assertEqual(result, [])
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['balance'], Amounts.ToString(4*e(7)))
		self.assertEqual(host._nextBlock, 8)
		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [])
	def test_expired_ltc_sell(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 3*e(7)])
		RunClient(host, ['sell_offer', '--hostCoinOffered', 3*e(7)//2, '--exchangeRate', '0.5', '--blocksUntilExpiry', '4'])
		host.holdNewTransactions = True
		# two blocks advanced so far, one for burn, one for sell offer
		host._advance(4)
		self.assertEqual(host._nextBlock, 6)
		# max block for the pay is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		# so this should be 6
		# so didn't expire yet, on block 6
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['balance'], '0.18125')
		output, result = RunClient(host, ['get_sell_offers', '-i'])
		self.assertEqual(result, [('exchange rate', '0.5', {'host coin offered': Amounts.ToString(15*e(6)), 'mine': True, 'swapbill equivalent': Amounts.ToString(3*e(7)), 'deposit': Amounts.ToString(1875000)})])
		host._advance(1)
		self.assertEqual(host._nextBlock, 7)
		# but expires on block 7
		output, result = RunClient(host, ['get_balance', '-i'])
		self.assertEqual(result['balance'], '0.3')
		output, result = RunClient(host, ['get_sell_offers', '-i'])
		self.assertEqual(result, [])
		# still on block 7
		# (transaction was added from mem pool in the above)
		self.assertEqual(host._nextBlock, 7)
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['balance'], '0.3')
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
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No pending exchange with the specified ID', RunClient, host, ['complete_sell', '--pendingExchangeID', '123'])
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
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		self.assertRaisesRegexp(ClientMain.BadAddressArgument, 'An address argument is not valid', RunClient, host, ['pay', '--amount', 12*e(6), '--toAddress', 'madeUpAddress'])
		RunClient(host, ['pay', '--amount', 12*e(6), '--toAddress', payTargetAddress])
		payChange = "0" + str(nextTX) + ":1"
		payTarget = "0" + str(nextTX) + ":2"
		nextTX += 1
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'balance': Amounts.ToString(39*e(6))})
		output, info = RunClient(host, ['get_balance'], owner='recipient')
		self.assertDictEqual(info, {'balance': Amounts.ToString(12*e(6))})
		info = GetStateInfo(host, owner='recipient')
		self.assertEqual(info['balances'], {thirdBurnTarget:26*e(6), payTarget:12*e(6), payChange:13*e(6)})
		# and this should now work, now we can use more than one input per transaction
		RunClient(host, ['pay', '--amount', 16*e(6), '--toAddress', payTargetAddress])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'balance': Amounts.ToString(23*e(6))})
		output, info = RunClient(host, ['get_balance'], owner='recipient')
		self.assertDictEqual(info, {'balance': Amounts.ToString(28*e(6))})

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
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		RunClient(host, ['pay', '--amount', 41*e(6), '--toAddress', payTargetAddress])
		payChange = "0" + str(nextTX) + ":1"
		payTarget = "0" + str(nextTX) + ":2"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {payTarget:41*e(6)})

	def test_non_swapbill_transactions(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--amount', 10000000])
		# just some randon transaction taken off the litecoin testnet
		# (txid 6bc0c859176a50540778c03b6c8f28268823a68cd1cd75d4afe2edbcf50ea8d1)
		# so, inputs will not be valid for our fake blockchain, but we depend on that not being checked for the purpose of this test
		host._addThirdPartyTransaction("0100000001566b10778dc28b7cc82e43794bfb26c47ab54a85e1f8e9c8dc04f261024b108c000000006b483045022100aaf6244b7df18296917f430dbb9fa42e159eb79eb3bad8e15a0dfbe84830e08c02206ff81a4cf2cdcd7910c67c13a0694064aec91ae6897d7382dc1e9400b2193bb5012103475fb57d448091d9ca790af2d6d9aca798393199aa70471f38dc359f9f30b50cffffffff0264000000000000001976a914e512a5846125405e009b6f22ac274289f69e185588acb83e5c02000000001976a9147cc3f7daeffe2cfb39630310fad6d0a9fbb4b6aa88ac00000000")
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
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
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
		RunClient(host, ['burn', '--amount', 10000000])
		RunClient(host, ['burn', '--amount', 20000000])
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
		host._addUnspent(1*e(8))
		RunClient(host, ['burn', '--amount', 1*e(7)], owner='1')
		host._addUnspent(1*e(8))
		RunClient(host, ['burn', '--amount', 2*e(7)], owner='2')
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':10000000, '04:1':20000000})
		output, info = RunClient(host, ['get_balance'], owner='2')
		self.assertDictEqual(info, {'balance': '0.2'})
		output, info = RunClient(host, ['get_balance'], owner='1')
		self.assertDictEqual(info, {'balance': '0.1'})

	def test_expected_dust_and_fees(self):
		host = InitHost()
		ownerList = ('alice', 'bob', 'clive', 'dave')
		expectedDustAndFees = 200000
		host._addUnspent(3*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--amount', 3*e(7)], owner='alice')
		host._addUnspent(2*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--amount', 2*e(7)], owner='bob')
		host._addUnspent(5*e(7) + expectedDustAndFees)
		RunClient(host, ['burn', '--amount', 5*e(7)], owner='clive')
		host._addUnspent(6*e(7) + expectedDustAndFees + 100000) ## will have 100000 backing funds left over
		RunClient(host, ['burn', '--amount', 6*e(7)], owner='dave')
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 2*e(7), 'clive': 5*e(7), 'alice': 3*e(7), 'dave': 6*e(7)})
		backingAmount = GetBackingAmount(host, info['balances'])
		self.assertEqual(backingAmount, 100000)

	def test_ltc_trading(self):
		host = InitHost()
		ownerList = ('alice', 'bob', 'clive', 'dave')
		for owner in ownerList:
			host._addUnspent(2*e(8))
		# initialise some account balances
		RunClient(host, ['burn', '--amount', 4*e(7)], owner='alice')
		RunClient(host, ['burn', '--amount', 3*e(7)], owner='bob')
		RunClient(host, ['burn', '--amount', 6*e(7)], owner='clive')
		RunClient(host, ['burn', '--amount', 7*e(7)], owner='dave')
		# alice and bob both want to buy LTC
		# clive and dave both want to sell
		# alice makes buy offer
		RunClient(host, ['buy_offer', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.5', '--blocksUntilExpiry', '100'], owner='alice')
		info = GetStateInfo(host, owner='alice')
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 3*e(7), 'clive': 6*e(7), 'dave': 7*e(7)})
		output, result = RunClient(host, ['get_buy_offers'], owner='alice')
		self.assertEqual(result, [('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15000000), 'mine': True, 'swapbill offered': Amounts.ToString(30000000)})])
		# bob makes better offer, but with smaller amount
		output, result = RunClient(host, ['get_buy_offers'], owner='bob')
		self.assertEqual(result, [('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15000000), 'mine': False, 'swapbill offered': Amounts.ToString(30000000)})])
		RunClient(host, ['buy_offer', '--swapBillOffered', 1*e(7), '--exchangeRate', '0.25'], owner='bob')
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 6*e(7), 'dave': 7*e(7)})
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 2)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		output, result = RunClient(host, ['get_buy_offers'], owner='bob')
		expectedResult = [
			('exchange rate', '0.25', {'host coin equivalent': Amounts.ToString(2500000), 'mine': True, 'swapbill offered': Amounts.ToString(10000000)}),
			('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15000000), 'mine': False, 'swapbill offered': Amounts.ToString(30000000)})
		]
		self.assertEqual(result, expectedResult)
		# clive makes a sell offer, matching bob's buy exactly
		host._addUnspent(100000000)
		RunClient(host, ['sell_offer', '--hostCoinOffered', 10000000//4, '--exchangeRate', '0.25'], owner='clive')
		cliveCompletionPaymentExpiry = host._nextBlock + 50 # note that RunClient posts the transaction, and then the transaction will go through in the next block
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7), 'clive': 6*e(7)-625000, 'dave': 7*e(7)})
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		output, result = RunClient(host, ['get_sell_offers'], owner='clive')
		self.assertEqual(result, []) # (got matched immediately)
		output, result = RunClient(host, ['get_pending_exchanges'], owner='clive')
		expectedResult = [
			('pending exchange index', 0, {
				'I am seller (and need to complete)': True,
				'outstanding host coin payment amount': Amounts.ToString(2500000),
				'swap bill paid by buyer': Amounts.ToString(10000000),
				'expires on block': 57,
		        'blocks until expiry': 50,
				'I am buyer (and waiting for payment)': False,
				'deposit paid by seller': Amounts.ToString(625000)
			})]
		self.assertEqual(result, expectedResult)
		# dave and bob make overlapping offers that 'cross over'
		output, result = RunClient(host, ['get_pending_exchanges'], owner='bob')
		# (as above, but identifies bob as buyer instead of seller)
		expectedResult = [
			('pending exchange index', 0, {
				'I am seller (and need to complete)': False,
				'outstanding host coin payment amount': Amounts.ToString(2500000),
				'swap bill paid by buyer': Amounts.ToString(10000000),
				'expires on block': 57,
		        'blocks until expiry': 50,
				'I am buyer (and waiting for payment)': True,
				'deposit paid by seller': Amounts.ToString(625000)
			})]
		self.assertEqual(result, expectedResult)
		# we now need enough to fund the offer with minimum balance in refund account
		# (which should now be possible without any new burns)
		RunClient(host, ['buy_offer', '--swapBillOffered', 1*e(7), '--exchangeRate', '0.25'], owner='bob')
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 5*e(7)-625000+1*e(7), 'dave': 7*e(7)})
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 2)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		exchangeRate = 269531250
		RunClient(host, ['sell_offer', '--hostCoinOffered', 2*e(7) * exchangeRate // Amounts.percentDivisor, '--exchangeRate', Amounts.PercentToString(exchangeRate), '--blocksUntilExpiry', '100'], owner='dave')
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 5*e(7)-625000+1*e(7), 'dave': 7*e(7)-1250000-Constraints.minimumSwapBillBalance})
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		output, result = RunClient(host, ['get_buy_offers'])
		expectedResult = [('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15000000), 'mine': False, 'swapbill offered': Amounts.ToString(30000000)})]
		self.assertEqual(result, expectedResult)
		output, result = RunClient(host, ['get_sell_offers'], owner='dave')
		# didn't check the exact calculations for this value, but seems about right
		# note that dave now *gets more swapbill*, in the case of overlapping offers, instead of *spending less litecoin*
		daveSwapBillReceived = 11125000
		daveDepositRemainder = 647645
		daveDepositMatched = 1250000 - daveDepositRemainder
		expectedResult = [('exchange rate', '0.26953125', {'deposit': Amounts.ToString(daveDepositRemainder), 'host coin offered': Amounts.ToString(2792969), 'mine': True, 'swapbill equivalent': Amounts.ToString(10362320)})]
		self.assertEqual(result, expectedResult)
		assert cliveCompletionPaymentExpiry > host._nextBlock
		host._advance(cliveCompletionPaymentExpiry - host._nextBlock)
		# GetStateInfo will advance to the expiry block
		# but the exchange doesn't expire until the end of that block
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 1*e(7), 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000-Constraints.minimumSwapBillBalance})
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		host._advance(1)
		# clive failed to make his payment within the required block clount!
		# the pending exchange expires
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 1)
		# bob is credited his offer amount (which was locked up for the exchange) + clive's deposit
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7)+625000, 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000-Constraints.minimumSwapBillBalance})
		# dave is more on the ball, and makes his completion payment
		RunClient(host, ['complete_sell', '--pendingExchangeID', '1'], owner='dave')
		info = GetStateInfo(host)
		# dave gets credited bob's exchange funds, and is also refunded the matched part of his exchange deposit
		# but seeded amount locked up in sell offer is not refunded, because part of this sell offer is still outstanding
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'alice': 1*e(7), 'bob': 2*e(7)+625000, 'clive': 6*e(7)-625000, 'dave': 7*e(7)-1250000-Constraints.minimumSwapBillBalance+1*e(7)+daveDepositMatched})
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		info = GetStateInfo(host, includePending=False, forceRescan=True, owner='alice')
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCBuyOffer'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 0)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 0)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 0)
		info = GetStateInfo(host, includePending=False, forceRescan=True, owner='bob')
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCBuyOffer'), 2)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 2)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 1)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 1)
		info = GetStateInfo(host, includePending=False, forceRescan=True, owner='clive')
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 0)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 1)
		info = GetStateInfo(host, includePending=False, forceRescan=True, owner='dave')
		self.assertEqual(info['syncOutput'].count(': Burn'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCSellOffer'), 1)
		self.assertEqual(info['syncOutput'].count(': LTCExchangeCompletion'), 1)
		self.assertEqual(info['syncOutput'].count(': Pay'), 0)
		self.assertEqual(info['syncOutput'].count('trade offer or pending exchange expired'), 0)

	def test_burn_and_pay_parameter_ranges(self):
		# following requires a long in python 2.7
		host = InitHost()
		host._addUnspent(2*e(19))
		RunClient(host, ['burn', '--amount', 1*e(19)])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'balance': Amounts.ToString(1*e(19))})
		# greater than 8 bytes
		host = InitHost()
		host._addUnspent(2*e(20))
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Control address output amount exceeds supported range.', RunClient, host, ['burn', '--amount', 1*e(20)])
		host = InitHost()
		host._addUnspent(2*e(15))
		self.assertRaisesRegexp(ExceptionReportedToUser, 'negative values are not permitted', RunClient, host, ['burn', '--amount', '-10000000'])
		self.assertRaisesRegexp(ValueError, 'invalid literal', RunClient, host, ['burn', '--amount', 'lots'])
		# can burn amounts above 6 byte range, because this is a litecoin output amount, not encoded in control address
		RunClient(host, ['burn', '--amount', 1*e(15)])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'balance': Amounts.ToString(1*e(15))})
		# but amounts for pay transaction (for example) *are* restricted
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Transaction parameter value exceeds supported range.', RunClient, host, ['pay', '--amount', 1*e(15), '--toAddress', payTargetAddress])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'negative values are not permitted', RunClient, host, ['pay', '--amount', -1*e(7), '--toAddress', payTargetAddress])

	def test_ltc_sells_backer_expiry(self):
		host = InitHost()
		host._addUnspent(2*e(12))
		RunClient(host, ['burn', '--amount', 1*e(12)])
		RunClient(host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '0.625'])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'balance': '0'})
		self.assertEqual(host._nextBlock, 3)
		# expiry block is calculated as state._currentBlockIndex (which equals next block after end of synch at time of submit) + blocksUntilExpiry
		output, result = RunClient(host, ['get_sell_backers'])
		expectedDetails = {
		'commission': '0.625',
		'backing amount': Amounts.ToString(1*e(12)), 'I am backer': True,
		'expires on block': 22,
		'blocks until expiry': 20,
		'maximum per transaction': Amounts.ToString(1*e(9))
		}
		self.assertListEqual(result, [('host coin sell backer index', 0, expectedDetails)])
		self.assertEqual(host._nextBlock, 3)
		host._advance(19)
		output, result = RunClient(host, ['get_sell_backers'])
		expectedDetails['blocks until expiry'] = 1
		self.assertListEqual(result, [('host coin sell backer index', 0, expectedDetails)])
		self.assertEqual(host._nextBlock, 22)
		host._advance(1)
		self.assertEqual(host._nextBlock, 23)
		output, result = RunClient(host, ['get_sell_backers'])
		self.assertListEqual(result, [])

	def test_backed_ltc_sell(self):
		host = InitHost()
		ownerList = ('backer', 'buyer', 'seller')
		host._addUnspent(2*e(12))
		RunClient(host, ['burn', '--amount', 1*e(12)], owner='backer')
		RunClient(host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '0.0625'], owner='backer')
		output, info = RunClient(host, ['get_balance'], owner='backer')
		self.assertDictEqual(info, {'balance': '0'})
		self.assertEqual(host._nextBlock, 3)
		output, result = RunClient(host, ['get_sell_backers'], owner='backer')
		expectedBackingAmount = 1*e(12)
		expectedBackerDetails = {
		'commission': '0.0625',
		'backing amount': Amounts.ToString(expectedBackingAmount), 'I am backer': True,
		'expires on block': 22,
		'blocks until expiry': 20,
		'maximum per transaction': Amounts.ToString(1*e(9))
		}
		self.assertListEqual(result, [('host coin sell backer index', 0, expectedBackerDetails)])
		RunClient(host, ['burn', '--amount', 3*e(8)], owner='buyer')
		RunClient(host, ['buy_offer', '--swapBillOffered', 3*e(8), '--exchangeRate', '0.5', '--blocksUntilExpiry', '100'], owner='buyer')
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 1)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {})
		output, result = RunClient(host, ['get_buy_offers'], owner='buyer')
		self.assertEqual(result, [('exchange rate', '0.5', {'host coin equivalent': Amounts.ToString(15*e(7)), 'mine': True, 'swapbill offered': Amounts.ToString(3*e(8))})])
		ltcOffered = 15*e(7)
		commission = ltcOffered // 16
		RunClient(host, ['sell_offer', '--hostCoinOffered', ltcOffered+commission, '--exchangeRate', '0.5', '--backerID', 0, '--includesCommission'], owner='seller')
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'seller': 3*e(8)})
		# deposit taken from backer object
		# seller paid directly from backer object
		# minimum balance seeded into sell offer is refunded back to backer object directly
		deposit = 3*e(8)//Constraints.depositDivisor
		expectedBackingAmount -= deposit
		expectedBackingAmount -= 3*e(8)
		expectedBackerDetails['backing amount'] = Amounts.ToString(expectedBackingAmount)
		expectedBackerDetails['blocks until expiry'] = 17
		output, result = RunClient(host, ['get_sell_backers'], owner='backer')
		self.assertListEqual(result, [('host coin sell backer index', 0, expectedBackerDetails)])
		output, result = RunClient(host, ['get_pending_exchanges'], owner='backer')
		expectedResult = [('pending exchange index', 0,
		     {
		         'expires on block': 55,
		         'blocks until expiry': 50,
		         'outstanding host coin payment amount': Amounts.ToString(150000000),
		         'I am seller (and need to complete)': True,
		         'backer id': 0,
		         'I am buyer (and waiting for payment)': False,
		         'swap bill paid by buyer': Amounts.ToString(300000000),
		         'deposit paid by seller': Amounts.ToString(18750000)
		     }
		)]
		self.assertEqual(result, expectedResult)

	def test_backed_ltc_sell_add_commission(self):
		host = InitHost()
		host._addUnspent(2*e(12))
		RunClient(host, ['burn', '--amount', 1*e(12)], owner='backer')
		RunClient(host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '0.0625'], owner='backer')
		ltcOffered = 15*e(7)
		commission = ltcOffered // 16
		RunClient(host, ['sell_offer', '--hostCoinOffered', ltcOffered, '--exchangeRate', '0.5', '--backerID', 0], owner='seller')
		output, result = RunClient(host, ['get_sell_offers'], owner='seller')
		self.assertEqual(result, [('exchange rate', '0.5', {'backer id':0, 'host coin offered': Amounts.ToString(ltcOffered), 'mine': False, 'swapbill equivalent': Amounts.ToString(ltcOffered*2), 'deposit': Amounts.ToString(ltcOffered*2//Constraints.depositDivisor)})])

	def test_bad_commission(self):
		host = InitHost()
		host._addUnspent(5*e(12))
		RunClient(host, ['burn', '--amount', 1*e(12) + Constraints.minimumSwapBillBalance])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad decimal string [(]negative values are not permitted[)]', RunClient, host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '-0.1'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '1.0'])
		# zero commission not permitted
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '0'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '0.0'])
		RunClient(host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '1000', '--blocksUntilExpiry', '20', '--commission', '0.1'])
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'balance': Amounts.ToString(Constraints.minimumSwapBillBalance)})
		output, result = RunClient(host, ['get_sell_backers'])
		expectedDetails = {
		'commission': "0.1",
		'backing amount': 1*e(12), 'I am backer': True, 'expires on block': 22, 'maximum per transaction': 1*e(9)
		}

	def test_bad_exchange_rate(self):
		host = InitHost()
		host._addUnspent(5*e(8))
		RunClient(host, ['burn', '--amount', 1*e(8)])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['sell_offer', '--hostCoinOffered', 3*e(7)//2, '--exchangeRate', '0.0'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad decimal string [(]negative values are not permitted[)]', RunClient, host, ['sell_offer', '--hostCoinOffered', 3*e(7)//2, '--exchangeRate', '-0.5'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['sell_offer', '--hostCoinOffered', 3*e(7)//2, '--exchangeRate', '1.0'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['buy_offer', '--swapBillOffered', 3*e(7), '--exchangeRate', '0.0'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad decimal string [(]negative values are not permitted[)]', RunClient, host, ['buy_offer', '--swapBillOffered', 3*e(7), '--exchangeRate', '-0.5'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', RunClient, host, ['buy_offer', '--swapBillOffered', 3*e(7), '--exchangeRate', '1.0'])

	def test_backed_sell_matches_multiple(self):
		host = InitHost()
		ownerList = ['buyer', 'seller', 'backer']
		host._addUnspent(5*e(12))
		RunClient(host, ['burn', '--amount', 6*e(9)], owner='buyer')
		RunClient(host, ['buy_offer', '--swapBillOffered', 2*e(9), '--exchangeRate', '0.5', '--blocksUntilExpiry', '100'], owner='buyer')
		RunClient(host, ['buy_offer', '--swapBillOffered', 4*e(9), '--exchangeRate', '0.5', '--blocksUntilExpiry', '100'], owner='buyer')
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 2)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertEqual(ownerBalances, {})
		RunClient(host, ['burn', '--amount', 1*e(12)], owner='backer')
		RunClient(host, ['back_sells', '--backingSwapBill', 1*e(12), '--transactionsBacked', '10', '--blocksUntilExpiry', '100', '--commission', '0.1'], owner='backer')
		ltcOffered = 6*e(9)//2
		deposit = 6*e(9)//Constraints.depositDivisor
		ltcCommission = ltcOffered // 10
		RunClient(host, ['sell_offer', '--hostCoinOffered', ltcOffered + ltcCommission, '--exchangeRate', '0.5', '--backerID', 0, '--includesCommission'], owner='seller')
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfHostCoinBuyOffers'], 0)
		self.assertEqual(info['numberOfHostCoinSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		# the backer gets a trade count incremented twice here, which triggered an incorrect assert
		output, result = RunClient(host, ['get_balance'], owner='backer')
		self.assertDictEqual(result, {'balance': '0'})
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertEqual(ownerBalances, {'seller':6*e(9)})
		expectedBackerDetails = {'commission': '0.1', 'blocks until expiry': 99, 'I am backer': True, 'backing amount': Amounts.ToString(1*e(12)-6*e(9)-deposit), 'expires on block': 105, 'maximum per transaction': Amounts.ToString(1*e(11))}
		output, result = RunClient(host, ['get_sell_backers'], owner='backer')
		self.assertListEqual(result, [('host coin sell backer index', 0, expectedBackerDetails)])
		RunClient(host, ['complete_sell', '--pendingExchangeID', '0'], owner='backer')
		RunClient(host, ['complete_sell', '--pendingExchangeID', '1'], owner='backer')
		output, result = RunClient(host, ['get_balance'], owner='backer')
		self.assertDictEqual(result, {'balance': '0'})
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertEqual(ownerBalances, {'seller':6*e(9)})
		expectedBackerDetails['backing amount'] = Amounts.ToString(Amounts.FromString(expectedBackerDetails['backing amount']) + 6*e(9)+deposit)
		expectedBackerDetails['blocks until expiry'] -= 2
		output, result = RunClient(host, ['get_sell_backers'], owner='backer')
		self.assertListEqual(result, [('host coin sell backer index', 0, expectedBackerDetails)])

	def test_10_unspent(self):
		host = InitHost()
		for i in range(10):
			host._addUnspent(1*e(6))
		host._addUnspent(TransactionFee.dustLimit * 2)
		RunClient(host, ['burn', '--amount', 1*e(7)])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '0.1'})

	def test_100_unspent(self):
		host = InitHost()
		for i in range(100):
			host._addUnspent(1*e(6))
		host._addUnspent(TransactionFee.dustLimit * 10)
		RunClient(host, ['burn', '--amount', 1*e(8)])
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '1'})

	#def test_1000_unspent(self):
		#host = InitHost()
		#for i in range(1000):
			#host._addUnspent(1*e(6))
		#host._addUnspent(TransactionFee.dustLimit * 100) # very large transaction!
		#RunClient(host, ['burn', '--amount', 1*e(9)])
		#output, result = RunClient(host, ['get_balance'])
		#self.assertDictEqual(result, {'balance': '10'})

	def test_first_output_unexpected_script(self):
		# regression for issue which broke v0.3 client synch
		# litecoin testnet txid 1773e169b5464bb5ddece1dc5624ab14191cf800daf13f348c0deb2837965c21
		# first output script type is not the swapbill 'standard' script type
		# and sync was incorrectly applying the test for this after the transaction decode call
		txHex = '01000000019bcc5e2f3545cb2311c322c37d0f9d76151152e5f9ec619bdd3ffa2d41fe6af5000000006a4730440220565c33fd0f4767c1b182fee131d015f0b0add681e7a2301ba25108734ae5299c02205c829ce88cabd3621b0186bab4b06136eb9136fb20d86ec7845c375f26f5c80c0121036b564092d5fee4c2a3935eddc7ebf09d34ccd81d9bccadbef65990c7305dea8effffffff02c00e16020000000017a914f134925c0e2ae1ae9621f0141b6dd0424d83c99187ce6dec21000000001976a914a3934b987fb4d7a310747e977863762429cea09588ac00000000'
		host = InitHost()
		host._addThirdPartyTransaction(txHex)
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '0'})

	def test_pay_on_proof_of_receipt(self):
		host = InitHost()
		host._addUnspent(11*e(7))
		RunClient(host, ['burn', '--amount', 1*e(8)])
		output, result = RunClient(host, ['get_receive_address'], owner='recipient')
		payTargetAddress = result['receive_address']

		# valid invocation, which should go through correctly
		RunClient(host, ['pay', '--amount', 1*e(8), '--toAddress', payTargetAddress, '--onRevealSecret'])

		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '0'})
		output, result = RunClient(host, ['get_pending_payments'])
		expectedResult = [
		    ('pending payment index', 0,
		     {'paid by me': True, 'expires on block': '10', 'amount': '1', 'paid to me': False})
		]
		self.assertEqual(result, expectedResult)

		# bad provide secret invocations
		self.assertRaisesRegexp(ExceptionReportedToUser, "The secret for this pending payment is not known", RunClient, host, ['reveal_secret_for_pending_payment', '--pendingPaymentID', 0], owner='someoneElse')
		self.assertRaisesRegexp(ExceptionReportedToUser, "No pending payment with the specified ID", RunClient, host, ['reveal_secret_for_pending_payment', '--pendingPaymentID', '1'])

		self.assertEqual(result, expectedResult)

		# valid invocation that should complete the payment
		RunClient(host, ['reveal_secret_for_pending_payment', '--pendingPaymentID', '0'])

		# recipient gets paid directly
		output, result = RunClient(host, ['get_balance'])
		self.assertDictEqual(result, {'balance': '0'})
		output, result = RunClient(host, ['get_balance'], owner='recipient')
		self.assertDictEqual(result, {'balance': '1'})
		output, result = RunClient(host, ['get_pending_payments'])
		self.assertEqual(result, [])
