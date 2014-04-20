from __future__ import print_function
import unittest
from SwapBill import DecodeTransaction

class Test(unittest.TestCase):
	def test(self):
		txHex = '01000000025b9b8a301fe6902cacfd7c6a1f9a5c5db7eaec68ed044fa3322a16473afffde7020000006b48304502202d1cf412570325884ade168056d505116e84a91202ffb17b0fd850b5eba5314e022100d961f2aea05b3b4d1986c33fc746eded50d4eaf69c1e2f35422cd24a42d3b2590121039d60fe18a53ce505bfe0e696e746fee6dfeefa9cff223a147a45390eba3e8438ffffffffb1213d6b4366b0c02d7a03328c54c1222304784c452b74bacffad29ab33d1866030000006b483045022100b2c50332ea7f1e2fb8aa6c8b16323d90920d87bfc35274f604f4ac6254180a6702200c71279244135acc0f418a2881e23017db989780a12941173e0a8cd52ccc8d11012103c6476b54cb9364e4d8e8177b9122d83ee7e61ae421f56b4e89a5ee0950be5bccffffffff04a0860100000000001976a91453574201050000000000ffffffff00000000000088aca0860100000000001976a9140e53c3016712c1bf1fb246ee9c7f451248595e8f88ac5f011200000000001976a9148e6843080cf1588fb3cee215bd459818fac38c3c88aca0860100000000001976a9141b12b098af6dfdf2ddf7491e0430e2c3c08e6c1288ac00000000'
		tx = DecodeTransaction.Decode(txHex)
		# note that output order got reversed since this test case set up
		# (control address normally goes first in decoded transaction, but this is irrelevant for this test)
		self.assertEqual(tx.outputPubKeyHash(3), b'SWB\x01\x05\x00\x00\x00\x00\x00\xff\xff\xff\xff\x00\x00\x00\x00\x00\x00')
		self.assertEqual(tx.numberOfInputs(), 2)
		self.assertEqual(tx.inputTXID(0), 'e7fdff3a47162a32a34f04ed68eceab75d5c9a1f6a7cfdac2c90e61f308a9b5b')
		self.assertEqual(tx.inputVOut(0), 2)
		self.assertEqual(tx.inputTXID(1), '66183db39ad2facfba742b454c78042322c1548c32037a2dc0b066436b3d21b1')
		self.assertEqual(tx.inputVOut(1), 3)
		self.assertEqual(tx.numberOfOutputs(), 4)
		self.assertEqual(tx.outputAmount(3), 100000)
		self.assertEqual(tx.outputPubKeyHash(2), b'\x0eS\xc3\x01g\x12\xc1\xbf\x1f\xb2F\xee\x9c\x7fE\x12HY^\x8f')
		self.assertEqual(tx.outputAmount(2), 100000)
		self.assertEqual(tx.outputPubKeyHash(1), b'\x8ehC\x08\x0c\xf1X\x8f\xb3\xce\xe2\x15\xbdE\x98\x18\xfa\xc3\x8c<')
		self.assertEqual(tx.outputAmount(1), 1179999)
		self.assertEqual(tx.outputPubKeyHash(0), b'\x1b\x12\xb0\x98\xafm\xfd\xf2\xdd\xf7I\x1e\x040\xe2\xc3\xc0\x8el\x12')
		self.assertEqual(tx.outputAmount(0), 100000)
		nonSwapBillTXHex = txHex.replace('5357420105', '5457420105')
		self.assertIsNone(DecodeTransaction.Decode(nonSwapBillTXHex))
		nonSwapBillTXHex = txHex.replace('5357420105', '5358420105')
		self.assertIsNone(DecodeTransaction.Decode(nonSwapBillTXHex))
		nonSwapBillTXHex = txHex.replace('5357420105', '5357430105')
		self.assertIsNone(DecodeTransaction.Decode(nonSwapBillTXHex))
		txHex = '0100000003f4dcbefc65134eedd0e4c51972d0153559373ca792d418224be7c28ba63ede20010000006b48304502206e0271aeb1b91673f9e0de8f0131d0c8d673ea738b94a0937a65e3cc1bd431460221008c00646703d19b6ce348e689df81b2429ffa8b57674cd26c7d3ac1003167f02401210210f8d9c2aa007e2024b85e419406a07e278febfc5828df523c45697129c81aaffffffffff4dcbefc65134eedd0e4c51972d0153559373ca792d418224be7c28ba63ede20030000006b483045022100faf3bc5cec4c3be0e8595c922617c20f05b9628a32c1a75548d305e25a6b2e18022035975ce25e2e987739d91feeccc9f0fd4e9a40fff24b1f92b730fd249009da71012103eb1932850c6ffdfbe806f534ead01a0b618a357782d8de6e947993c7a1334553ffffffff8c270b204ef48ee923b5ab0e2f3269447b1777af31d2bc84ef5a04e690970520010000006b48304502210087c1ee75391d2da87493ce0444c34a237d3418990e7ba45878e263148480e6d402203d89e68755925de0c852c03956fe540af9a3232b45a853796c08f3938c0d812b01210222bd9a33a910e7d7e08071424fa06c462605069de8ea99826eed02675e02f9d7ffffffff03a0860100000000001976a91453574203881300000000ffffffff99999959000088aca0860100000000001976a9147e877cb57a375c4525229942326f5e51fb6ad16288ac91790529000000001976a91431b05dabe3fc38cdb5a2de8e07123fd0b945047888ac00000000'
		tx = DecodeTransaction.Decode(txHex)
		# note that output order got reversed since this test case set up
		# (control address normally goes first in decoded transaction, but this is irrelevant for this test)
		self.assertEqual(tx.outputPubKeyHash(2), b'SWB\x03\x88\x13\x00\x00\x00\x00\xff\xff\xff\xff\x99\x99\x99Y\x00\x00')
		self.assertEqual(tx.numberOfOutputs(), 3)
