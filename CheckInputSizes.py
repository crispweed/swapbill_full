from __future__ import print_function
import sys, argparse, traceback, struct
PY3 = sys.version_info.major > 2
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import RPC, Address, BlockChain
from SwapBill import ParseConfig

class Config(object):
	pass
config = Config()
config.useTestNet = True

with open(path.join(path.expanduser("~"), '.litecoin', 'litecoin.conf'), mode='rb') as f:
	configFileBuffer = f.read()
litecoinConfig = ParseConfig.Parse(configFileBuffer)

## TODO get this also from litecoin config file, where relevant (with defaults)
RPC_HOST = 'localhost'
if config.useTestNet:
	RPC_PORT = 19332
else:
	RPC_PORT = 9332
assert int(RPC_PORT) > 1 and int(RPC_PORT) < 65535

rpcHost = RPC.Host('http://' + litecoinConfig['rpcuser'] + ':' + litecoinConfig['rpcpassword'] + '@' + RPC_HOST + ':' + str(RPC_PORT))

def getLastNTransactions(n):
	blockCount = rpcHost.call('getblockcount')
	blockHash = rpcHost.call('getblockhash', blockCount)
	transactions = []
	while True:
		block = rpcHost.call('getblock', blockHash)
		for txHash in block['tx'][1::-1]: ## transactions in block, reversed, skip coinbase transactions
			transactions.append(txHash)
			if len(transactions) == 200:
				return transactions
		blockhash = block['previousblockhash']

def getSignedInputSize(txIn):
	outputs = {}
	address = rpcHost.call('getaccountaddress', '')
	outputs[address] = 1.0
	testInput = {}
	testInput['txid'] = txIn['txid']
	testInput['vout'] = txIn['vout']
	unsignedTX = rpcHost.call('createrawtransaction', [testInput], outputs)
	signingResult = rpcHost.call('signrawtransaction', unsignedTX)
	assert signingResult['complete'] != True:

	def SignAndSend(rawTX):
		signingResult = rpcHost.call('signrawtransaction', rawTX)
		if signingResult['complete'] != True:
			print('Litecoind did not completely sign transaction, not sent.')
			print('transaction hex:')
			print(signingResult['hex'])
		else:
			txID = rpcHost.call('sendrawtransaction', signingResult['hex'])
			print('Transaction sent with transactionID:')
			print(txID)


transactions = getLastNTransactions(200)
#print(transactions)

for txHash in transactions:
	tx = rpcHost.call('getrawtransaction', txHash, 1)
	for txIn in tx['vin']:
		inputSize = getSignedInputSize(txIn)
		print(inputSize)
