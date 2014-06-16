from __future__ import print_function
import unittest
from SwapBill import Amounts
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

roundTripPairs=(
    ('0', 0),
    ('1', 100000000),
    ('1.2', 120000000),
    ('0.00000004', 4),
    ('0.0000004', 40),
    ('1.00000005', 100000005),
    ('12.3456789', 1234567890),
)

nonStandardButParsed=(
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

class Test(unittest.TestCase):

	def test(self):
		for s, amount in roundTripPairs:
			self.assertEqual(Amounts.FromString(s), amount)
			self.assertEqual(Amounts.ToString(amount), s)
		for s, amount in nonStandardButParsed:
			self.assertEqual(Amounts.FromString(s), amount)

	def test_bad_amount_strings(self):
		self.assertRaisesRegexp(ExceptionReportedToUser, 'Too much precision in amount string', Amounts.FromString, '0.000000001')
		self.assertRaisesRegexp(ExceptionReportedToUser, 'negative values are not permitted', Amounts.FromString, '-1')
