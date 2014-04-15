from __future__ import print_function
import unittest
from SwapBill import SourceLookup
from SwapBillTest.MockRPC import Host

class Test(unittest.TestCase):
	def test(self):
		addressVersion = b'\x6f'
		rpcHost = Host()

		lookup = SourceLookup.Lookup(addressVersion, rpcHost)

		#rpcHost._connect('**password**')

		txID = "227ad2f0546ce25ec6f74708620d386f8a7bf74c3eb086292fbd472d0c6a4b8c"
		vOut = 0

		expectedQuery = ('getrawtransaction', '227ad2f0546ce25ec6f74708620d386f8a7bf74c3eb086292fbd472d0c6a4b8c', 1)
		results = {'blockhash': '84ed88b6f0cede5f2b2055401e0f8a9a19f26316de43aa124d1ed3decfda82c5', 'vout': [{'n': 0, 'value': 50.0, 'scriptPubKey': {'reqSigs': 1, 'hex': '76a914fea78b7efa774694aa66246e7d1ee9d2b82f199388ac', 'addresses': ['n4jSe18kZMCdGcZqaYprShXW6EH1wivUK1'], 'asm': 'OP_DUP OP_HASH160 fea78b7efa774694aa66246e7d1ee9d2b82f1993 OP_EQUALVERIFY OP_CHECKSIG', 'type': 'pubkeyhash'}}], 'hex': '01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff270355bd03062f503253482f04493a47530810000000000000000d2f6e6f64655374726174756d2f000000000100f2052a010000001976a914fea78b7efa774694aa66246e7d1ee9d2b82f199388ac00000000', 'vin': [{'coinbase': '0355bd03062f503253482f04493a47530810000000000000000d2f6e6f64655374726174756d2f', 'sequence': 0}], 'txid': '227ad2f0546ce25ec6f74708620d386f8a7bf74c3eb086292fbd472d0c6a4b8c', 'blocktime': 1397176905, 'version': 1, 'confirmations': 1304, 'time': 1397176905, 'locktime': 0}
		rpcHost._d[expectedQuery] = results

		source = lookup.getSourceFor(txID, vOut)
		self.assertEqual(source, b'\xfe\xa7\x8b~\xfawF\x94\xaaf$n}\x1e\xe9\xd2\xb8/\x19\x93')

		txID = "a94da761685326e1d78d7311a43d3c4cd59169926552aa6853e4ade3f71df305"
		vOut = 0

		expectedQuery = ('getrawtransaction', 'a94da761685326e1d78d7311a43d3c4cd59169926552aa6853e4ade3f71df305', 1)
		results = {'version': 1, 'locktime': 0, 'blocktime': 1397179491, 'blockhash': 'f5aa07ad76ed7c13c32c0b8f61655c9b5a42ef1274c332dc3b7d484f2bb53c56', 'vout': [{'scriptPubKey': {'reqSigs': 1, 'type': 'pubkeyhash', 'asm': 'OP_DUP OP_HASH160 fea78b7efa774694aa66246e7d1ee9d2b82f1993 OP_EQUALVERIFY OP_CHECKSIG', 'addresses': ['n4jSe18kZMCdGcZqaYprShXW6EH1wivUK1'], 'hex': '76a914fea78b7efa774694aa66246e7d1ee9d2b82f199388ac'}, 'n': 0, 'value': 50.0}], 'hex': '01000000010000000000000000000000000000000000000000000000000000000000000000ffffffff270375be03062f503253482f04634447530810000000000000000d2f6e6f64655374726174756d2f000000000100f2052a010000001976a914fea78b7efa774694aa66246e7d1ee9d2b82f199388ac00000000', 'confirmations': 1016, 'time': 1397179491, 'txid': 'a94da761685326e1d78d7311a43d3c4cd59169926552aa6853e4ade3f71df305', 'vin': [{'coinbase': '0375be03062f503253482f04634447530810000000000000000d2f6e6f64655374726174756d2f', 'sequence': 0}]}
		rpcHost._d[expectedQuery] = results

		source = lookup.getSourceFor(txID, vOut)
		self.assertEqual(source, b'\xfe\xa7\x8b~\xfawF\x94\xaaf$n}\x1e\xe9\xd2\xb8/\x19\x93')
