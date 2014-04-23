def GetUnspent(buildLayer, swapBillBalances):
	addresses, amounts, asInputs = buildLayer.getUnspent()
	amountsResult = []
	asInputsResult = []
	swapBillUnspent = {}
	for i in range(len(addresses)):
		if asInputs[i] in swapBillBalances:
			assert not asInputs[i] in swapBillUnspent
			swapBillUnspent[asInputs[i]] = (addresses[i], amounts[i])
		else:
			amountsResult.append(amounts[i])
			asInputsResult.append(asInputs[i])
	return (amountsResult, asInputsResult), swapBillUnspent
