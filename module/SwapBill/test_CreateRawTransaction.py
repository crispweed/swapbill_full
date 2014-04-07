from __future__ import print_function
import unittest
from SwapBill import CreateRawTransaction

class MockObject(object):
	pass

class Test(unittest.TestCase):
	def test(self):
		config = MockObject()
		config.addressVersion = b'\x6f'
		inputs = [["b46c0b9cab086fd3ffbe69796e0c0416c14e4b5f416fe7ec349848b08ded7986", 0, "2102066feb3b543146fec6afcb89a2e92e18e3fbbee43ff5c1175cb01897594ab8acac"]]
		targetAddresses = ['mnPc49jpEpUohMCdr7Uh3So5u4o9Ms82MC', 'mkdo4rWNPNSbFTjfkV1WhoyDmZLsuNuG9N']
		targetAmounts = [100000000, 200000000]
		rawTX = CreateRawTransaction.CreateRawTransaction(config, inputs, targetAddresses, targetAmounts)
		#print(rawTX)
		assert rawTX == b'01000000018679ed8db0489834ece76f415f4b4ec116040c6e7969beffd36f08ab9c0b6cb400000000232102066feb3b543146fec6afcb89a2e92e18e3fbbee43ff5c1175cb01897594ab8acacffffffff0200e1f505000000001976a9144b6512d12809128d65329225b630b7f508d2c58b88ac00c2eb0b000000001976a9143823d67db1ca2067d141ae2ffce6cba88e286f2288ac00000000'
