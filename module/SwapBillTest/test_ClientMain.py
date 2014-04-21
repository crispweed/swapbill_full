from __future__ import print_function
import unittest, sys, os, json
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from SwapBillTest.MockHost import MockHost
from SwapBill import ClientMain
from SwapBill.BuildHostedTransaction import InsufficientFunds
from SwapBill.ClientMain import TransactionNotSuccessfulAgainstCurrentState

cacheFile = 'test.cache'

def RunClient(host, args):
	fullArgs = ['--cache-file', cacheFile] + args
	out = io.StringIO()
	ClientMain.Main(startBlockIndex=0, startBlockHash=host.getBlockHash(0), commandLineArgs=fullArgs, host=host, out=out)
	return out.getvalue()

def GetStateInfo(host):
	output = RunClient(host, ['print_state_info_json'])
	return json.loads(output)

class Test(unittest.TestCase):
	def test(self):
		host = MockHost()

		if os.path.exists(cacheFile):
			os.remove(cacheFile)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '1000000'])
		self.assertTrue(os.path.exists(cacheFile))

		host._addUnspent(100000000)

		RunClient(host, ['burn', '--quantity', '1000000'])

		info = GetStateInfo(host)
		## TODO - would be nicer if the client reused address "swapbill2", from the first burn
		self.assertEqual(info['balances'], {"swapbill2": 1000000})

		output = RunClient(host, ['burn', '--quantity', '2000000'])
		#print(output)

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill2": 1000000, "swapbill3": 2000000})

		output = RunClient(host, ['pay', '--fromAddress', "swapbill3", '--changeAddress', "swapbill3", '--quantity', '1', '--toAddress', "swapbill2"])

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill2": 1000001, "swapbill3": 1999999})

		host._addUnspent(800000000)
		output = RunClient(host, ['burn', '--quantity', '400000000'])
		output = RunClient(host, ['burn', '--quantity', '100000000'])
		#print(output)

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill2": 1000001, "swapbill3": 1999999, "swapbill4": 400000000, "swapbill5": 100000000})

		output = RunClient(host, ['post_ltc_buy', '--fromAddress', "swapbill4", '--quantity', '400000000', '--exchangeRate', "0.5"])

		info = GetStateInfo(host)
		#print(info)
		self.assertEqual(info['balances'], {"swapbill2": 1000001, "swapbill3": 1999999, "swapbill5": 100000000}) # swapbill4 entire balance moved in to buy offer

		output = RunClient(host, ['post_ltc_sell', '--fromAddress', "swapbill5", '--quantity', '200000000', '--exchangeRate', "0.5"])

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill2": 1000001, "swapbill3": 1999999, "swapbill5": 87500000}) # deposit of 12500000 moved in to sell offer

		output = RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', "0"])
		#print('complete:')
		#print(output)
		#print('end complete')

		info = GetStateInfo(host)
		#print('get info:')
		#print(output)
		#print('end get info')
		self.assertEqual(info['balances'], {"swapbill2": 1000001, "swapbill3": 1999999, "swapbill5": 300000000}) # swapbill5 gets deposit returned plus payment for ltc

	def test_pay(self):
		host = MockHost()
		if os.path.exists(cacheFile):
			os.remove(cacheFile)

		host._addUnspent(100000000)
		RunClient(host, ['burn', '--quantity', '1000000'])
		RunClient(host, ['burn', '--quantity', '2000000'])
		RunClient(host, ['burn', '--quantity', '3000000'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill1": 1000000, "swapbill2": 2000000, "swapbill3": 3000000})

		output = RunClient(host, ['pay', '--fromAddress', 'swapbill1', '--quantity', '1', '--toAddress', 'swapbill2', '--changeAddress', 'swapbill3'])
		#print(output)
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill2": 2000001, "swapbill3": 3999999})

	def test_burn_and_pay(self):
		host = MockHost()
		if os.path.exists(cacheFile):
			os.remove(cacheFile)

		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '100000'])
		host._addUnspent(100000)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '100000'])

		host._addUnspent(200000)
		host._addUnspent(300000)
		RunClient(host, ['burn', '--quantity', '100000'])
		info = GetStateInfo(host)
		firstBurnTarget = "swapbill3" ## couple of addresses got 'wasted'
		self.assertEqual(info['balances'], {firstBurnTarget: 100000})

		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '600000'])

		RunClient(host, ['burn', '--quantity', '150000'])

		info = GetStateInfo(host)		
		secondBurnTarget = "swapbill5"
		self.assertEqual(info['balances'], {firstBurnTarget: 100000, secondBurnTarget:150000})
		
		host._addUnspent(600000)

		RunClient(host, ['burn', '--quantity', '150000'])

		info = GetStateInfo(host)		
		thirdBurnTarget = "swapbill6"
		self.assertEqual(info['balances'], {firstBurnTarget: 100000, secondBurnTarget:150000, thirdBurnTarget:150000})

		RunClient(host, ['pay', '--fromAddress', firstBurnTarget, '--changeAddress', 'pay_change', '--quantity', '100', '--toAddress', 'pay_target'])

		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {secondBurnTarget:150000, thirdBurnTarget:150000, 'pay_target':100, 'pay_change':100000-100})

		# can't submit the same pay action again, since there are no funds left in source account
		self.assertRaises(TransactionNotSuccessfulAgainstCurrentState, RunClient, host, ['pay', '--fromAddress', firstBurnTarget, '--changeAddress', 'pay_change', '--quantity', '100', '--toAddress', 'pay_target'])
		# and this should not submit because there are not enough funds for the payment
		self.assertRaises(TransactionNotSuccessfulAgainstCurrentState, RunClient, host, ['pay', '--fromAddress', 'pay_change', '--changeAddress', 'pay_change', '--quantity', '100000', '--toAddress', 'pay_target'])

	def test_ltc_trading(self):
		host = MockHost()
		if os.path.exists(cacheFile):
			os.remove(cacheFile)
		change = b'change'

		## backing ltc
		host._addUnspent(200000000)

		## initialise some account balances
		RunClient(host, ['burn', '--quantity', '30000000'])
		alice = 'swapbill1'
		RunClient(host, ['burn', '--quantity', '20000000'])
		bob = 'swapbill2'
		RunClient(host, ['burn', '--quantity', '50000000'])
		clive = 'swapbill3'
		RunClient(host, ['burn', '--quantity', '60000000'])
		dave = 'swapbill4'
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {alice:30000000, bob:20000000, clive:50000000, dave:60000000})

		## alice and bob both want to buy LTC
		## clive and dave both want to sell

		## alice makes buy offer

		RunClient(host, ['post_ltc_buy', '--fromAddress', alice, '--quantity', '30000000', '--exchangeRate', '0.5'])
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {bob:20000000, clive:50000000, dave:60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		## bob makes better offer, but with smaller amount

		RunClient(host, ['post_ltc_buy', '--fromAddress', bob, '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {bob:10000000, clive:50000000, dave:60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		## clive makes a sell offer, matching bob's buy exactly

		RunClient(host, ['post_ltc_sell', '--fromAddress', clive, '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {bob:10000000, clive:49375000, dave:60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		## dave and bob make overlapping offers that 'cross over'

		RunClient(host, ['post_ltc_buy', '--fromAddress', bob, '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {clive:49375000, dave:60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		RunClient(host, ['post_ltc_sell', '--fromAddress', dave, '--quantity', '20000000', '--exchangeRate', '0.26953125'])
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {clive:49375000, dave:58750000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)

		host._advance(47)
		info = GetStateInfo(host)		
		self.assertEqual(info['balances'], {clive:49375000, dave:58750000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		#clive fails to make his payment within the required block clount!
		host._advance(1)
		info = GetStateInfo(host)		
		#bob is credited his offer amount (which was locked up for the exchange) + clive's deposit
		self.assertEqual(info['balances'], {bob:10625000, clive:49375000, dave:58750000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		#dave is more on the ball, and makes his completion payment
		#(actually made from 'communal' ltc unspent, in the case of this test)
		RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', '1'])

		info = GetStateInfo(host)		
		#dave gets credited bob's exchange funds, and is also refunded his exchange deposit
		self.assertEqual(info['balances'], {bob:10625000, clive:49375000, dave:69375000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
