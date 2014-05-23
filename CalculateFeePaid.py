from __future__ import print_function
import sys, argparse, binascii, traceback, struct
import csv
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import RPC, Address, BlockChain
import sys
PY3 = sys.version_info.major > 2

class Config(object):
	pass
config = Config()
config.useTestNet = True
## testnet address version (so bitcoin testnet, but looks like this also works for litecoin testnet)
## TODO: set this up dependant on config.useTestNet
config.addressVersion = b'\x6f'

configFileName = path.join(path.expanduser("~"), '.litecoin', 'litecoin.conf')
litecoinConfig = {}
open_kwargs = dict(mode='r', newline='') if PY3 else dict(mode='rb')
with open(configFileName, **open_kwargs) as csvfile:
	reader = csv.reader(csvfile, delimiter='=', escapechar='\\', quoting=csv.QUOTE_NONE)
	for row in reader:
		if len(row) != 2:
			raise Exception("Unexpected format for line in litecoin.conf: " + str(row))
		litecoinConfig[row[0]] = row[1]

## TODO get this also from litecoin config file, where relevant (with defaults)
RPC_HOST = 'localhost'
if config.useTestNet:
	RPC_PORT = 19332
else:
	RPC_PORT = 9332
assert int(RPC_PORT) > 1 and int(RPC_PORT) < 65535

rpcHost = RPC.Host('http://' + litecoinConfig['rpcuser'] + ':' + litecoinConfig['rpcpassword'] + '@' + RPC_HOST + ':' + str(RPC_PORT))

txID = sys.argv[1]
tx = rpcHost.call('getrawtransaction', txID, 1)

inputsAmount = 0
for txIn in tx['vin']:
	inputTX = rpcHost.call('getrawtransaction', txIn['txid'], 1)
	spentOutput = inputTX['vout'][txIn['vout']]
	inputAmount = spentOutput['value']
	print('  from', txIn['txid'] + ':' + str(txIn['vout']))
	print('  spent', str(inputAmount))
	inputsAmount += inputAmount
print('total spent:', inputsAmount)
outputsAmount = 0
for txOut in tx['vout']:
	print('  paid', str(txOut['value']))
	outputsAmount += txOut['value']
print('total paid:', outputsAmount)
print('fee:', inputsAmount - outputsAmount)
