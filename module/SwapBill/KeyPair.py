from __future__ import print_function
import ecdsa
from SwapBill import Base58Check

class BadVersionNumber(Exception):
	pass

def generatePrivateKey():
	# Warning: this random function is not cryptographically strong and is just for example
	# (but using for now anyway, just to see things working!)
	privateKeyHex = ''.join(['%x' % random.randrange(16) for x in range(0, 64)])
	return privateKeyHex.decode('hex')
def privateKeyFromWIF(wif):
	data = Base58Check.Decode(wif)
	if data[:1] != b'\x80':
		raise BadVersionNumber()
	return data[1:]

def privateKeyToPublicKey(privateKey):
	sk = ecdsa.SigningKey.from_string(privateKey, curve=ecdsa.SECP256k1)
	vk = sk.verifying_key
	return sk.verifying_key.to_string()

