def Format(host, tx):
	transactionType = tx.__class__.__name__
	details = tx.details()
	result = transactionType
	for key in sorted(details):
		result += ', ' + key + '='
		if key.endswith('Account'):
			result += host.formatAddressForEndUser(details[key])
		else:
			result += str(details[key])
	return result
