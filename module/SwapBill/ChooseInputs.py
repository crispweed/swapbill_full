def ChooseInputs(unspentAmounts, amountRequired):
	if amountRequired == 0:
		return ([], 0)
	assert amountRequired > 0

	sortedUnspent = []
	for	i, amount in enumerate(unspentAmounts):
		sortedUnspent.append((amount, i))
	sortedUnspent.sort()

	spent = 0
	result = []

	while spent < amountRequired and len(result) < len(unspentAmounts):
		toAddI = sortedUnspent[len(result)][1]
		result.append(toAddI)
		spent += unspentAmounts[result[-1]]

	return (result, spent)
