from __future__ import print_function
import sys, argparse, binascii, traceback, struct
import csv
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import RPC, RawTransaction, Address, TransactionFee, ScriptPubKeyLookup
from SwapBill import TransactionTypes, BuildHostedTransaction, GetUnspent, Sync, ParseConfig
from SwapBill.Sync import SyncAndReturnState
from SwapBill.Amounts import ToSatoshis, FromSatoshis
PY3 = sys.version_info.major > 2

config_file = path.join(path.expanduser("~"), '.litecoin', 'litecoin.conf')

with open(config_file, mode='rb') as f:
	configFileBuffer = f.read()

clientConfig = ParseConfig.Parse(configFileBuffer)

## RPC HOST
try:
	RPC_HOST = clientConfig['externalip']
except KeyError:
	RPC_HOST = 'localhost'

## RPC PORT
try:
	RPC_PORT = clientConfig['rpcport']
except KeyError:
	RPC_PORT = 19332

assert int(RPC_PORT) > 1 and int(RPC_PORT) < 65535

## RPC USER
try:
	RPC_USER = clientConfig['rpcuser']
except KeyError:
	RPC_USER = 'rpcuser'

## RPC PASSWORD
try:
	RPC_PASSWORD = clientConfig['rpcpassword']
except KeyError:
	RPC_PASSWORD = 'rpcpass'

rpcHost = RPC.Host('http://' + RPC_USER + ':' + RPC_PASSWORD + '@' + RPC_HOST + ':' + str(RPC_PORT))

spendTXID = sys.argv[1]
spendVOut = int(sys.argv[2])
spendTX = rpcHost.call('getrawtransaction', spendTXID, 1)
blockHash = spendTX['blockhash']

#transactionsSince = rpcHost.call('listsinceblock', blockHash)['transactions']
#for txInfo in transactionsSince:
	#tx = rpcHost.call('getrawtransaction', txInfo['txid'], 1)
	#for txIn in tx['vin']:
		#print(txIn)
		#if not 'coinbase' in txIn and txIn['txid'] == spendTXID and txIn['vout'] == spendVOut:
			#print("spent by ", txIn['txid'])
			#exit()


while True:
	block = rpcHost.call('getblock', blockHash)
	for txHash in block['tx'][1:]: ## skip coinbase transactions
		tx = rpcHost.call('getrawtransaction', txHash, 1)
		for txIn in tx['vin']:
			if txIn['txid'] == spendTXID and txIn['vout'] == spendVOut:
				print("spent by ", tx['txid'])
				exit()
	if not 'nextblockhash' in block:
		break
	blockHash = block['nextblockhash']



##... can do this much more directly, without using BlockChain.Tracker
#config.startBlockHash = blockHash
#config.startBlockIndex = rpcHost.call('getblock', blockHash)['height']
#tracker = BlockChain.Tracker(config, rpcHost)
#currentChainSince = [blockHash]
#while True:
	#increment = tracker.update(config, rpcHost)
	#if increment == 0:
		#break
	#if increment == -1:
		#currentChainSince = currentChainSince[:-1]
	#else:
		#assert increment == 1
		#currentChainSince.append(tracker.currentHash())

#currentChainSince = ['2eba420de998e73a62a976c0e306f9cd98f35e7a13d7fed765342adb836c4114']

#print("Checking all transaction in currently reported best chain")
#print("chain start:", currentChainSince[0])
#print("chain end:", currentChainSince[-1])
#print("chain length:", len(currentChainSince))

#for h in currentChainSince[::-1]:
	#block = rpcHost.call('getblock', h)
	#for txHash in block['tx'][1:]: ## skip coinbase transactions
		#tx = rpcHost.call('getrawtransaction', txHash, 1)
		#for txIn in tx['vin']:
			#if txIn['txid'] == spendTXID and txIn['vout'] == spendVOut:
				#print("spent by ", tx['txid'])
				#exit()

print("No spent found in transactions in currently reported best chain")
