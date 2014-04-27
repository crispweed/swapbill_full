import binascii
import hashlib

class BadAddress(Exception):
	pass

dhash = lambda x: hashlib.sha256(hashlib.sha256(x).digest()).digest()
b58_digits = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def base58_check_encode(b, version):
	#b = binascii.unhexlify(bytes(b, 'utf-8'))
	d = version + b

	address_hex = d + dhash(d)[:4]

	# Convert big-endian bytes to integer
	n = int('0x0' + binascii.hexlify(address_hex).decode('ascii'), 16)

	# Divide that integer into base58
	res = []
	while n > 0:
		n, r = divmod (n, 58)
		res.append(b58_digits[r])
	res = ''.join(res[::-1])

	# Encode leading zeros as base58 zeros
	czero = 0
	pad = 0
	for c in d:
		if c == czero: pad += 1
		else: break
	return b58_digits[0] * pad + res

def base58_decode (s, version):
	# Convert the string to an integer
	n = 0
	for c in s:
		n *= 58
		if c not in b58_digits:
			raise BadAddress('Not a valid base58 character:', c)
		digit = b58_digits.index(c)
		n += digit

	# Convert the integer to bytes
	h = '%x' % n
	if len(h) % 2:
		h = '0' + h
	res = binascii.unhexlify(h.encode('ascii'))

	# Add padding back.
	pad = 0
	for c in s[:-1]:
		if c == b58_digits[0]: pad += 1
		else: break
	k = version * pad + res

	addrbyte, data, chk0 = k[0:1], k[1:-4], k[-4:]
	if addrbyte != version:
		raise BadAddress('incorrect version byte:', addrbyte, 'expected:', version)
	chk1 = dhash(addrbyte + data)[:4]
	if chk0 != chk1:
		raise BadAddress('checksum mismatch')
	return data

def FromPubKeyHash(addressVersion, data):
	assert type(addressVersion) is type(b'.')
	assert type(data) is type(b'.')
	assert len(addressVersion) == 1
	assert len(data) == 20
	return base58_check_encode(data, addressVersion)

def ToPubKeyHash(addressVersion, address):
	assert type(addressVersion) is type(b'.')
	assert len(addressVersion) == 1
	return base58_decode(address, addressVersion)
