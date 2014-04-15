import binascii
from SwapBill import RawTransaction
from SwapBill.Amounts import ToSatoshis

def CalculateRequired(rpcHost, rawTransactionHex):
	## calculates fee requirement based on code in litecoind at time of writing
	## assuming we want the transaction relayed independantly of litecoind priority calculations
	#assert type(rawTransactionHex) == str
	rawTransactionBytes = RawTransaction.FromHex(rawTransactionHex) ## note that we can count bytes more efficiently, and without dependency on RawTransaction, but this also checks input data validity
	byteSize = len(rawTransactionBytes)
	multiplier = (1 + int(byteSize / 1000))
	decodedTX = rpcHost.call('decoderawtransaction', rawTransactionHex)
	for out in decodedTX['vout']:
		if ToSatoshis(out['value']) < 100000: ## soft dust limit
			multiplier += 1
	return multiplier * 100000

def CalculatePaid(rpcHost, rawTransactionHex):
	#assert type(rawTransactionHex) == str
	decodedTX = rpcHost.call('decoderawtransaction', rawTransactionHex)
	inputAmount = 0
	for txIn in decodedTX['vin']:
		inputTX = rpcHost.call('getrawtransaction', txIn['txid'], 1)
		spentOutput = inputTX['vout'][txIn['vout']]
		inputAmount += ToSatoshis(spentOutput['value'])
	outputAmount = 0
	for txOut in decodedTX['vout']:
		outputAmount += ToSatoshis(txOut['value'])
	return inputAmount - outputAmount

def TransactionFeeIsSufficient(rpcHost, rawTransactionHex):
	#assert type(rawTransactionHex) == str
	feePaid = CalculatePaid(rpcHost, rawTransactionHex)
	return feePaid >= CalculateRequired(rpcHost, rawTransactionHex)

dustLimit = 100000
baseFee = 100000
feeIncrement = 100000
