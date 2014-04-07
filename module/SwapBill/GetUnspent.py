from SwapBill.Amounts import ToSatoshis

def AllNonSwapBill(rpcHost, swapBillBalances):
	allUnspent = rpcHost.call('listunspent')
	amounts = []
	asInputs = []
	for output in allUnspent:
		if not 'address' in output: ## is this check required?
			continue
		if not output['address'] in swapBillBalances:
			amounts.append(ToSatoshis(output['amount']))
			asInputs.append((output['txid'], output['vout'], output['scriptPubKey']))
	return amounts, asInputs

def SingleForAddress(rpcHost, address):
	allUnspent = rpcHost.call('listunspent')
	for output in allUnspent:
		if not 'address' in output: ## is this check required?
			continue
		if output['address'] == address:
			amount = ToSatoshis(output['amount'])
			asInput = (output['txid'], output['vout'], output['scriptPubKey'])
			return amount, asInput
	return None
