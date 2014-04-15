from __future__ import print_function
import unittest
from SwapBill import TransactionFee
from SwapBillTest.MockRPC import Host

class Test(unittest.TestCase):
	def test(self):
		tx = '01000000025b9b8a301fe6902cacfd7c6a1f9a5c5db7eaec68ed044fa3322a16473afffde7020000006b48304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b2590121039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438ffffffffb1213d6b4366b0c02d7a03328c54c1222304784c452b74bacffad29ab33d1866030000006b483045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d11012103c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bccffffffff04a0860100000000001976a91453574201050000000000ffffffff00000000000088aca0860100000000001976a9140e53c3016712c1bf1fb246ee9c7f451248595e8f88ac5f011200000000001976a9148e6843080cf1588fb3cee215bd459818fac38c3c88aca0860100000000001976a9141b12b098af6dfdf2ddf7491e0430e2c3c08e6c1288ac00000000'
		spentTX1 = 'e7fdff3a47162a32a34f04ed68eceab75d5c9a1f6a7cfdac2c90e61f308a9b5b'
		spentTX2 = '66183db39ad2facfba742b454c78042322c1548c32037a2dc0b066436b3d21b1'
		rpcHost = Host()
		rpcHost._d[('decoderawtransaction', tx)] = {
			"vin" : [{"txid":spentTX1,"vout":2},{"txid":spentTX2,"vout":3}],
			"vout" : [{"value":0.00100000},{"value":0.00100000},{"value":0.01179999},{"value":0.00100000}]
		}
		feeRequired = TransactionFee.CalculateRequired(rpcHost, tx)
		self.assertEqual(feeRequired, 100000)
		rpcHost._d[('getrawtransaction', spentTX1, 1)] = {
			"vout" : [{"value":0.00010000},{"value":0.00010000},{"value":0.01579000},{"value":0.00001000}]
		}
		rpcHost._d[('getrawtransaction', spentTX2, 1)] = {
			"vout" : [{"value":0.00010000},{"value":0.00010000},{"value":0.75821191},{"value" : 0.00001000}]
		}
		feePaid = TransactionFee.CalculatePaid(rpcHost, tx)
		self.assertEqual(feePaid, 100000)
		self.assertTrue(TransactionFee.TransactionFeeIsSufficient(rpcHost, tx))

	def test_regression(self):
		## Matt's stuck ltc sell offer transaction
		## (but so far, didn't repeat any issue with this regression code)
		tx = '010000000261bcc223a62c7d466d04295bbf883c7f7526a28161d9c1d578afe94d7a31ce35020000006a47304402201728c7b892e26f29c6cdcee9377919abf1ec3e3939b8870d582a9cb6b053f2fd02201d945968e3148e6f3bb81f092823f3598d0c246a03c643386070767ee87a0139012103ed96074b6a2f3624da46fcb02ff7e70541ac5c3c4cca65ffedf7c720b50be4e6ffffffff61bcc223a62c7d466d04295bbf883c7f7526a28161d9c1d578afe94d7a31ce35010000006a473044022014f2aba8f02c941c32fe5d56a23fc77eab7170b3e8d01da7e9245a1ea8e9607c02202c03892b5e6880314473f14b79b1aef99a9bbd3493764a3cb8e584efa33fe5e201210222bd9a33a910e7d7e08071424fa06c462605069de8ea99826eed02675e02f9d7ffffffff03a0860100000000001976a9145357420350c300000000ffffffffc2f5285c000088aca0860100000000001976a9147e877cb57a375c4525229942326f5e51fb6ad16288ac516c0229000000001976a914593ab0d62f2a0f2ebb7a59dff4e14c180f34d7e388ac00000000'
		rpcHost = Host()
		#rpcHost._connect('**password**')
		expectedQuery = ('decoderawtransaction', '010000000261bcc223a62c7d466d04295bbf883c7f7526a28161d9c1d578afe94d7a31ce35020000006a47304402201728c7b892e26f29c6cdcee9377919abf1ec3e3939b8870d582a9cb6b053f2fd02201d945968e3148e6f3bb81f092823f3598d0c246a03c643386070767ee87a0139012103ed96074b6a2f3624da46fcb02ff7e70541ac5c3c4cca65ffedf7c720b50be4e6ffffffff61bcc223a62c7d466d04295bbf883c7f7526a28161d9c1d578afe94d7a31ce35010000006a473044022014f2aba8f02c941c32fe5d56a23fc77eab7170b3e8d01da7e9245a1ea8e9607c02202c03892b5e6880314473f14b79b1aef99a9bbd3493764a3cb8e584efa33fe5e201210222bd9a33a910e7d7e08071424fa06c462605069de8ea99826eed02675e02f9d7ffffffff03a0860100000000001976a9145357420350c300000000ffffffffc2f5285c000088aca0860100000000001976a9147e877cb57a375c4525229942326f5e51fb6ad16288ac516c0229000000001976a914593ab0d62f2a0f2ebb7a59dff4e14c180f34d7e388ac00000000')
		queryResult = {'vout': [{'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 5357420350c300000000ffffffffc2f5285c0000 OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a9145357420350c300000000ffffffffc2f5285c000088ac', 'addresses': ['mo7cukx42hj1WDPsv3w6HRMgEk7bQ8b1cP'], 'type': 'pubkeyhash', 'reqSigs': 1}, 'value': 0.001, 'n': 0}, {'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 7e877cb57a375c4525229942326f5e51fb6ad162 OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a9147e877cb57a375c4525229942326f5e51fb6ad16288ac', 'addresses': ['ms3yk34v25KVgH7D4JpfE6tqBBJ4CqCuVu'], 'type': 'pubkeyhash', 'reqSigs': 1}, 'value': 0.001, 'n': 1}, {'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 593ab0d62f2a0f2ebb7a59dff4e14c180f34d7e3 OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a914593ab0d62f2a0f2ebb7a59dff4e14c180f34d7e388ac', 'addresses': ['moekk2sExoaQQZqm8ViJJfDnRsa4xvsVPi'], 'type': 'pubkeyhash', 'reqSigs': 1}, 'value': 6.88024657, 'n': 2}], 'vin': [{'sequence': 4294967295, 'scriptSig': {'asm': '304402201728c7b892e26f29c6cdcee9377919abf1ec3e3939b8870d582a9cb6b053f2fd02201d945968e3148e6f3bb81f092823f3598d0c246a03c643386070767ee87a013901 03ed96074b6a2f3624da46fcb02ff7e70541ac5c3c4cca65ffedf7c720b50be4e6', 'hex': '47304402201728c7b892e26f29c6cdcee9377919abf1ec3e3939b8870d582a9cb6b053f2fd02201d945968e3148e6f3bb81f092823f3598d0c246a03c643386070767ee87a0139012103ed96074b6a2f3624da46fcb02ff7e70541ac5c3c4cca65ffedf7c720b50be4e6'}, 'vout': 2, 'txid': '35ce317a4de9af78d5c1d96181a226757f3c88bf5b29046d467d2ca623c2bc61'}, {'sequence': 4294967295, 'scriptSig': {'asm': '3044022014f2aba8f02c941c32fe5d56a23fc77eab7170b3e8d01da7e9245a1ea8e9607c02202c03892b5e6880314473f14b79b1aef99a9bbd3493764a3cb8e584efa33fe5e201 0222bd9a33a910e7d7e08071424fa06c462605069de8ea99826eed02675e02f9d7', 'hex': '473044022014f2aba8f02c941c32fe5d56a23fc77eab7170b3e8d01da7e9245a1ea8e9607c02202c03892b5e6880314473f14b79b1aef99a9bbd3493764a3cb8e584efa33fe5e201210222bd9a33a910e7d7e08071424fa06c462605069de8ea99826eed02675e02f9d7'}, 'vout': 1, 'txid': '35ce317a4de9af78d5c1d96181a226757f3c88bf5b29046d467d2ca623c2bc61'}], 'locktime': 0, 'txid': '2d22d5afecd943ee2510768598a09c397491ac0109cfb76c230a172c4c06e940', 'version': 1}
		rpcHost._d[expectedQuery] = queryResult
		feeRequired = TransactionFee.CalculateRequired(rpcHost, tx)
		self.assertEqual(feeRequired, 100000)
		#feePaid = TransactionFee.CalculatePaid(rpcHost, tx)
		#self.assertEqual(feePaid, 100000)
		#self.assertTrue(TransactionFee.TransactionFeeIsSufficient(rpcHost, tx))
