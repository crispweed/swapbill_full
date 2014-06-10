from __future__ import print_function
import unittest, binascii, struct
from SwapBill import KeyPair
from SwapBill import Address

class Test(unittest.TestCase):
	def test(self):
		privateKey = KeyPair.privateKeyFromWIF(b'\x80', '5HueCGU8rMjxEXxiPuD5BDku4MkFqeZyd4dZ1jvhTVqvbTLvyTJ') # has bitcoin main net address version!
		self.assertEqual(privateKey,  b"\x0c\x28\xfc\xa3\x86\xc7\xa2'`\x0b/\xe5\x0b|\xae\x11\xec\x86\xd3\xbf\x1f\xbeG\x1b\xe8\x98'\xe1\x9dr\xaa\x1d")
		testNetWIF = KeyPair.privateKeyToWIF(privateKey, b'\xef') # litecoin testnet private key address version
		self.assertEqual(testNetWIF, '91gGn1HgSap6CbU12F6z3pJri26xzp7Ay1VW6NHCoEayNXwRpu2')
		pubKeyHash = KeyPair.privateKeyToPubKeyHash(privateKey)
		#print(binascii.hexlify(pubKeyHash).decode('ascii'))
		# a65d1a239d4ec666643d350c7bb8fc44d2881128
		self.assertEqual(pubKeyHash, b'\xa6]\x1a#\x9dN\xc6fd=5\x0c{\xb8\xfcD\xd2\x88\x11(')
		#print(Address.FromPubKeyHash(b'\x6f', pubKeyHash))
		# mvgbzkCSgKbYgaeG38auUzR7otscEGi8U7
		# sent to this address with txID = 9f432b7be77e95beda7c46a7e829b15bdee3d118f39eb2beaf8d0b6bcb81c0bb, vout = 0
	#redeeming transaction (unsigned)
#0100000001bbc081cb6b0b8dafbeb29ef318d1e3de5bb129e8a7467cdabe957ee77b2b439f0000000000ffffffff01c0e1e400000000001976a914a65d1a239d4ec666643d350c7bb8fc44d288112888ac00000000
# command to sign, after import private key:
#src/litecoind -testnet -txindex signrawtransaction 0100000001bbc081cb6b0b8dafbeb29ef318d1e3de5bb129e8a7467cdabe957ee77b2b439f0000000000ffffffff01c0e1e400000000001976a914a65d1a239d4ec666643d350c7bb8fc44d288112888ac00000000
		privateKey = KeyPair.generatePrivateKey()
		testNetWIF = KeyPair.privateKeyToWIF(privateKey, b'\xef') # litecoin testnet private key address version
		#print(testNetWIF)
		#93MQGkahxMeYN63i8fnXNMTyhz75143vzC1YpyZ2o4tCZAwHvFk
		pubKeyHash = KeyPair.privateKeyToPubKeyHash(privateKey)
		#print(Address.FromPubKeyHash(b'\x6f', pubKeyHash))
		#mywrEu2mvWZfxvqMzLmcQUGG1BxJNsM5uy

#thomas@Z77A-MINT15 ~/git/sb-litecoin $ src/litecoind -testnet -txindex sendtoaddress mywrEu2mvWZfxvqMzLmcQUGG1BxJNsM5uy 0.3
#fc0b5a5ac9987c0374c49907c2062db6c4f84251a2ac9c4f6aceec37238fbadb

# check vout with following: (was 1)
#thomas@Z77A-MINT15 ~/git/sb-litecoin $ src/litecoind -testnet -txindex getrawtransaction fc0b5a5ac9987c0374c49907c2062db6c4f84251a2ac9c4f6aceec37238fbadb 1

#thomas@Z77A-MINT15 ~/git/sb-litecoin $ src/litecoind -testnet -txindex createrawtransaction '[{"txid":"fc0b5a5ac9987c0374c49907c2062db6c4f84251a2ac9c4f6aceec37238fbadb","vout":1}]' '{"mvgbzkCSgKbYgaeG38auUzR7otscEGi8U7":0.16}'
#0100000001dbba8f2337ecce6a4f9caca25142f8c4b62d06c20799c474037c98c95a5a0bfc0100000000ffffffff010024f400000000001976a914a65d1a239d4ec666643d350c7bb8fc44d288112888ac00000000

#thomas@Z77A-MINT15 ~/git/sb-litecoin $ src/litecoind -testnet -txindex signrawtransaction 0100000001dbba8f2337ecce6a4f9caca25142f8c4b62d06c20799c474037c98c95a5a0bfc0100000000ffffffff010024f400000000001976a914a65d1a239d4ec666643d350c7bb8fc44d288112888ac00000000 null '["93MQGkahxMeYN63i8fnXNMTyhz75143vzC1YpyZ2o4tCZAwHvFk"]'
#{
#    "hex" : "0100000001dbba8f2337ecce6a4f9caca25142f8c4b62d06c20799c474037c98c95a5a0bfc010000008b4830450220159e9a0816d338d14c07c66247da8214c338dfcd27aaf31aa9af534bdae45d9c022100802e9ef189c9e2c374610574b217da609d218fa3dc285906f1d892d59afb197f014104d46e3900a229c189c9eb0bd3455a80b7c9fe5ab58892aa217c7d758cf76f55555ba23783804bf3058101c5f83a1d48d97b328eeb61c45a609246649da7f039e0ffffffff010024f400000000001976a914a65d1a239d4ec666643d350c7bb8fc44d288112888ac00000000",
#    "complete" : true
#}

#thomas@Z77A-MINT15 ~/git/sb-litecoin $ src/litecoind -testnet -txindex sendrawtransaction 0100000001dbba8f2337ecce6a4f9caca25142f8c4b62d06c20799c474037c98c95a5a0bfc010000008b4830450220159e9a0816d338d14c07c66247da8214c338dfcd27aaf31aa9af534bdae45d9c022100802e9ef189c9e2c374610574b217da609d218fa3dc285906f1d892d59afb197f014104d46e3900a229c189c9eb0bd3455a80b7c9fe5ab58892aa217c7d758cf76f55555ba23783804bf3058101c5f83a1d48d97b328eeb61c45a609246649da7f039e0ffffffff010024f400000000001976a914a65d1a239d4ec666643d350c7bb8fc44d288112888ac00000000
#606510631cdf04820cb409ec0ec7072fce293f08c0594b8f85f798533d8a36e2

