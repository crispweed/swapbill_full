

def GetUnspent(buildLayer, swapBillBalances):
	addresses, amounts, asInputs = buildLayer.getUnspent()
	amountsResult = []
	asInputsResult = []
	for i in range(len(addresses)):
		if not addresses[i] in swapBillBalances:
			amountsResult.append(amounts[i])
			asInputsResult.append(asInputs[i])
	return amountsResult,asInputsResult

def GetUnspent_WithSingleSource(buildLayer, swapBillBalances, sourceAddress):
	assert sourceAddress in swapBillBalances
	addresses, amounts, asInputs = buildLayer.getUnspent()
	amountsResult = []
	asInputsResult = []
	singleSourceResult = None
	for i in range(len(addresses)):
		if not addresses[i] in swapBillBalances:
			amountsResult.append(amounts[i])
			asInputsResult.append(asInputs[i])
		elif addresses[i] == sourceAddress:
			singleSourceResult = (amounts[i], asInputs[i])
	return (amountsResult, asInputsResult), singleSourceResult

def AddressesWithUnspent(buildLayer, swapBillBalances):
	addresses, amounts, asInputs = buildLayer.getUnspent()
	result = set()
	for i in range(len(addresses)):
		if addresses[i] in swapBillBalances:
			result.add(addresses[i])
	return result
