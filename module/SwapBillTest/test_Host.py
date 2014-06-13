from __future__ import print_function
import unittest, shutil, os
from os import path
from SwapBill import Host
from SwapBillTest import MockRPC

# litecoin testnet address versions
addressVersion = b'\x6f'
privateKeyAddressVersion = b'\xef'

dataDirectory = 'dataDirectoryForTests'

class Test(unittest.TestCase):

	def test_initial_tests(self):
		if path.exists(dataDirectory):
			assert path.isdir(dataDirectory)
			shutil.rmtree(dataDirectory)
		os.mkdir(dataDirectory)
		submittedTransactionsLogFileName = path.join(dataDirectory, 'submittedTransactions.txt')
		rpcHost = MockRPC.Host()
		expectedQuery = ('getblockhash', 0)
		queryResult = u'f5ae71e26c74beacc88382716aced69cddf3dffff24f384e1808905e0188f68f'
		rpcHost._d[expectedQuery] = queryResult
		expectedQuery = ('getrawtransactionsinblock', u'f5ae71e26c74beacc88382716aced69cddf3dffff24f384e1808905e0188f68f')
		# following result is for patched litecoind, of course!
		# (add tests for non patched version?)
		queryResult = [{u'hex': u'01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff4804ffff001d0104404e592054696d65732030352f4f63742f32303131205374657665204a6f62732c204170706c65e280997320566973696f6e6172792c2044696573206174203536ffffffff0100f2052a010000004341040184710fa689ad5023690c80f3a49c8f13f8d45b8c857fbcbc8bc4a8e4d3eb4b10f4d4604fa08dce601aaf0f470216fe1b51850b4acf21b179c45070ac7b03a9ac00000000', u'txid': u'97ddfbbae6be97fd6cdf3e7ca13232a3afff2353e29badfab7f73011edd4ced9'}]
		rpcHost._d[expectedQuery] = queryResult
		host = Host.Host(rpcHost=rpcHost, addressVersion=addressVersion, privateKeyAddressVersion=privateKeyAddressVersion, submittedTransactionsLogFileName=submittedTransactionsLogFileName)
		rpcHost._connect('9Eh7BzxEJGseHnqB7L8dDH3EQG3iNgnDQBTjdhEhPeDg')
		unspent = host.getUnspent()
		self.assertEqual(unspent, '')