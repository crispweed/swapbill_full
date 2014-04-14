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

class Config(object):
	pass
config = Config()
config.blocksBehindForCachedState = 20
config.useTestNet = True
config.startBlockIndex = 241432
## from: litecoind -testnet getblockhash 241432
config.startBlockHash = '3fa2cf2d644b74b7f6407a1d3a9d15ad98f85da9adecbac0b1560c11c0393eed'

## testnet address version (so bitcoin testnet, but looks like this also works for litecoin testnet)
## TODO: set this up dependant on config.useTestNet
config.addressVersion = b'\x6f'

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

unspent = GetUnspent.AllNonSwapBill(config.addressVersion, rpcHost, {})
scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
destination = Address.ToPubKeyHash(config.addressVersion, 'mnwNZCyvCKkEycX86UmugTfM2V7pRzxGWu')
burnTX = TransactionTypes.Burn()
burnTX.init_FromUserRequirements(burnAmount=100000, target=destination)
change = destination
transactionFee = TransactionFee.baseFee
litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, burnTX, unspent, change)
unsignedData = RawTransaction.Create(litecoinTX, scriptPubKeyLookup)
unsignedHex = RawTransaction.ToHex(unsignedData)
signingResult = rpcHost.call('signrawtransaction_simplified', unsignedHex)
print(signingResult)
