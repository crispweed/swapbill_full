from SwapBill import KeyPair

nextI = 0
def GeneratePrivateKey_ForTests():
	global nextI
	result = str(nextI) + '-' * 31
	nextI += 1
	return result[:32].encode('ascii')
def GenerateRandomPublicKeyForUseAsSecret_ForTests():
	global nextI
	result = str(nextI) + '+' * 63
	nextI += 1
	return result[:64].encode('ascii')
def PrivateKeyToPublicKey_ForTests(privateKey):
	s = privateKey.decode('ascii').strip('-')
	i = int(s)
	result = str(i) + '+' * 63
	return result[:64].encode('ascii')
def PublicKeyToPubKeyHash_ForTests(publicKey):
	s = publicKey.decode('ascii').strip('+')
	i = int(s)
	result = str(i) + '*' * 19
	return result[:20].encode('ascii')

KeyPair.GeneratePrivateKey = GeneratePrivateKey_ForTests
KeyPair.GenerateRandomPublicKeyForUseAsSecret = GenerateRandomPublicKeyForUseAsSecret_ForTests
KeyPair.PrivateKeyToPublicKey = PrivateKeyToPublicKey_ForTests
KeyPair.PublicKeyToPubKeyHash = PublicKeyToPubKeyHash_ForTests
