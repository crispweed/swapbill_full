from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

def e(power):
	return 10**power
def ToSatoshis(value):
	assert type(value) is float
	return int(value * e(8))

def ToString(satoshis):
	s = str(satoshis)
	l = len(s)
	if l < 9:
		s = '0'*(9-l) + s
	result = s[:-8]
	after = s[-8:]
	while after[-1:] == '0':
		after = after[:-1]
	if after:
		result = result + '.' + after
	return result

def FromString(s):
	pos = s.find('.')
	if pos == -1:
		satoshisString = s + '0' * 8
	else:
		digitsAfter = len(s) - 1 - pos
		if digitsAfter > 8:
			raise ExceptionReportedToUser('Too much precision in amount string (a maximum of 8 digits are allowed after the decimal point).')
		digitsToAdd = 8 - digitsAfter
		satoshisString = s[:pos] + s[pos+1:] + '0' * digitsToAdd
	return int(satoshisString)

