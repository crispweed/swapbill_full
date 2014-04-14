from __future__ import print_function
import unittest
from SwapBill import TransactionFee

class MockRPCHost(object):
	def __init__(self):
		self._d = {}
	def call(self, *arguments):
		return self._d[arguments]

class Test(unittest.TestCase):
	def test(self):
		tx = '01000000025b9b8a301fe6902cacfd7c6a1f9a5c5db7eaec68ed044fa3322a16473afffde7020000006b48304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b2590121039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438ffffffffb1213d6b4366b0c02d7a03328c54c1222304784c452b74bacffad29ab33d1866030000006b483045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d11012103c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bccffffffff04a0860100000000001976a91453574201050000000000ffffffff00000000000088aca0860100000000001976a9140e53c3016712c1bf1fb246ee9c7f451248595e8f88ac5f011200000000001976a9148e6843080cf1588fb3cee215bd459818fac38c3c88aca0860100000000001976a9141b12b098af6dfdf2ddf7491e0430e2c3c08e6c1288ac00000000'
		spentTX1 = 'e7fdff3a47162a32a34f04ed68eceab75d5c9a1f6a7cfdac2c90e61f308a9b5b'
		spentTX2 = '66183db39ad2facfba742b454c78042322c1548c32037a2dc0b066436b3d21b1'
		rpcHost = MockRPCHost()
		rpcHost._d[('decoderawtransaction', tx)] = {
			"vin" : [{"txid":spentTX1,"vout":2},{"txid":spentTX2,"vout":3}],
			"vout" : [{"value":0.00100000},{"value":0.00100000},{"value":0.01179999},{"value":0.00100000}]
		}
		feeRequired = TransactionFee.CalculateRequired(rpcHost, tx)
		assert feeRequired == 100000
		rpcHost._d[('getrawtransaction', spentTX1, 1)] = {
			"vout" : [{"value":0.00010000},{"value":0.00010000},{"value":0.01579000},{"value":0.00001000}]
		}
		rpcHost._d[('getrawtransaction', spentTX2, 1)] = {
			"vout" : [{"value":0.00010000},{"value":0.00010000},{"value":0.75821191},{"value" : 0.00001000}]
		}
		feePaid = TransactionFee.CalculatePaid(rpcHost, tx)
		assert feePaid == 100000
		assert TransactionFee.TransactionFeeIsSufficient(rpcHost, tx)
