from __future__ import print_function
import sys, argparse, binascii, traceback, struct
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import RawTransaction, Address, TransactionFee, ScriptPubKeyLookup, Address
from SwapBill import TransactionTypes, BuildHostedTransaction, Sync, Host
from SwapBill.Sync import SyncAndReturnState
from SwapBill.Amounts import ToSatoshis, FromSatoshis
PY3 = sys.version_info.major > 2

class Config(object):
	pass
config = Config()
config.blocksBehindForCachedState = 20
#config.useTestNet = True
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

host = Host.Host(useTestNet=True, configFile=args.config_file)

print("current litecoind block count = {}".format(host._rpcHost.call('getblockcount')))
state = SyncAndReturnState(config, host)
print("state updated to end of block {}".format(state._currentBlockIndex - 1))

def CheckAndReturnPubKeyHash(address):
	try:
		pubKeyHash = Address.ToPubKeyHash(host._addressVersion, address)
	except Address.BadAddress as e:
		print('Bad address:', address)
		print(e)
		exit()
	return pubKeyHash

def CheckAndSend_FromAddress(tx):
	wouldSucceed, failReason = tx.checkWouldApplySuccessfully(state)
	if not wouldSucceed:
		print('Transaction would not complete successfully against current state:', failReason)
		exit()
	source = tx.source
	sourceSingleUnspent = host.getSingleUnspentForAddress(source)
	if sourceSingleUnspent == None:
		print('No unspent outputs reported by litecoind for the specified from address.')
		print("This could be because a transaction is in progress and needs to be confirmed (in which case you may just need to wait)," +
			  " or it's also possible that all litecoin seeded to this address has been spent (in which case you will need to reseed).")
		exit()
	backerUnspent = host.getNonSwapBillUnspent(state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(backerUnspent[1], sourceSingleUnspent[1])
	change = host.getNewChangeAddress()
	print('attempting to send swap bill transaction:', tx)
	transactionFee = TransactionFee.baseFee
	try:
		litecoinTX = BuildHostedTransaction.Build_WithSourceAddress(TransactionFee.dustLimit, transactionFee, tx, sourceSingleUnspent, backerUnspent, change)
		txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
	except InsufficientTransactionFees:
		try:
			transactionFee += TransactionFee.feeIncrement
			litecoinTX = BuildHostedTransaction.Build_WithSourceAddress(TransactionFee.dustLimit, transactionFee, tx, sourceSingleUnspent, backerUnspent, change)
			txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
		except InsufficientTransactionFees:
			print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
	except Host.SigningFailed:
		print("Failed: Transaction could not be signed (source address not in wallet?)")
	else:
		print('Transaction sent with transactionID:')
		print(txID)

if args.action == 'burn':
	target = host.getNewSwapBillAddress()
	burnTX = TransactionTypes.Burn()
	burnTX.init_FromUserRequirements(burnAmount=int(args.quantity), target=target)
	wouldSucceed, failReason = burnTX.checkWouldApplySuccessfully(state)
	if not wouldSucceed:
		print('Transaction would not complete successfully against current state:', failReason)
		exit()
	unspent = host.getNonSwapBillUnspent(state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
	change = host.getNewChangeAddress()
	print('attempting to send swap bill transaction:', burnTX)
	transactionFee = TransactionFee.baseFee
	try:
		litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, burnTX, unspent, change)
		txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
	except Host.InsufficientTransactionFees:
		try:
			transactionFee += TransactionFee.feeIncrement
			litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, burnTX, unspent, change)
			txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
		except Host.InsufficientTransactionFees:
			print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
	except Host.SigningFailed:
		print("Failed: Transaction could not be signed")
	except BuildHostedTransaction.ControlAddressBelowDustLimit:
		print("Failed: Burn quantity is below configured dust limit")
	else:
		print('Transaction sent with transactionID:')
		print(txID)

elif args.action == 'transfer':
	source = CheckAndReturnPubKeyHash(args.fromAddress)
	destination = CheckAndReturnPubKeyHash(args.toAddress)
	transferTX = TransactionTypes.Transfer()
	## TODO: add arg for block validity limit
	transferTX.init_FromUserRequirements(source=source, amount=int(args.quantity), destination=destination)
	CheckAndSend_FromAddress(transferTX)

