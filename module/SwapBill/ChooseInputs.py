def ChooseInputs(maxInputs, unspentAmounts, amountRequired):
	if amountRequired == 0 or maxInputs == 0:
		return ([], 0)
	assert amountRequired > 0

	sortedUnspent = []
	for	i in range(len(unspentAmounts)):
		sortedUnspent.append((unspentAmounts[i], i))
	sortedUnspent.sort()
	#print(sortedUnspent)

	if maxInputs > len(unspentAmounts):
		maxInputs = len(unspentAmounts)

	spent = 0
	result = []

	#print('start')
	#print result

	while spent < amountRequired and len(result) < maxInputs:
		#print('extend')
		toAddI = sortedUnspent[len(result)][1]
		result.append(toAddI)
		spent += unspentAmounts[result[-1]]
		#print result

	startI = 0
	while spent < amountRequired and startI + len(result) < len(unspentAmounts):
		#print('shift')
		spent -= unspentAmounts[result[0]]
		result = result[1:]
		startI += 1
		toAddI = sortedUnspent[startI + len(result)][1]
		result.append(toAddI)
		spent += unspentAmounts[result[-1]]
		#print result

	return (result, spent)
