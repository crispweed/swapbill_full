from __future__ import print_function
import sys
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import KeyPair,Address,Util

privateKey = KeyPair.GeneratePrivateKey()
print(Util.toHex(privateKey))
publicKey = KeyPair.PrivateKeyToPublicKey(privateKey)
pubKeyHash = KeyPair.PublicKeyToPubKeyHash(publicKey)

#address = Address.FromPubKeyHash(b'\x00', pubKeyHash) # bitcoin mainnet address version
#assert Address.ToPubKeyHash(b'\x00', address) == pubKeyHash
#print('bitcoin:', address)

address = Address.FromPubKeyHash(b'\x6f', pubKeyHash)
assert Address.ToPubKeyHash(b'\x6f', address) == pubKeyHash
print('bitcoin or litecoin testnet:', address)

