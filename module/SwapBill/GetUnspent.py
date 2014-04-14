from SwapBill.Amounts import ToSatoshis
from SwapBill import Address

def AllNonSwapBill(addressVersion, rpcHost, swapBillBalances):
	allUnspent = rpcHost.call('listunspent')
	amounts = []
	asInputs = []
	for output in allUnspent:
		if not 'address' in output: ## is this check required?
			continue
		address = output['address']
		pubKeyHash = Address.ToPubKeyHash(addressVersion, address)
		if not pubKeyHash in swapBillBalances:
			amounts.append(ToSatoshis(output['amount']))
			asInputs.append((output['txid'], output['vout'], output['scriptPubKey']))
	return amounts, asInputs

def SingleForAddress(addressVersion, rpcHost, pubKeyHash):
	allUnspent = rpcHost.call('listunspent')
	for output in allUnspent:
		if not 'address' in output: ## is this check required?
			continue
		address = output['address']
		outputPubKeyHash = Address.ToPubKeyHash(addressVersion, address)
		if outputPubKeyHash == pubKeyHash:
			amount = ToSatoshis(output['amount'])
			asInput = (output['txid'], output['vout'], output['scriptPubKey'])
			return amount, asInput
	return None
