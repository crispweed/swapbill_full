def ToSatoshis(value):
	assert type(value) is float
	return int(value * 100000000)
