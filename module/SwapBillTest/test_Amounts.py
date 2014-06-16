from __future__ import print_function
import unittest
from SwapBill import Amounts
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

class Test(unittest.TestCase):

	def test(self):
		# following are in canonical representation
		pairs=(
			('0', 0),
			('1', 100000000),
			('1.2', 120000000),
			('0.00000004', 4),
			('0.0000004', 40),
			('1.00000005', 100000005),
			('12.3456789', 1234567890),
		)
		for s, amount in pairs:
			self.assertEqual(Amounts.FromString(s), amount)
			self.assertEqual(Amounts.ToString(amount), s)
		# following are not in canonical representation, but should be parsed as the given value
		pairs=(
	        ('.0', 0),
	        ('0.0', 0),
	        ('0.00000000', 0),
	        ('01', 100000000),
	        ('1.20', 120000000),
	        ('01.20', 120000000),
	        ('00.00000004', 4),
	        ('0.00000040', 40),
	        ('0001.00000005', 100000005),
	        ('12.34567890', 1234567890),
	    )
		for s, amount in pairs:
			self.assertEqual(Amounts.FromString(s), amount)

	def test_bad_amount(self):
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Too much precision in decimal string', Amounts.FromString, '0.000000001')
		self.assertRaisesRegexp(ExceptionReportedToUser, 'negative values are not permitted', Amounts.FromString, '-1')

	def test_percent_parameters(self):
		self.assertEqual(Amounts.percentBytes, 4)
		self.assertEqual(Amounts.percentDivisor, 1000000000)
		percentBits = Amounts.percentBytes * 8
		bytesDivisor = 2 ** percentBits
		self.assertTrue(Amounts.percentDivisor <= bytesDivisor)
		self.assertTrue(Amounts.percentDivisor * 10 > bytesDivisor)
		self.assertEqual(10 ** Amounts._percentDigits, Amounts.percentDivisor)

	def test_percent_divisor(self):
		# following are in canonical representation
		pairs=(
			('0.1', 100000000),
			('0.000000002', 2),
			('0.999999999', 999999999),
		)
		for s, value in pairs:
			self.assertEqual(Amounts.PercentFromString(s), value)
			self.assertEqual(Amounts.PercentToString(value), s)
		# following are not in canonical representation, but should be parsed as the given value
		pairs=(
			('0.10', 100000000),
			('0.100', 100000000),
			('0.100000000', 100000000),
			('0.000000020', 20),
		)
		for s, value in pairs:
			self.assertEqual(Amounts.PercentFromString(s), value)

	def test_bad_percent(self):
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Too much precision in decimal string [(]a maximum of 9 digits are allowed after the decimal point[)]', Amounts.PercentFromString, '0.0000000001')
		self.assertRaisesRegexp(ExceptionReportedToUser, 'negative values are not permitted', Amounts.PercentFromString, '-1')
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', Amounts.PercentFromString, '0')
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Bad percentage string [(]value must be greater than 0.0 and less than 1.0[)]', Amounts.PercentFromString, '0.0')
