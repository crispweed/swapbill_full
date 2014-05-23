from __future__ import print_function
import sys, argparse, binascii, traceback, struct, time
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from os import path
from SwapBill import RawTransaction, Address, TransactionFee
from SwapBill import TransactionEncoding, BuildHostedTransaction, Sync, Host, TransactionBuildLayer
from SwapBill import FormatTransactionForUserDisplay
from SwapBill.Sync import SyncAndReturnStateAndOwnedAccounts
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

class BadAddressArgument(ExceptionReportedToUser):
	def __init__(self, address):
		self._address = address
	def __str__(self):
		return 'An address argument is not valid (' + self._address + ').'
class BadAmountArgument(ExceptionReportedToUser):
	pass
class TransactionNotSuccessfulAgainstCurrentState(ExceptionReportedToUser):
	pass
class SourceAddressUnseeded(ExceptionReportedToUser):
	pass

parser = argparse.ArgumentParser(prog='SwapBillClient', description='the reference implementation of the SwapBill protocol')
#parser.add_argument('-V', '--version', action='version', version="SwapBillClient version %s" % config.clientVersion)
parser.add_argument('--configfile', help='the location of the configuration file')
parser.add_argument('--datadir', help='the location of the data directory', default='.')
subparsers = parser.add_subparsers(dest='action', help='the action to be taken')

sp = subparsers.add_parser('burn', help='destroy litecoin to create swapbill')
sp.add_argument('--quantity', required=True, help='quantity of LTC to be destroyed (in LTC satoshis)')

sp = subparsers.add_parser('pay', help='make a swapbill payment')
sp.add_argument('--quantity', required=True, help='quantity of swapbill to be paid (in swapbill satoshis)')
sp.add_argument('--toAddress', required=True, help='pay to this address')
sp.add_argument('--blocksUntilExpiry', type=int, default=8, help='if the transaction takes longer than this to go through then the transaction expires (in which case no payment is made and the full amount is returned as change)')

sp = subparsers.add_parser('post_ltc_buy', help='make an offer to buy litecoin with swapbill')
sp.add_argument('--quantity', required=True, help='amount of swapbill offered')
sp.add_argument('--exchangeRate', required=True, help='the exchange rate (positive integer, SWP/LTC * 0x100000000, must be less than 0x100000000)')
sp.add_argument('--blocksUntilExpiry', type=int, default=200, help='after this block the offer expires (and swapbill remaining in any unmatched part of the offer is returned)')

sp = subparsers.add_parser('post_ltc_sell', help='make an offer to sell litecoin for swapbill')
sp.add_argument('--quantity', required=True, help='amount of swapbill to buy (deposit of 1/16 of this amount will be paid in to the offer)')
sp.add_argument('--exchangeRate', required=True, help='the exchange rate SWP/LTC (must be greater than 0 and less than 1)')
sp.add_argument('--blocksUntilExpiry', type=int, default=200, help='after this block the offer expires (and swapbill remaining in any unmatched part of the offer is returned)')

sp = subparsers.add_parser('complete_ltc_sell', help='complete an ltc exchange by fulfilling a pending exchange payment')
sp.add_argument('--pending_exchange_id', required=True, help='the id of the pending exchange payment to fulfill')

subparsers.add_parser('collect', help='combine all current owned swapbill outputs into active account')

subparsers.add_parser('get_receive_address', help='generate a new key pair for the swapbill wallet and display the corresponding public payment address')

sp = subparsers.add_parser('get_balance', help='get current SwapBill balance')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

sp = subparsers.add_parser('get_buy_offers', help='get list of currently active litecoin buy offers')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

sp = subparsers.add_parser('get_sell_offers', help='get list of currently active litecoin sell offers')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

sp = subparsers.add_parser('get_pending_exchanges', help='get current SwapBill pending exchange payments')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

sp = subparsers.add_parser('get_state_info', help='get some general state information')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

