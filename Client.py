from __future__ import print_function
import sys, argparse, binascii, traceback, struct
try:
	import cPickle as pickle
except ImportError:
	import pickle
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
from SwapBill import RPC, BlockChain, BlockChainFollower, CreateRawTransaction, Address
from SwapBill import TransactionTypes, BuildHostedTransaction, GetUnspent, Sync
from SwapBill.Sync import SyncAndReturnState
from SwapBill.Amounts import ToSatoshis, FromSatoshis

class ReindexingRequiredException(Exception):
	pass

class Config(object):
	pass
config = Config()
config.clientVersion = 0.2
config.useTestNet = True
config.startBlockIndex = 241432
## from: litecoind -testnet getblockhash 241432
config.startBlockHash = '3fa2cf2d644b74b7f6407a1d3a9d15ad98f85da9adecbac0b1560c11c0393eed'
config.allowRewindMismatch = False

## (work out best value to use here)
## this is for payments to third parties, or to control address (so lost)
## we want the transaction to go through, while minimising actual amount
## based on reading litecoind source code it looks like there is no actual minimun output value being applied
config.dustOutputAmount = ToSatoshis(0.0000001)

## this stays under our control
## any value should work, as long as the transaction goes through
## but it is convenient if we can actually find the output again with litecoind listunspent
## without having to 'reseed'
## based on testing on litecoin testnet
## 0.000001 ltc unspent outputs don't seem to get included by litecoind wallet
## 0.00001 ltc unspent outputs do
config.seedAmount = ToSatoshis(0.00001)

config.minimumTransactionAmount = ToSatoshis(0.1) ## minimum weight for host transactions, this amount will be paid back as change
config.transactionFee = ToSatoshis(0.003) ##... work this out properly, e.g. look at what litecoind sets, make dependant on transaction size if relevant

## testnet address version (so bitcoin testnet, but looks like this also works for litecoin testnet)
## TODO: set this up dependant on config.useTestNet
config.addressVersion = b'\x6f'

## TODO get this info from litecoin config file
RPC_USER = '{ENTER_RPC_USER}'
RPC_PASSWORD = '{ENTER_RPC_PASSWORD}'
RPC_HOST = 'localhost'
if config.useTestNet:
	RPC_PORT = 19332
else:
	RPC_PORT = 9332
assert int(RPC_PORT) > 1 and int(RPC_PORT) < 65535

rpcHost = RPC.Host('http://' + RPC_USER + ':' + RPC_PASSWORD + '@' + RPC_HOST + ':' + str(RPC_PORT))

parser = argparse.ArgumentParser(prog='SwapBillClient', description='the reference implementation of the SwapBill protocol')
parser.add_argument('-V', '--version', action='version', version="SwapBillClient version %s" % config.clientVersion)
subparsers = parser.add_subparsers(dest='action', help='the action to be taken')

sp = subparsers.add_parser('burn', help='destroy litecoin to create swapbill')
sp.add_argument('--quantity', required=True, help='quantity of LTC to be destroyed (in LTC satoshis)')

sp = subparsers.add_parser('transfer', help='move swapbill from one swapbill balance to another')
sp.add_argument('--fromAddress', required=True, help='pay from this address')
sp.add_argument('--quantity', required=True, help='quantity of swapbill to be paid (in swapbill satoshis)')
sp.add_argument('--toAddress', required=True, help='pay to this address')

subparsers.add_parser('show_balances', help='show current SwapBill balances (after initial sync)')
subparsers.add_parser('show_balances_no_update', help='show current SwapBill balances (without initial sync)')
subparsers.add_parser('rewindOne', help='rewind past last block containing swapbill transactions, permissively (for debugging purposes)')

args = parser.parse_args()

print("current litecoind block count = {}".format(rpcHost.call('getblockcount')))

def CheckAddress(address):
	try:
		Address.ToData(config.addressVersion, address)
	except Address.BadAddress as e:
		print('Bad address:', address)
		print(e)
		exit()

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
def CreateSignAndSend(config, tx):
	inputs, targetAddresses, targetAmounts = tx
	rawTX = CreateRawTransaction.CreateRawTransaction(config, inputs, targetAddresses, targetAmounts)
	SignAndSend(rawTX.decode())

if args.action == 'burn':
	state = SyncAndReturnState(config, rpcHost)
	unspent = GetUnspent.AllNonSwapBill(rpcHost, state._balances)
	targetAddress = rpcHost.call('getnewaddress', 'SwapBill')
	CheckAddress(targetAddress)
	burnTX = TransactionTypes.Burn()
	burnTX.init_FromUserRequirements(burnAmount=int(args.quantity), targetAddress=targetAddress)
	changeAddress = rpcHost.call('getnewaddress')
	litecoinTX = BuildHostedTransaction.Build_FundedByAccount(config, burnTX, unspent, changeAddress, True)
	if not litecoinTX is None:
		CreateSignAndSend(config, litecoinTX)
		print('submitted swap bill transaction:', burnTX)

elif args.action == 'transfer':
	state = SyncAndReturnState(config, rpcHost)
	sourceAddress = args.fromAddress
	quantity = int(args.quantity)
	if not sourceAddress in state._balances or state._balances[sourceAddress] < quantity:
		print('Insufficient swapbill balance for source address.')
		exit()
	CheckAddress(sourceAddress)
	CheckAddress(args.toAddress)
	sourceAddressSingleUnspent = GetUnspent.SingleForAddress(rpcHost, sourceAddress)
	if sourceAddressSingleUnspent == None:
		print('No unspent outputs reported by litecoind for the specified from address.')
		print("This could be because a transaction is in progress and needs to be confirmed (in which case you may just need to wait)," +
			" or it's also possible that all litecoin seeded to this address has been spent (in which case you will need to reseed).")
		exit()
	backerUnspent = GetUnspent.AllNonSwapBill(rpcHost, state._balances)
	## TODO: add args for block validity limits
	transferTX = TransactionTypes.Transfer()
	transferTX.init_FromUserRequirements(fromAddress=sourceAddress, amount=quantity, toAddress=args.toAddress)
	changeAddress = rpcHost.call('getnewaddress')
	seedDestination = False ## (could be controlled by an argument)
	litecoinTX = BuildHostedTransaction.Build_WithSourceAddress(config, transferTX, sourceAddress, sourceAddressSingleUnspent, backerUnspent, changeAddress, seedDestination)
	if not litecoinTX is None:
		CreateSignAndSend(config, litecoinTX)
		print('submitted swap bill transaction:', transferTX)

elif args.action == 'show_balances':
	state = SyncAndReturnState(config, rpcHost)
	print('current account balances:', state._balances)
	print('total swap bill satoshis created: ' + str(state._totalCreated))

elif args.action == 'show_balances_no_update':
	state = Sync.LoadAndReturnStateWithoutUpdate(config)
	print('current account balances:', state._balances)
	print('total swap bill satoshis created: ' + str(state._totalCreated))

elif args.action == 'rewindOne':
	config.allowRewindMismatch = True
	state = Sync.RewindLastBlockWithTransactions(config, rpcHost)

else:
	parser.print_help()
