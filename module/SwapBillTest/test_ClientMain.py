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

def InitHost():
	host = MockHost()
	if os.path.exists(cacheFile):
		os.remove(cacheFile)
	return host

def RunClient(host, args):
	fullArgs = ['--cache-file', cacheFile] + args
	out = io.StringIO()
	ClientMain.Main(startBlockIndex=0, startBlockHash=host.getBlockHash(0), commandLineArgs=fullArgs, host=host, out=out)
	return out.getvalue()

def GetStateInfo(host):
	output = RunClient(host, ['print_state_info_json'])
	return json.loads(output)

def GetAddressForUnspent(host, formattedAccount):
	#print('trying to match', formattedAccount)
	for entry in host.getUnspent():
		txID = entry['txid']
		vOut = entry['vout']
		formattedAccountForEntry = host.formatAccountForEndUser((txID, vOut))
		#print(formattedAccountForEntry)
		if formattedAccountForEntry == formattedAccount:
			return entry['address']
	raise Exception('not found')

def GetOwnerBalances(host, ownerList, balances):
	result = {}
	ownerAtStart = host._getOwner()
	for owner in ownerList:
		host._setOwner(owner)
		unspent = host.getUnspent()
		ownerBalance = 0
		for entry in unspent:
			account = (entry['txid'], entry['vout'])
			key = host.formatAccountForEndUser(account)
			ownerBalance += balances[key]
		if ownerBalance > 0:
			result[owner] = ownerBalance
	host._setOwner(ownerAtStart)
	return result

