SATOSHIS_IN_LTC = 100000000
def ToSatoshis(value):
	assert type(value) is float
	return int(value * SATOSHIS_IN_LTC)
def FromSatoshis(value):
	assert type(value) is int
	return float(value) / SATOSHIS_IN_LTC
