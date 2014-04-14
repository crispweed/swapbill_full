from __future__ import print_function
import unittest
from SwapBill.ParseConfig import Parse

class Test(unittest.TestCase):
	def test(self):
		expected = {'key':'value'}
		buf = b'#elimin\xc3\xa9\nkey=value'
		self.assertEqual(Parse(buf), expected)
		buf = b'#elimin\xc3\xa9\nkey=value\n'
		self.assertEqual(Parse(buf), expected)
		buf = b'#elimin\xc3\xa9\rkey=value\r'
		self.assertEqual(Parse(buf), expected)
		buf = b'#elimin\xc3\xa9\r\nkey=value\r\n'
		self.assertEqual(Parse(buf), expected)
		buf = b'  #elimin\xc3\xa9\n  key = value \n'
		self.assertEqual(Parse(buf), expected)
		buf = b'  #elimin\xc3\xa9\r\n  key = value \r\n'
		self.assertEqual(Parse(buf), expected)
		expected = {'key1':'value1', 'key2':'value2'}
		buf = b'#key=value\nkey1=value1\nkey2=value2\n'
		self.assertEqual(Parse(buf), expected)