class Test(unittest.TestCase):
	def test(self):
		host = MockHost()

		if os.path.exists(cacheFile):
			os.remove(cacheFile)
		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '1000000'])
		self.assertTrue(os.path.exists(cacheFile))

		host._addUnspent(100000000)

		RunClient(host, ['burn', '--quantity', '1000000'])

		#print('unspent after burn:')
		#print(host.getUnspent())

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 1000000})

		output = RunClient(host, ['burn', '--quantity', '2000000'])
		#print(output)

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"02:1": 1000000, "03:1": 2000000})

		output = RunClient(host, ['pay', '--quantity', '1', '--toAddress', "_swapbill2"])

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
		self.assertEqual(info['balances'], {"_swapbill2": 1000001, "_swapbill4": 1999999, "_swapbill6": 100000000}) # swapbill5 entire balance moved in to buy offer

		RunClient(host, ['post_ltc_sell', '--quantity', '200000000', '--exchangeRate', "0.5"])

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"_swapbill2": 1000001, "_swapbill4": 1999999, "_swapbill9": 87500000}) # deposit of 12500000 moved in to sell offer

		output = RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', "0"])
		#print('complete:')
		#print(output)
		#print('end complete')

		info = GetStateInfo(host)
		#print('get info:')
		#print(output)
		#print('end get info')
		self.assertEqual(info['balances'], {"_swapbill2": 1000001, "_swapbill4": 1999999, "_swapbill9": 87500000, "_swapbill10": 212500000}) # seller gets deposit returned plus payment for ltc

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
		firstBurnTarget = "04:1"
		self.assertEqual(info['balances'], {firstBurnTarget:100000})

		self.assertRaises(InsufficientFunds, RunClient, host, ['burn', '--quantity', '600000'])

		RunClient(host, ['burn', '--quantity', '150000'])

		info = GetStateInfo(host)
		secondBurnTarget = "05:1"
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000})

		host._addUnspent(600000)

		RunClient(host, ['burn', '--quantity', '160000'])

		info = GetStateInfo(host)
		thirdBurnTarget = "07:1"
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000, thirdBurnTarget:160000})

		host._setOwner('recipient')
		payTargetAddress = host.formatAddressForEndUser(host.getNewSwapBillAddress())
		host._setOwner('')
		
		RunClient(host, ['pay', '--quantity', '100', '--toAddress', payTargetAddress])
		#print('unspent after pay:')
		#print(host.getUnspent())

		info = GetStateInfo(host)
		payChange = "08:1"
		#self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000, 'pay_target':100, payChange:160000-100})
		payTarget = "08:2"
		self.assertEqual(info['balances'], {firstBurnTarget:100000, secondBurnTarget:150000, payTarget:100, payChange:160000-100})
		host._setOwner('recipient')
		self.assertEqual(host.formatAddressForEndUser(GetAddressForUnspent(host, payTarget)), payTargetAddress)
		host._setOwner('')

		# and this should not submit because there are not enough funds for the payment
		self.assertRaises(TransactionNotSuccessfulAgainstCurrentState, RunClient, host, ['pay', '--quantity', '160000', '--toAddress', 'pay_target'])

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

	def test_ltc_trading(self):
		host = InitHost()

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
		host._addUnspent(60200000)
		RunClient(host, ['burn', '--quantity', '60000000'])
		info = GetStateInfo(host)
		#print('dave unspent:')
		#print(host.getUnspent())
		ownerList = ('alice', 'bob', 'clive', 'dave', 'bob')
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		#print(ownerBalances)
		self.assertDictEqual(ownerBalances, {'bob': 20000000, 'clive': 50000000, 'alice': 30000000, 'dave': 60000000})

		## alice and bob both want to buy LTC
		## clive and dave both want to sell

		## alice makes buy offer

		host._setOwner('alice')
		RunClient(host, ['post_ltc_buy', '--quantity', '30000000', '--exchangeRate', '0.5'])
		info = GetStateInfo(host)
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
		ownerBalances = GetOwnerBalances(host, ownerList, info['balances'])
		self.assertDictEqual(ownerBalances, {'bob': 20000000, 'clive': 50000000, 'dave': 60000000})

		## bob makes better offer, but with smaller amount

		host._setOwner('bob')
		RunClient(host, ['post_ltc_buy', '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'bob_swapbill7':10000000, 'clive_swapbill3':50000000, 'dave_swapbill4':60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 0)

		## clive makes a sell offer, matching bob's buy exactly

		host._setOwner('clive')
		RunClient(host, ['post_ltc_sell', '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'bob_swapbill7':10000000, 'clive_swapbill9':49375000, 'dave_swapbill4':60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		## dave and bob make overlapping offers that 'cross over'

		host._setOwner('bob')
		RunClient(host, ['post_ltc_buy', '--quantity', '10000000', '--exchangeRate', '0.25'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'clive_swapbill9':49375000, 'dave_swapbill4':60000000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 2)
		self.assertEqual(info['numberOfLTCSellOffers'], 0)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		host._setOwner('dave')
		RunClient(host, ['post_ltc_sell', '--quantity', '20000000', '--exchangeRate', '0.26953125'])
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'clive_swapbill9':49375000, 'dave_swapbill13':58750000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)

		host._advance(47)
		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {'clive_swapbill9':49375000, 'dave_swapbill13':58750000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 2)
		#clive fails to make his payment within the required block clount!
		host._advance(1)
		info = GetStateInfo(host)
		#bob is credited his offer amount (which was locked up for the exchange) + clive's deposit
		self.assertEqual(info['balances'], {'bob_swapbill8':10625000, 'clive_swapbill9':49375000, 'dave_swapbill13':58750000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 1)

		#dave is more on the ball, and makes his completion payment
		host._setOwner('dave')
		RunClient(host, ['complete_ltc_sell', '--pending_exchange_id', '1'])

		info = GetStateInfo(host)
		#dave gets credited bob's exchange funds, and is also refunded his exchange deposit
		self.assertEqual(info['balances'], {'bob_swapbill8':10625000, 'clive_swapbill9':49375000, 'dave_swapbill13':58750000, 'dave_swapbill14':10625000})
		self.assertEqual(info['numberOfLTCBuyOffers'], 1)
		self.assertEqual(info['numberOfLTCSellOffers'], 1)
		self.assertEqual(info['numberOfPendingExchanges'], 0)
