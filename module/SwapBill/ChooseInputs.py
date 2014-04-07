def ChooseInputs(unspent, amountRequired):
	if amountRequired == 0:
		return ([], 0)
	assert amountRequired > 0
	assert sum(unspent) >= amountRequired
	spent = 0
	result = []
	for i in range(len(unspent)):
		result.append(i)
		spent += unspent[i]
		if spent >= amountRequired:
			return (result, spent)
	assert false