elif args.action == 'post_ltc_buy':
	source = CheckAndReturnPubKeyHash(args.fromAddress)
	receivingDestination = host.getNewSwapBillAddress()
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
	pendingExchangeID = int(args.pending_exchange_id)
	if not pendingExchangeID in state._pendingExchanges:
		print('No pending exchange with the specified ID.')
		exit()
	exchange = state._pendingExchanges[pendingExchangeID]
	tx = TransactionTypes.LTCExchangeCompletion()
	tx.init_FromUserRequirements(ltcAmount=exchange.ltc, destination=exchange.ltcReceiveAddress, pendingExchangeIndex=pendingExchangeID)
	wouldSucceed, failReason = tx.checkWouldApplySuccessfully(state)
	if not wouldSucceed:
		print('Transaction would not complete successfully against current state:', failReason)
		exit()
	unspent = host.getNonSwapBillUnspent(state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
	change = host.getNewChangeAddress()
	print('attempting to send swap bill transaction:', tx)
	transactionFee = TransactionFee.baseFee
	try:
		litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, tx, unspent, change)
		txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
	except Host.InsufficientTransactionFees:
		try:
			transactionFee += TransactionFee.feeIncrement
			litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, tx, unspent, change)
			txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
		except InsufficientTransactionFees:
			print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
	except Host.SigningFailed:
		print("Failed: Transaction could not be signed")
	except BuildHostedTransaction.ControlAddressBelowDustLimit:
		print("Failed: payment quantity is below configured dust limit (but then this pending exchange should not have been added!)")
	else:
		print('Transaction sent with transactionID:')
		print(txID)

elif args.action == 'show_balances':
	print('all balances:')
	totalSpendable = 0
	for pubKeyHash in state._balances:
		address = Address.FromPubKeyHash(host._addressVersion, pubKeyHash)
		balance = state._balances[pubKeyHash]
		print(address + ': ' + str(balance))
		totalSpendable += balance
	print('total spendable swap bill satoshis: ' + str(totalSpendable))
	print('total swap bill satoshis created:   ' + str(state._totalCreated))

elif args.action == 'show_my_balances':
	addressesWithUnspent = host.getAddressesWithUnspent(state._balances)
	print('my balances:')
	totalSpendable = 0
	for pubKeyHash in state._balances:
		address = Address.FromPubKeyHash(host._addressVersion, pubKeyHash)
		validateResults = host._rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			balance = state._balances[pubKeyHash]
			line = address + ': ' + str(balance)
			if not pubKeyHash in addressesWithUnspent:
				line += ' (needs seeding)'
			print(line)
			totalSpendable += balance
	print('total spendable swap bill satoshis: ' + str(totalSpendable))

elif args.action == 'show_offers':
	print('Buy offers:')
	offers = state._LTCBuys.getSortedExchangeRateAndDetails()
	if len(offers) == 0:
		print('  (no buy offers)')
	for exchangeRate, buyDetails in offers:
		pubKeyHash = buyDetails.swapBillAddress
		exchangeAmount = buyDetails.swapBillAmount
		rate_Double = float(exchangeRate) / 0x100000000
		ltc = int(exchangeAmount * rate_Double)
		line = '  rate:{:.7f}, swapbill offered:{}, ltc equivalent:{}'.format(rate_Double, exchangeAmount, ltc)
		address = Address.FromPubKeyHash(host._addressVersion, pubKeyHash)
		validateResults = host._rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			line += ' (mine)'
		print(line)
	print('Sell offers:')
	offers = state._LTCSells.getSortedExchangeRateAndDetails()
	if len(offers) == 0:
		print('  (no sell offers)')
	for exchangeRate, sellDetails in offers:
		pubKeyHash = sellDetails.swapBillAddress
		exchangeAmount = sellDetails.swapBillAmount
		depositAmount = sellDetails.swapBillDeposit
		rate_Double = float(exchangeRate) / 0x100000000
		ltc = int(exchangeAmount * rate_Double)
		line = '  rate:{:.7f}, swapbill desired:{}, ltc equivalent:{}'.format(rate_Double, exchangeAmount, ltc)
		address = Address.FromPubKeyHash(host._addressVersion, pubKeyHash)
		validateResults = host._rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			line += ' (mine)'
		print(line)

elif args.action == 'show_pending_exchanges':
	print('Pending exchange completion payments:')
	if len(state._pendingExchanges) == 0:
		print('  (no pending completion payments)')
	for key in state._pendingExchanges:
		exchange = state._pendingExchanges[key]
		print(' key =', key, ':')
		address = Address.FromPubKeyHash(host._addressVersion, exchange.buyerAddress)
		line = '  buyer = ' + address
		validateResults = host._rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			line += ' (me)'
		print(line)
		address = Address.FromPubKeyHash(host._addressVersion, exchange.sellerAddress)
		line = '  seller = ' + address
		validateResults = host._rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			line += ' (me)'
		print(line)
		print('  swapBillAmount =', exchange.swapBillAmount)
		print('  swapBillDeposit =', exchange.swapBillDeposit)
		print('  ltc amount to pay =', exchange.ltc)
		address = Address.FromPubKeyHash(host._addressVersion, exchange.ltcReceiveAddress)
		line = '  pay ltc to = ' + address
		validateResults = host._rpcHost.call('validateaddress', address)
		if validateResults['ismine'] == True:
			line += ' (me)'
		print(line)
		print('  expires on block =', exchange.expiry)

else:
	parser.print_help()