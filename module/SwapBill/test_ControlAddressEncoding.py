from __future__ import print_function
import unittest
from SwapBill import ControlAddressEncoding

class MockTransaction(object):
	def encode(self):
		return self.amount, self.maxBlock, self.extraData

def _checkDecode(address, transaction):
	typeCode, amount, maxBlock, extraData = ControlAddressEncoding.Decode(address)
	assert typeCode == transaction.typeCode
	assert amount == transaction.amount
	assert maxBlock == transaction.maxBlock
	assert extraData == transaction.extraData

class Test(unittest.TestCase):
	def test(self):
		transaction = MockTransaction()

		transaction.typeCode = 0
		transaction.amount = 0
		transaction.maxBlock = 0
		transaction.extraData = b'extrad'
		address = ControlAddressEncoding.Encode(transaction)
		#print(address.__repr__())
		assert address == b'SWB\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00extrad'
		_checkDecode(address, transaction)

		transaction.typeCode = 0x11
		transaction.amount = 0x171615141312
		transaction.maxBlock = 0x1b1a1918
		transaction.extraData = b'......'
		address = ControlAddressEncoding.Encode(transaction)
		assert address == b'SWB\x11\x12\x13\x14\x15\x16\x17\x18\x19\x1a\x1b......'
		_checkDecode(address, transaction)

		transaction.typeCode = 0x11
		transaction.amount = 0x121314151617
		transaction.maxBlock = 0x18191a1b
		transaction.extraData = b'......'
		address = ControlAddressEncoding.Encode(transaction)
		assert address == b'SWB\x11\x17\x16\x15\x14\x13\x12\x1b\x1a\x19\x18......'
		_checkDecode(address, transaction)

		transaction.typeCode = 0xff
		transaction.amount = 0xffffffffffff
		transaction.maxBlock = 0xffffffff
		transaction.extraData = b'......'
		address = ControlAddressEncoding.Encode(transaction)
		assert address == b'SWB\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff......'
		_checkDecode(address, transaction)

		transaction.typeCode = -1
		transaction.amount = 0
		transaction.maxBlock = 0
		transaction.extraData = b'extrad'
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)
		transaction.typeCode = 0x100
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)

		transaction.typeCode = 0
		transaction.amount = -1
		transaction.maxBlock = 0
		transaction.extraData = b'extrad'
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)
		transaction.amount = 0x1000000000000
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)

		transaction.typeCode = 0
		transaction.amount = 0
		transaction.maxBlock = -1
		transaction.extraData = b'extrad'
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)
		transaction.amount = 0x100000000
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)

		transaction.typeCode = 0
		transaction.amount = 0
		transaction.maxBlock = 0
		transaction.extraData = b'extradata'
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)
		transaction.extraData = b'extra'
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)
		transaction.extraData = 25
		self.assertRaises(AssertionError, ControlAddressEncoding.Encode, transaction)