def Main(startBlockIndex, startBlockHash, useTestNet, commandLineArgs=sys.argv[1:], host=None, out=sys.stdout):
	args = parser.parse_args(commandLineArgs)

	if not path.isdir(args.datadir):
		raise ExceptionReportedToUser("The following path (specified for data directory parameter) is not a valid path to an existing directory: " + args.datadir)

	if host is None:
		host = Host.Host(useTestNet=useTestNet, dataDirectory=args.datadir, configFile=args.configfile)
		print("current litecoind block count = {}".format(host._rpcHost.call('getblockcount')), file=out)

	includePending = hasattr(args, 'includepending') and args.includepending

	if args.action == 'get_state_info':
		syncOut = io.StringIO()
		startTime = time.clock()
		state, ownedAccounts = SyncAndReturnStateAndOwnedAccounts(args.datadir, startBlockIndex, startBlockHash, host, includePending=includePending, out=syncOut)
		elapsedTime = time.clock() - startTime
		formattedBalances = {}
		for account in state._balances:
			key = host.formatAccountForEndUser(account)
			formattedBalances[key] = state._balances[account]
		info = {
		    'totalCreated':state._totalCreated,
		    'atEndOfBlock':state._currentBlockIndex - 1, 'balances':formattedBalances, 'syncOutput':syncOut.getvalue(),
		    'syncTime':elapsedTime,
		    'numberOfLTCBuyOffers':state._LTCBuys.size(),
		    'numberOfLTCSellOffers':state._LTCSells.size(),
		    'numberOfPendingExchanges':len(state._pendingExchanges),
		    'numberOfOwnedAccounts':len(ownedAccounts)
		}
		return info

	state, ownedAccounts = SyncAndReturnStateAndOwnedAccounts(args.datadir, startBlockIndex, startBlockHash, host, includePending=includePending, out=out)
	print("state updated to end of block {}".format(state._currentBlockIndex - 1), file=out)

	transactionBuildLayer = TransactionBuildLayer.TransactionBuildLayer(host, ownedAccounts)

	def SetFeeAndSend(baseTX, baseTXInputsAmount, unspent):
		change = host.getNewNonSwapBillAddress()
		transactionFee = TransactionFee.baseFee
		try:
			filledOutTX = BuildHostedTransaction.AddPaymentFeesAndChange(baseTX, baseTXInputsAmount, TransactionFee.dustLimit, transactionFee, unspent, change)
			return transactionBuildLayer.sendTransaction(filledOutTX)
		except Host.InsufficientTransactionFees:
			print("Transaction fee increased.")
			try:
				transactionFee += TransactionFee.feeIncrement
				filledOutTX = BuildHostedTransaction.AddPaymentFeesAndChange(baseTX, baseTXInputsAmount, TransactionFee.dustLimit, transactionFee, unspent, change)
				return transactionBuildLayer.sendTransaction(filledOutTX)
			except Host.InsufficientTransactionFees:
				raise Exception("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")

	def CheckAndSend(transactionType, outputs, outputPubKeys, details):
		canApply, errorText = state.checkTransaction(transactionType, outputs, details)
		if errorText != '':
			raise TransactionNotSuccessfulAgainstCurrentState('Transaction would not complete successfully against current state:', errorText)
		assert canApply
		change = host.getNewNonSwapBillAddress()
		print('attempting to send ' + FormatTransactionForUserDisplay.Format(host, transactionType, outputs, outputPubKeys, details), file=out)
		backingUnspent = transactionBuildLayer.getUnspent()
		baseTX = TransactionEncoding.FromStateTransaction(transactionType, outputs, outputPubKeys, details)
		baseInputsAmount = 0
		for i in range(baseTX.numberOfInputs()):
			txID = baseTX.inputTXID(i)
			vOut = baseTX.inputVOut(i)
			baseInputsAmount += ownedAccounts[(txID, vOut)][0]
		txID = SetFeeAndSend(baseTX, baseInputsAmount, backingUnspent)
		return {'transaction id':txID}

	def CheckAndReturnPubKeyHash(address):
		try:
			pubKeyHash = host.addressFromEndUserFormat(address)
		except Address.BadAddress as e:
			raise BadAddressArgument(address)
		return pubKeyHash

	if args.action == 'burn':
		if int(args.quantity) < TransactionFee.dustLimit:
			raise ExceptionReportedToUser('Burn amount is below dust limit.')
		transactionType = 'Burn'
		outputs = ('destination',)
		outputPubKeyHashes = (host.getNewSwapBillAddress(),)
		details = {'amount':int(args.quantity)}
		transactionBuildLayer.startTransactionConstruction()
		return CheckAndSend(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'pay':
		transactionType = 'Pay'
		outputs = ('change', 'destination')
		outputPubKeyHashes = (host.getNewSwapBillAddress(), CheckAndReturnPubKeyHash(args.toAddress))
		transactionBuildLayer.startTransactionConstruction()
		details = {
		    'sourceAccount':transactionBuildLayer.getActiveAccount(state),
		    'amount':int(args.quantity),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'post_ltc_buy':
		transactionType = 'LTCBuyOffer'
		outputs = ('change', 'refund')
		outputPubKeyHashes = (host.getNewSwapBillAddress(), host.getNewSwapBillAddress())
		transactionBuildLayer.startTransactionConstruction()
		details = {
		    'sourceAccount':transactionBuildLayer.getActiveAccount(state),
		    'swapBillOffered':int(args.quantity),
		    'exchangeRate':int(float(args.exchangeRate) * 0x100000000),
		    'receivingAddress':host.getNewNonSwapBillAddress(),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'post_ltc_sell':
		transactionType = 'LTCSellOffer'
		outputs = ('change', 'receiving')
		outputPubKeyHashes = (host.getNewSwapBillAddress(), host.getNewSwapBillAddress())
		transactionBuildLayer.startTransactionConstruction()
		details = {
		    'sourceAccount':transactionBuildLayer.getActiveAccount(state),
		    'swapBillDesired':int(args.quantity),
		    'exchangeRate':int(float(args.exchangeRate) * 0x100000000),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'complete_ltc_sell':
		transactionType = 'LTCExchangeCompletion'
		pendingExchangeID = int(args.pending_exchange_id)
		if not pendingExchangeID in state._pendingExchanges:
			raise ExceptionReportedToUser('No pending exchange with the specified ID.')
		exchange = state._pendingExchanges[pendingExchangeID]
		details = {
		    'pendingExchangeIndex':pendingExchangeID,
		    'destinationAddress':exchange.ltcReceiveAddress,
		    'destinationAmount':exchange.ltc
		}
		#print('complete_ltc_sell details:')
		#print(details)
		transactionBuildLayer.startTransactionConstruction()
		return CheckAndSend(transactionType, (), (), details)

	elif args.action == 'collect':
		transactionType = 'Collect'
		transactionBuildLayer.startTransactionConstruction()
		sourceAccounts = transactionBuildLayer.getAllOwnedAndSpendable(state)
		if len(sourceAccounts) < 2:
			raise ExceptionReportedToUser('There are currently less than two spendable swapbill outputs.')
		outputs = ('destination',)
		outputPubKeyHashes = (host.getNewSwapBillAddress(),)
		details = {'sourceAccounts':sourceAccounts}
		return CheckAndSend(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'get_receive_address':
		pubKeyHash = host.getNewSwapBillAddress()
		return {'receive_address': host.formatAddressForEndUser(pubKeyHash)}

	elif args.action == 'get_balance':
		total = 0
		activeAccountAmount = 0
		for account in ownedAccounts:
			if not account in state._balances:
				# e.g. zero amount account for ltc trading that got cleaned up
				continue
			amount = state._balances[account]
			total += amount
			if amount > activeAccountAmount:
				activeAccountAmount = amount
		return {'total':total, 'in active account':activeAccountAmount}

	elif args.action == 'get_buy_offers':
		result = []
		offers = state._LTCBuys.getSortedExchangeRateAndDetails()
		for exchangeRate, buyDetails in offers:
			#print('testing owned status for:', buyDetails.refundAccount[0][-3:], buyDetails.refundAccount[1])
			mine = buyDetails.refundAccount in ownedAccounts
			exchangeAmount = buyDetails.swapBillAmount
			rate_Double = float(exchangeRate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			result.append(('exchange rate', rate_Double, {'swapbill offered':exchangeAmount, 'ltc equivalent':ltc, 'mine':mine}))
		return result

	elif args.action == 'get_sell_offers':
		result = []
		offers = state._LTCSells.getSortedExchangeRateAndDetails()
		for exchangeRate, sellDetails in offers:
			mine = sellDetails.receivingAccount in ownedAccounts
			exchangeAmount = sellDetails.swapBillAmount
			depositAmount = sellDetails.swapBillDeposit
			rate_Double = float(exchangeRate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			result.append(('exchange rate', rate_Double, {'swapbill desired':exchangeAmount, 'deposit paid':depositAmount, 'ltc equivalent':ltc, 'mine':mine}))
		return result

	elif args.action == 'get_pending_exchanges':
		result = []
		for key in state._pendingExchanges:
			d = {}
			exchange = state._pendingExchanges[key]
			#d['ltc receive address'] = host.formatAddressForEndUser(exchange.ltcReceiveAddress)
			d['I am seller (and need to complete)'] = exchange.sellerReceivingAccount in ownedAccounts
			d['I am buyer (and waiting for payment)'] = exchange.buyerAddress in ownedAccounts
			d['deposit paid by seller'] = exchange.swapBillDeposit
			d['swap bill paid by buyer'] = exchange.swapBillAmount
			d['outstanding ltc payment amount'] = exchange.ltc
			d['expires on block'] = exchange.expiry
			result.append(('pending exchange index', key, d))
		return result

	else:
		parser.print_help()
