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

		output = RunClient(host, ['transfer', '--fromAddress', "swapbill3", '--quantity', '1', '--toAddress', "swapbill2"])

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

		info = GetStateInfo(host)
		self.assertEqual(info['balances'], {"swapbill2": 1000001, "swapbill3": 1999999, "swapbill5": 300000000}) # swapbill5 gets deposit returned plus payment for ltc
