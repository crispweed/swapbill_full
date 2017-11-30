from __future__ import print_function
import sys
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import Wallet,Address

keyGen = Wallet.DefaultKeyGenerator()
privateKey = keyGen.generatePrivateKey()
print(Address.PrivateKeyToWIF(privateKey, b'\x80')) # bitcoin mainnet private key address version
pubKeyHash = keyGen.privateKeyToPubKeyHash(privateKey)
address = Address.FromPubKeyHash(b'\x00', pubKeyHash) # bitcoin mainnet address version
assert Address.ToPubKeyHash(b'\x00', address) == pubKeyHash
print(address)
