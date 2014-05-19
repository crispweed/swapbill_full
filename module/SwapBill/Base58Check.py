from __future__ import print_function
import binascii
import hashlib

class CharacterNotPermittedInEncodedData(Exception):
	pass
class ChecksumDoesNotMatch(Exception):
	pass

dhash = lambda x: hashlib.sha256(hashlib.sha256(x).digest()).digest()
b58_digits = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'

def Encode(data):
	assert type(data) is type(b'')
	address_hex = data + dhash(data)[:4]
	# Convert big-endian bytes to integer
	n = int('0x0' + binascii.hexlify(address_hex).decode('ascii'), 16)
	# Divide that integer into base58
	res = []
	while n > 0:
		n, r = divmod (n, 58)
		res.append(b58_digits[r])
	res = ''.join(res[::-1])
	# Encode leading zeros as base58 zeros
	pad = 0
	while data[pad:pad + 1] == b'\x00':
		pad += 1
	return b58_digits[0] * pad + res

def Decode(string):
	# Convert the string to an integer
	n = 0
	for c in string:
		n *= 58
		if c not in b58_digits:
			raise CharacterNotPermittedInEncodedData()
		digit = b58_digits.index(c)
		n += digit
	# Convert the integer to bytes
	h = '%x' % n
	if len(h) % 2:
		h = '0' + h
	res = binascii.unhexlify(h.encode('ascii'))
	# Add padding back.
	pad = 0
	for c in string[:-1]:
		if c == b58_digits[0]: pad += 1
		else: break
	k = b'\x00' * pad + res
	data, chk0 = k[0:-4], k[-4:]
	chk1 = dhash(data)[:4]
	if chk0 != chk1:
		raise ChecksumDoesNotMatch()
	return data
