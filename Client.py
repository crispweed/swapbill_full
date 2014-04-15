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

parser = argparse.ArgumentParser(prog='SwapBillClient', description='the reference implementation of the SwapBill protocol')
#parser.add_argument('-V', '--version', action='version', version="SwapBillClient version %s" % config.clientVersion)
parser.add_argument('--config-file', help='the location of the configuration file')
subparsers = parser.add_subparsers(dest='action', help='the action to be taken')

sp = subparsers.add_parser('burn', help='destroy litecoin to create swapbill')
sp.add_argument('--quantity', required=True, help='quantity of LTC to be destroyed (in LTC satoshis)')

sp = subparsers.add_parser('transfer', help='move swapbill from one swapbill balance to another')
sp.add_argument('--fromAddress', required=True, help='pay from this address')
sp.add_argument('--quantity', required=True, help='quantity of swapbill to be paid (in swapbill satoshis)')
sp.add_argument('--toAddress', required=True, help='pay to this address')

sp = subparsers.add_parser('post_ltc_buy', help='make an offer to buy litecoin with swapbill')
sp.add_argument('--fromAddress', required=True, help='the address to fund the offer')
sp.add_argument('--quantity', required=True, help='amount of swapbill offered')
sp.add_argument('--exchangeRate', required=True, help='the exchange rate (positive integer, SWP/LTC * 0x100000000, must be less than 0x100000000)')
#sp.add_argument('--offerDuration', required=True, help='the number of blocks (from transaction maxBlock) for which the offer should remain valid')

sp = subparsers.add_parser('post_ltc_sell', help='make an offer to sell litecoin for swapbill')
sp.add_argument('--fromAddress', required=True, help='the address to fund the offer')
sp.add_argument('--quantity', required=True, help='amount of swapbill to buy (deposit of 1/16 of this amount will be paid in to the offer)')
sp.add_argument('--exchangeRate', required=True, help='the exchange rate SWP/LTC (must be greater than 0 and less than 1)')
#sp.add_argument('--offerDuration', required=True, help='the number of blocks (from transaction maxBlock) for which the offer should remain valid')

sp = subparsers.add_parser('complete_ltc_sell', help='complete an ltc exchange by fulfilling a pending exchange payment')
sp.add_argument('--pending_exchange_id', required=True, help='the id of the pending exchange payment to fulfill')

subparsers.add_parser('show_balances', help='show current SwapBill balances')
subparsers.add_parser('show_my_balances', help='show current SwapBill balances owned by server wallet')
#subparsers.add_parser('show_balances_no_update', help='show current SwapBill balances (without initial sync)')
subparsers.add_parser('show_offers', help='show current SwapBill exchange offers')
subparsers.add_parser('show_pending_exchanges', help='show current SwapBill pending exchange payments')

args = parser.parse_args()

## Read custom configuration file
if args.config_file == None:        
        args.config_file = path.join(path.expanduser("~"), '.litecoin', 'litecoin.conf')    

## Open config
try:        
        with open(args.config_file, mode='rb') as f:
                configFileBuffer = f.read()
except FileNotFoundError:        
        configFileBuffer = b''

clientConfig = ParseConfig.Parse(configFileBuffer)

## testnet address version (so bitcoin testnet, but looks like this also works for litecoin testnet)
## TODO: set this up dependant on config.useTestNet
config.addressVersion = b'\x6f'

## RPC HOST
try:        
        RPC_HOST = clientConfig['externalip']
except KeyError:
        RPC_HOST = 'localhost'

## RPC PORT
try:
        RPC_PORT = clientConfig['rpcport']
except KeyError:
        if config.useTestNet:
                RPC_PORT = 19332
        else:
                RPC_PORT = 9332

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

print("current litecoind block count = {}".format(rpcHost.call('getblockcount')))

def CheckAndReturnPubKeyHash(address):
	try:
		pubKeyHash = Address.ToPubKeyHash(config.addressVersion, address)
	except Address.BadAddress as e:
		print('Bad address:', address)
		print(e)
		exit()
	return pubKeyHash

class SigningFailed(Exception):
	pass
class InsufficientTransactionFees(Exception):
	pass

