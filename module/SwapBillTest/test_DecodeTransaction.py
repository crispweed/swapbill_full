from __future__ import print_function
import unittest
from SwapBill import DecodeTransaction
from SwapBill import RPC ## for setup only

class MockRPCHost(object):
	def __init__(self):
		self._d = {}
	def call(self, *arguments):
		if hasattr(self, '_actualHost'):
			print(arguments.__repr__())
			print(self._actualHost.call(*arguments).__repr__())
		return self._d[arguments]

class Test(unittest.TestCase):
	def test(self):
		txHex = '01000000025b9b8a301fe6902cacfd7c6a1f9a5c5db7eaec68ed044fa3322a16473afffde7020000006b48304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b2590121039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438ffffffffb1213d6b4366b0c02d7a03328c54c1222304784c452b74bacffad29ab33d1866030000006b483045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d11012103c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bccffffffff04a0860100000000001976a91453574201050000000000ffffffff00000000000088aca0860100000000001976a9140e53c3016712c1bf1fb246ee9c7f451248595e8f88ac5f011200000000001976a9148e6843080cf1588fb3cee215bd459818fac38c3c88aca0860100000000001976a9141b12b098af6dfdf2ddf7491e0430e2c3c08e6c1288ac00000000'
		## first pub key hash query shouldn't do rpc (important optimisation)
		tx = DecodeTransaction.Transaction(txHex=txHex, rpcHost=None)
		self.assertEqual(tx.outputPubKeyHash(0), b'SWB\x01\x05\x00\x00\x00\x00\x00\xff\xff\xff\xff\x00\x00\x00\x00\x00\x00')
		#print(tx.outputPubKeyHash(0))
		rpcHost = MockRPCHost()
		tx = DecodeTransaction.Transaction(txHex=txHex, rpcHost=rpcHost)
		expectedQuery = ('decoderawtransaction', '01000000025b9b8a301fe6902cacfd7c6a1f9a5c5db7eaec68ed044fa3322a16473afffde7020000006b48304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b2590121039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438ffffffffb1213d6b4366b0c02d7a03328c54c1222304784c452b74bacffad29ab33d1866030000006b483045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d11012103c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bccffffffff04a0860100000000001976a91453574201050000000000ffffffff00000000000088aca0860100000000001976a9140e53c3016712c1bf1fb246ee9c7f451248595e8f88ac5f011200000000001976a9148e6843080cf1588fb3cee215bd459818fac38c3c88aca0860100000000001976a9141b12b098af6dfdf2ddf7491e0430e2c3c08e6c1288ac00000000')
		rpcResponse = {'version': 1, 'vin': [{'sequence': 4294967295, 'scriptSig': {'asm': '304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b25901 039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438', 'hex': '48304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b2590121039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438'}, 'txid': 'e7fdff3a47162a32a34f04ed68eceab75d5c9a1f6a7cfdac2c90e61f308a9b5b', 'vout': 2}, {'sequence': 4294967295, 'scriptSig': {'asm': '3045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d1101 03c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bcc', 'hex': '483045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d11012103c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bcc'}, 'txid': '66183db39ad2facfba742b454c78042322c1548c32037a2dc0b066436b3d21b1', 'vout': 3}], 'txid': '7fedd7ef53bb47be6d47785a01c06b18a2fcafa1938dda0792b28f19a31d114b', 'locktime': 0, 'vout': [{'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 53574201050000000000ffffffff000000000000 OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a91453574201050000000000ffffffff00000000000088ac', 'type': 'pubkeyhash', 'addresses': ['mo7cukos6ZRkaKSKoQPY3TTjKFr5NDrv7c'], 'reqSigs': 1}, 'n': 0, 'value': 0.001}, {'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 0e53c3016712c1bf1fb246ee9c7f451248595e8f OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a9140e53c3016712c1bf1fb246ee9c7f451248595e8f88ac', 'type': 'pubkeyhash', 'addresses': ['mgpi6cBV9KQohQs9wGYZKRopgumRsKTgpF'], 'reqSigs': 1}, 'n': 1, 'value': 0.001}, {'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 8e6843080cf1588fb3cee215bd459818fac38c3c OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a9148e6843080cf1588fb3cee215bd459818fac38c3c88ac', 'type': 'pubkeyhash', 'addresses': ['mtVw9XubrZm4Mc2qA7DaxqZVQVJ3qEAmt9'], 'reqSigs': 1}, 'n': 2, 'value': 0.01179999}, {'scriptPubKey': {'asm': 'OP_DUP OP_HASH160 1b12b098af6dfdf2ddf7491e0430e2c3c08e6c12 OP_EQUALVERIFY OP_CHECKSIG', 'hex': '76a9141b12b098af6dfdf2ddf7491e0430e2c3c08e6c1288ac', 'type': 'pubkeyhash', 'addresses': ['mhz6vpqWej1MffgnubKAENtvLHBHFmaaym'], 'reqSigs': 1}, 'n': 3, 'value': 0.001}]}
		rpcHost._d[expectedQuery] = rpcResponse
		self.assertEqual(tx.numberOfInputs(), 2)
		self.assertEqual(tx.inputTXID(0), 'e7fdff3a47162a32a34f04ed68eceab75d5c9a1f6a7cfdac2c90e61f308a9b5b')
		self.assertEqual(tx.inputVOut(0), 2)
		self.assertEqual(tx.inputTXID(1), '66183db39ad2facfba742b454c78042322c1548c32037a2dc0b066436b3d21b1')
		self.assertEqual(tx.inputVOut(1), 3)
		self.assertEqual(tx.numberOfOutputs(), 4)
		self.assertEqual(tx.outputPubKeyHash(0), b'SWB\x01\x05\x00\x00\x00\x00\x00\xff\xff\xff\xff\x00\x00\x00\x00\x00\x00')
		self.assertEqual(tx.outputAmount(0), 100000)
		self.assertEqual(tx.outputPubKeyHash(1), b'\x0eS\xc3\x01g\x12\xc1\xbf\x1f\xb2F\xee\x9c\x7fE\x12HY^\x8f')
		self.assertEqual(tx.outputAmount(1), 100000)
		self.assertEqual(tx.outputPubKeyHash(2), b'\x8ehC\x08\x0c\xf1X\x8f\xb3\xce\xe2\x15\xbdE\x98\x18\xfa\xc3\x8c<')
		self.assertEqual(tx.outputAmount(2), 1179999)
		self.assertEqual(tx.outputPubKeyHash(3), b'\x1b\x12\xb0\x98\xafm\xfd\xf2\xdd\xf7I\x1e\x040\xe2\xc3\xc0\x8el\x12')
		self.assertEqual(tx.outputAmount(3), 100000)

		## TODO check that exception is raised when output scripts are in unexpected format!

		## for setup, if required, using testnet port
		#rpcHost._actualHost = RPC.Host(b'http://litecoinrpc:**password**@localhost:19332')
