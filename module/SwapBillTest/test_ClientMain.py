from __future__ import print_function
import unittest, sys, shutil, os
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from os import path
from SwapBillTest.MockHost import MockHost
from SwapBill import ClientMain
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
	assert path.isdir(dataDirectory)
	ownerDir = path.join(dataDirectory, host._getOwner())
	if not path.exists(ownerDir):
		os.mkdir(ownerDir)
	fullArgs = ['--datadir', ownerDir] + args
	out = io.StringIO()
	result = ClientMain.Main(startBlockIndex=0, startBlockHash=host.getBlockHash(0), useTestNet=True, commandLineArgs=fullArgs, host=host, out=out)
	return out.getvalue(), result

#def RunClient(host, args):
	#if path.exists(dataDirectory):
		#assert path.isdir(dataDirectory)
		#shutil.rmtree(dataDirectory)
	#os.mkdir(dataDirectory)
	#return RunClient(host, args)

def GetStateInfo(host):
	output, info = RunClient(host, ['get_state_info'])
	#CheckEachBalanceHasUnspent(host, info['balances'])
	return info

class Test(unittest.TestCase):
	def assertBalancesEqual(self, host, expected):
		info = GetStateInfo(host)
		self.assertSetEqual(set(info['balances'].values()), set(expected))

	def test(self):
		host = InitHost()

		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '1000000'])

		host._addUnspent(100000000)

		RunClient(host, ['burn', '--quantity', '1000000'])

		#print('unspent after burn:')
		#print(host.getUnspent())

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 1000000})
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nStarting from block 0\n'))

		output = RunClient(host, ['burn', '--quantity', '2000000'])
		#print(output)

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 1000000, "03:1": 2000000})

		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)

		output = RunClient(host, ['pay', '--quantity', '1', '--toAddress', payTargetAddress])
		self.assertTrue(info['syncOutput'].startswith('Loaded cached state data successfully\nStarting from block 0\n'))

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 1000000, '04:2': 1, '04:1': 1999999})

		host._addUnspent(800000000)
		output = RunClient(host, ['burn', '--quantity', '400000000'])
		output = RunClient(host, ['burn', '--quantity', '100000000'])
		#print(output)

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 1000000, '04:2': 1, '04:1': 1999999, '06:1': 400000000, '07:1': 100000000})

		output = RunClient(host, ['post_ltc_buy', '--quantity', '400000000', '--exchangeRate', "0.5"])

		info = GetStateInfo(host)
		#print(info)
		self.assertEqual(info['balances'], {'02:1': 1000000, '04:2': 1, '04:1': 1999999, '07:1': 100000000, '08:2': 0})

		RunClient(host, ['post_ltc_sell', '--quantity', '200000000', '--exchangeRate', "0.5"])

		info = GetStateInfo(host)
		# deposit of 12500000 moved in to sell offer, 87500000 change
		self.assertEqual(info['balances'], {'02:1': 1000000, '04:2': 1, '04:1': 1999999, '09:1': 87500000, '08:2': 0, '09:2': 0})

		output = RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', "0"])

		info = GetStateInfo(host)
		# exchange completed successfully
		# deposit + swapcoin counterparty credited to ltc seller
		## TODO left over zero balance account should be cleaned up
		self.assertEqual(info['balances'], {'02:1': 1000000, '04:2': 1, '04:1': 1999999, '09:1': 87500000, '08:2': 0, '09:2': 212500000})

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
		#host._logConsumeUnspent = True
		RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', '0'])
		info = GetStateInfo(host)
		#print(host._unspent)
		# TODO - clean up that zero outstanding balance!
		self.assertEqual(info['balances'], {'04:2': 0, '04:1': 68125000, '03:2': 31875000})

	def test_burn_less_than_dust_limit(self):
		host = InitHost()
		host._addUnspent(500000000)
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Burn amount is below dust limit', RunClient, host, ['burn', '--quantity', '1000'])

	def test_simultaneous_collect_and_pay(self):
		# attempted to trigger potential issue with consume failing if one of the inputs is already spent,
		# but it turns out the host blockchain takes care of this for us
		host = InitHost()
		host._addUnspent(500000000)
		RunClient(host, ['burn', '--quantity', '1000000'])
		RunClient(host, ['burn', '--quantity', '2000000'])
		RunClient(host, ['burn', '--quantity', '3000000'])
		self.assertBalancesEqual(host, [1000000,2000000,3000000])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		output = RunClient(host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
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
		RunClient(host, ['burn', '--quantity', '1000000'])
		RunClient(host, ['burn', '--quantity', '2000000'])
		RunClient(host, ['burn', '--quantity', '3000000'])
		self.assertBalancesEqual(host, [1000000,2000000,3000000])
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		output = RunClient(host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		output = RunClient(host, ['collect'])
		host.holdNewTransactions = False
		output, result = RunClient(host, ['get_balance'])
		self.assertEqual(result['total'], 5999900)


	def test_burn_funding(self):
		host = InitHost()
		dustLimit = 100000
		transactionFee = 100000
		# burn requires burnAmount for control + 1 dust for dest + transactionFee
		# so burn of 1111111 will require 111111 + 100000 + 100000 = 311111
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '111111'])
		host._addUnspent(100000)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '111111'])
		host._addUnspent(100000)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '111111'])
		host._addUnspent(100000)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '111111'])
		host._addUnspent(11110)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '111111'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		host._addUnspent(1)
		RunClient(host, ['burn', '--quantity', '100000'])
		burnTarget = "06:1"
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {burnTarget:100000})

	def test_bad_invocations(self):
		host = InitHost()
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No pending exchange with the specified ID', RunClient, host, ['complete_ltc_sell', '--pending_exchange_id', '123'])
		self.assertRaisesRegexp(ExceptionReportedToUser, 'The following path [(]specified for data directory parameter[)] is not a valid path to an existing directory', RunClient, host, ['--datadir=dontMakeADirectoryCalledThis', 'get_balance'])

	def test_burn_and_pay(self):
		host = InitHost()

		nextTX = 1

		host._addUnspent(100000000)
		nextTX += 1

		RunClient(host, ['burn', '--quantity', '100000'])
		firstBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000})

		RunClient(host, ['burn', '--quantity', '150000'])
		secondBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000})

		host._addUnspent(600000)
		nextTX += 1

		RunClient(host, ['burn', '--quantity', '160000'])
		thirdBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000, thirdBurnTarget:160000})

		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)

		self.assertRaisesRegexp(ClientMain.BadAddressArgument, 'An address argument is not valid', RunClient, host, ['pay', '--quantity', '100', '--toAddress', 'madeUpAddress'])
		RunClient(host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
		payChange = "0" + str(nextTX) + ":1"
		payTarget = "0" + str(nextTX) + ":2"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000, payTarget:100, payChange:160000-100})
		host._setOwner('recipient')
		#self.assertEqual(host.formatAddressForEndUser(GetAddressForUnspent(host, payTarget)), payTargetAddress)
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 100, 'total': 100})
		host._setOwner(host.defaultOwner)

		# and this should not submit because there are not enough funds for the payment
		self.assertRaises(TransactionNotSuccessfulAgainstCurrentState, RunClient, host, ['pay', '--quantity', '160000', '--toAddress', payTargetAddress])

	def test_burn_and_collect(self):
		host = InitHost()
		nextTX = 1
		host._addUnspent(100000000)
		nextTX += 1
		RunClient(host, ['burn', '--quantity', '100000'])
		firstBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000})
		RunClient(host, ['burn', '--quantity', '150000'])
		secondBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000})
		host._addUnspent(600000)
		nextTX += 1
		RunClient(host, ['burn', '--quantity', '160000'])
		thirdBurnTarget = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000, thirdBurnTarget:160000})
		RunClient(host, ['collect'])
		collectOutput = "0" + str(nextTX) + ":1"
		nextTX += 1
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {collectOutput:410000})
		# and should not submit again because there is now only one owned output
		self.assertRaisesRegexp(ExceptionReportedToUser, 'There are currently less than two owned swapbill outputs.', RunClient, host, ['collect'])

	def test_non_swapbill_transactions(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '1000000'])
		# just some randon transaction taken off the litecoin testnet
		# so, inputs will not be valid for our fake blockchain, but we depend on that not being checked for the purpose of this test
		host.addTransaction("6bc0c859176a50540778c03b6c8f28268823a68cd1cd75d4afe2edbcf50ea8d1", "0100000001566b10778dc28b7cc82e43794bfb26c47ab54a85e1f8e9c8dc04f261024b108c000000006b483045022100aaf6244b7df18296917f430dbb9fa42e159eb79eb3bad8e15a0dfbe84830e08c02206ff81a4cf2cdcd7910c67c13a0694064aec91ae6897d7382dc1e9400b2193bb5012103475fb57d448091d9ca790af2d6d9aca798393199aa70471f38dc359f9f30b50cffffffff0264000000000000001976a914e512a5846125405e009b6f22ac274289f69e185588acb83e5c02000000001976a9147cc3f7daeffe2cfb39630310fad6d0a9fbb4b6aa88ac00000000")
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':1000000})

	def test_double_spend(self):
		host = InitHost()
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '1000000'])
		host.holdNewTransactions = True
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 1000000})
		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner(host.defaultOwner)
		RunClient(host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
		host.holdNewTransactions = True
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1': 1000000})
		self.assertRaisesRegexp(ExceptionReportedToUser, 'No active swapbill balance currently available', RunClient, host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
		host.holdNewTransactions = False
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'03:1': 999900, '03:2':100})
		# once the first pay transaction goes through, we can make another one
		RunClient(host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'04:1': 999800, '04:2':100, '03:2':100})

	def test_include_pending(self):
		host = InitHost()
		host._addUnspent(100000000)
		host.holdNewTransactions = True
		RunClient(host, ['burn', '--quantity', '1000000'])
		RunClient(host, ['burn', '--quantity', '2000000'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {})
		output, info = RunClient(host, ['--includepending', 'get_state_info'])
		self.assertEqual(info['balances'], {'02:1': 1000000, '03:1': 2000000})
		output, info = RunClient(host, ['-i', 'get_state_info'])
		self.assertEqual(info['balances'], {'02:1': 1000000, '03:1': 2000000})
		output, info = RunClient(host, ['get_state_info'])
		self.assertEqual(info['balances'], {})

	def test_two_owners(self):
		host = InitHost()
		host._setOwner('1')
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '1000000'])
		host._setOwner('2')
		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '2000000'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'02:1':1000000, '04:1':2000000})
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 2000000, 'total': 2000000})
		host._setOwner('1')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 1000000, 'total': 1000000})

	def test_ltc_trading(self):
		host = InitHost()

		ownerList = ('alice', 'bob', 'clive', 'dave')

		## initialise some account balances
		host._setOwner('alice')
		host._addUnspent(30200000)
		RunClient(host, ['burn', '--quantity', '30000000'])
		host._setOwner('bob')
		host._addUnspent(20200000)
		RunClient(host, ['burn', '--quantity', '20000000'])
		host._setOwner('clive')
		host._addUnspent(50200000)
		RunClient(host, ['burn', '--quantity', '50000000'])
		host._setOwner('dave')
		host._addUnspent(60300000) ## will have 100000 backing funds left over
		RunClient(host, ['burn', '--quantity', '60000000'])
		info = GetStateInfo(host)
		#print('dave unspent:')
		#print(host.getUnspent())
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		#print(ownerBalances)
		self.assertDictEqual(ownerBalances, {'bob': 20000000, 'clive': 50000000, 'alice': 30000000, 'dave': 60000000})

		backingAmounts = GetOwnerBackingAmounts(host, ownerList, info['balances'])
		self.assertDictEqual(backingAmounts, {'dave': 100000})

		## alice and bob both want to buy LTC
		## clive and dave both want to sell

		## alice makes buy offer

		host._setOwner('alice')
		host._addUnspent(100000000)
		RunClient(host, ['post_ltc_buy', '--quantity', '30000000', '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 20000000, 'clive': 50000000, 'dave': 60000000})

		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': True, 'swapbill offered': 30000000})])

		## bob makes better offer, but with smaller amount

		host._setOwner('bob')
		output, result = RunClient(host, ['get_buy_offers'])
		self.assertEqual(result, [('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': False, 'swapbill offered': 30000000})])

		host._addUnspent(100000000)
		RunClient(host, ['post_ltc_buy', '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 10000000, 'clive': 50000000, 'dave': 60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		output, result = RunClient(host, ['get_buy_offers'])
		expectedResult = [
		    ('exchange rate', 0.25, {'ltc equivalent': 2500000, 'mine': True, 'swapbill offered': 10000000}),
			('exchange rate', 0.5, {'ltc equivalent': 15000000, 'mine': False, 'swapbill offered': 30000000})
		]
		self.assertEqual(result, expectedResult)

		## clive makes a sell offer, matching bob's buy exactly

		host._setOwner('clive')
		host._addUnspent(100000000)
		RunClient(host, ['post_ltc_sell', '--quantity', '10000000', '--exchangeRate', '0.25'])
		cliveCompletionPaymentExpiry = host._nextBlock + 50 # note that RunClient posts the transaction, and then the transaction will go through in the next block
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 10000000, 'clive': 49375000, 'dave': 60000000})
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

		## dave and bob make overlapping offers that 'cross over'

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

		RunClient(host, ['post_ltc_buy', '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'clive': 49375000, 'dave': 60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		host._setOwner('dave')
		host._addUnspent(100000000)
		RunClient(host, ['post_ltc_sell', '--quantity', '20000000', '--exchangeRate', '0.26953125'])
		info = GetStateInfo(host)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'clive': 49375000, 'dave': 58750000})
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
		self.assertDictEqual(ownerBalances, {'clive': 49375000, 'dave': 58750000})
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
		self.assertDictEqual(ownerBalances, {'bob':10625000, 'clive': 49375000, 'dave': 58750000})

		#dave is more on the ball, and makes his completion payment
		host._setOwner('dave')
		RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', '1'])

		info = GetStateInfo(host)
		#dave gets credited bob's exchange funds, and is also refunded his exchange deposit
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob':10625000, 'clive': 49375000, 'dave': 58750000+10625000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		host._setOwner('alice')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 0, 'total': 0})
		host._setOwner('bob')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 10625000, 'total': 10625000})
		host._setOwner('clive')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 49375000, 'total': 49375000})
		host._setOwner('dave')
		output, info = RunClient(host, ['get_balance'])
		self.assertDictEqual(info, {'in active account': 58750000, 'total': 58750000+10625000})

