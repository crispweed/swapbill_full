def Format(host, transactionType, outputs, outputPubKeys, details):
	assert len(outputs) == len(outputPubKeys)
	result = transactionType
	for address, pubKey in zip(outputs, outputPubKeys):
		result += ', ' + address + ' output address='
		result += host.formatAddressForEndUser(pubKey)
	for key in sorted(details):
		result += ', ' + key + '='
		if key.endswith('Address'):
			result += host.formatAddressForEndUser(details[key])
		else:
			result += str(details[key])
	return result