def CreateSignAndSend(tx, scriptPubKeyLookup):
	unsignedData = RawTransaction.Create(tx, scriptPubKeyLookup)
	unsignedHex = RawTransaction.ToHex(unsignedData)
	#signingResult = rpcHost.call('signrawtransaction_simplified', unsignedHex)
	signingResult = rpcHost.call('signrawtransaction', unsignedHex)
	if signingResult['complete'] != True:
			raise SigningFailed()
	signedHex = signingResult['hex']
	if not TransactionFee.TransactionFeeIsSufficient(rpcHost, signedHex):
		raise InsufficientTransactionFees()
	txID = rpcHost.call('sendrawtransaction', signedHex)
	print('Transaction sent with transactionID:')
	print(txID)

def CheckAndSend_FromAddress(tx):
	state = SyncAndReturnState(config, rpcHost)
	source = tx.source
	if hasattr(tx, 'consumedAmount'):
		requiredAmount = tx.consumedAmount()
	else:
		requiredAmount = tx.amount
	if not source in state._balances or state._balances[source] < requiredAmount:
		print('Insufficient swapbill balance for source address.')
		exit()
	sourceSingleUnspent = GetUnspent.SingleForAddress(config.addressVersion, rpcHost, source)
	if sourceSingleUnspent == None:
		print('No unspent outputs reported by litecoind for the specified from address.')
		print("This could be because a transaction is in progress and needs to be confirmed (in which case you may just need to wait)," +
		      " or it's also possible that all litecoin seeded to this address has been spent (in which case you will need to reseed).")
		exit()
	backerUnspent = GetUnspent.AllNonSwapBill(config.addressVersion, rpcHost, state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(backerUnspent[1], sourceSingleUnspent[1])
	change = Address.ToPubKeyHash(config.addressVersion, rpcHost.call('getnewaddress'))
	print('attempting to send swap bill transaction:', tx)
	transactionFee = TransactionFee.baseFee
	try:
		litecoinTX = BuildHostedTransaction.Build_WithSourceAddress(TransactionFee.dustLimit, transactionFee, tx, sourceSingleUnspent, backerUnspent, change)
		CreateSignAndSend(litecoinTX, scriptPubKeyLookup)
	except InsufficientTransactionFees:
		try:
			transactionFee += TransactionFee.feeIncrement
			litecoinTX = BuildHostedTransaction.Build_WithSourceAddress(TransactionFee.dustLimit, transactionFee, tx, sourceSingleUnspent, backerUnspent, change)
			CreateSignAndSend(litecoinTX, scriptPubKeyLookup)
		except InsufficientTransactionFees:
			print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
	except SigningFailed:
		print("Failed: Transaction could not be signed (source address not in wallet?)")


if args.action == 'burn':
	state = SyncAndReturnState(config, rpcHost)
	unspent = GetUnspent.AllNonSwapBill(config.addressVersion, rpcHost, state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
	target = Address.ToPubKeyHash(config.addressVersion, rpcHost.call('getnewaddress', 'SwapBill'))
	burnTX = TransactionTypes.Burn()
	burnTX.init_FromUserRequirements(burnAmount=int(args.quantity), target=target)
	change = Address.ToPubKeyHash(config.addressVersion, rpcHost.call('getnewaddress'))
	print('attempting to send swap bill transaction:', burnTX)
	transactionFee = TransactionFee.baseFee
	try:
		litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, burnTX, unspent, change)
		CreateSignAndSend(litecoinTX, scriptPubKeyLookup)
	except InsufficientTransactionFees:
		try:
			transactionFee += TransactionFee.feeIncrement
			litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, burnTX, unspent, change)
			CreateSignAndSend(litecoinTX, scriptPubKeyLookup)
		except InsufficientTransactionFees:
			print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
	except SigningFailed:
		print("Failed: Transaction could not be signed")
	except BuildHostedTransaction.ControlAddressBelowDustLimit:
		print("Failed: Burn quantity is below configured dust limit")

elif args.action == 'transfer':
	source = CheckAndReturnPubKeyHash(args.fromAddress)
	destination = CheckAndReturnPubKeyHash(args.toAddress)
	transferTX = TransactionTypes.Transfer()
	## TODO: add arg for block validity limit
	transferTX.init_FromUserRequirements(source=source, amount=int(args.quantity), destination=destination)
	CheckAndSend_FromAddress(transferTX)

elif args.action == 'post_ltc_buy':
	source = CheckAndReturnPubKeyHash(args.fromAddress)
	receivingDestination = Address.ToPubKeyHash(config.addressVersion, rpcHost.call('getnewaddress', 'SwapBill'))
	exchangeRate = int(float(args.exchangeRate) * 0x100000000)
	## TODO: add args for block validity limit and offer duration
	tx = TransactionTypes.LTCBuyOffer()
	tx.init_FromUserRequirements(source=source, swapBillAmountOffered=int(args.quantity), exchangeRate=exchangeRate, receivingDestination=receivingDestination)
	CheckAndSend_FromAddress(tx)

elif args.action == 'post_ltc_sell':
	source = CheckAndReturnPubKeyHash(args.fromAddress)
	exchangeRate = int(float(args.exchangeRate) * 0x100000000)
	## TODO: add args for block validity limit and offer duration
	tx = TransactionTypes.LTCSellOffer()
	swapBillToBuy=int(args.quantity)
	tx.init_FromUserRequirements(source=source, swapBillDesired=swapBillToBuy, exchangeRate=exchangeRate)
	CheckAndSend_FromAddress(tx)

elif args.action == 'complete_ltc_sell':
	state = SyncAndReturnState(config, rpcHost)
	pendingExchangeID = int(args.pending_exchange_id)
	if not pendingExchangeID in state._pendingExchanges:
		print('No pending exchange with the specified ID.')
		exit()
	exchange = state._pendingExchanges[pendingExchangeID]
	unspent = GetUnspent.AllNonSwapBill(config.addressVersion, rpcHost, state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
	target = Address.ToPubKeyHash(config.addressVersion, rpcHost.call('getnewaddress', 'SwapBill'))
	tx = TransactionTypes.LTCExchangeCompletion()
	tx.init_FromUserRequirements(ltcAmount=exchange.ltc, destination=exchange.ltcReceiveAddress, pendingExchangeIndex=pendingExchangeID)
	change = Address.ToPubKeyHash(config.addressVersion, rpcHost.call('getnewaddress'))
	print('attempting to send swap bill transaction:', tx)
	transactionFee = TransactionFee.baseFee
	try:
		litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, tx, unspent, change)
		CreateSignAndSend(litecoinTX, scriptPubKeyLookup)
	except InsufficientTransactionFees:
		try:
			transactionFee += TransactionFee.feeIncrement
			litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, tx, unspent, change)
			CreateSignAndSend(litecoinTX, scriptPubKeyLookup)
		except InsufficientTransactionFees:
			print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
	except SigningFailed:
		print("Failed: Transaction could not be signed")
	except BuildHostedTransaction.ControlAddressBelowDustLimit:
		print("Failed: payment quantity is below configured dust limit (but then this pending exchange should not have been added!)")

elif args.action == 'show_balances':
	state = SyncAndReturnState(config, rpcHost)
	print('all balances:')
	totalSpendable = 0
	for pubKeyHash in state._balances:
		address = Address.FromPubKeyHash(config.addressVersion, pubKeyHash)
		balance = state._balances[pubKeyHash]
		print(address + ': ' + str(balance))
		totalSpendable += balance
	print('total spendable swap bill satoshis: ' + str(totalSpendable))
	print('total swap bill satoshis created:   ' + str(state._totalCreated))

elif args.action == 'show_offers':
	state = SyncAndReturnState(config, rpcHost)
	state.printOffers()

elif args.action == 'show_pending_exchanges':
	state = SyncAndReturnState(config, rpcHost)
	state.printPendingExchanges()

#elif args.action == 'show_balances_no_update':
	#state = Sync.LoadAndReturnStateWithoutUpdate(config)
	#print('current account balances:', state._balances)
	#print('total swap bill satoshis created: ' + str(state._totalCreated))

elif args.action == 'show_my_balances':
	state = SyncAndReturnState(config, rpcHost)
	print('my balances:')
	totalSpendable = 0
	for pubKeyHash in state._balances:
		address = Address.FromPubKeyHash(config.addressVersion, pubKeyHash)
		validateResults = rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			balance = state._balances[pubKeyHash]
			print(address + ': ' + str(balance))
			totalSpendable += balance
	print('total spendable swap bill satoshis: ' + str(totalSpendable))

elif args.action == 'show_pending_exchanges':
	state = SyncAndReturnState(config, rpcHost)
	state.printPendingExchanges()

else:
	parser.print_help()
