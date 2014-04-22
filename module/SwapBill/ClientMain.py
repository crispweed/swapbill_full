from __future__ import print_function
import sys, argparse, binascii, traceback, struct, json
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from SwapBill import RawTransaction, Address, TransactionFee, GetUnspent
from SwapBill import TransactionTypes, BuildHostedTransaction, Sync, Host, TransactionBuildLayer
from SwapBill import FormatTransactionForUserDisplay
from SwapBill.Sync import SyncAndReturnState
from SwapBill.Amounts import ToSatoshis, FromSatoshis
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
parser.add_argument('--config-file', help='the location of the configuration file')
parser.add_argument('--cache-file', help='the location of the cache file')
subparsers = parser.add_subparsers(dest='action', help='the action to be taken')

sp = subparsers.add_parser('burn', help='destroy litecoin to create swapbill')
sp.add_argument('--quantity', required=True, help='quantity of LTC to be destroyed (in LTC satoshis)')

sp = subparsers.add_parser('pay', help='make a swapbill payment')
sp.add_argument('--quantity', required=True, help='quantity of swapbill to be paid (in swapbill satoshis)')
sp.add_argument('--toAddress', required=True, help='pay to this address')

sp = subparsers.add_parser('post_ltc_buy', help='make an offer to buy litecoin with swapbill')
sp.add_argument('--quantity', required=True, help='amount of swapbill offered')
sp.add_argument('--exchangeRate', required=True, help='the exchange rate (positive integer, SWP/LTC * 0x100000000, must be less than 0x100000000)')

sp = subparsers.add_parser('post_ltc_sell', help='make an offer to sell litecoin for swapbill')
sp.add_argument('--quantity', required=True, help='amount of swapbill to buy (deposit of 1/16 of this amount will be paid in to the offer)')
sp.add_argument('--exchangeRate', required=True, help='the exchange rate SWP/LTC (must be greater than 0 and less than 1)')

sp = subparsers.add_parser('complete_ltc_sell', help='complete an ltc exchange by fulfilling a pending exchange payment')
sp.add_argument('--pending_exchange_id', required=True, help='the id of the pending exchange payment to fulfill')

subparsers.add_parser('show_balance', help='show current SwapBill balance')
subparsers.add_parser('show_offers', help='show current SwapBill exchange offers')
subparsers.add_parser('show_pending_exchanges', help='show current SwapBill pending exchange payments')
subparsers.add_parser('print_state_info_json', help='outpt some state information in JSON format')

def Main(startBlockIndex, startBlockHash, commandLineArgs=sys.argv[1:], host=None, out=sys.stdout):
	args = parser.parse_args(commandLineArgs)

	if host is None:
		host = Host.Host(useTestNet=True, configFile=args.config_file)
		print("current litecoind block count = {}".format(host._rpcHost.call('getblockcount')), file=out)

	if args.action == 'print_state_info_json':
		syncOut = io.StringIO()
		state = SyncAndReturnState(args.cache_file, startBlockIndex, startBlockHash, host, out=syncOut)
		balancesByAddress = {}
		for pubKeyHash in state._balances:
			address = host.formatAddressForEndUser(pubKeyHash)
			balancesByAddress[address] = state._balances[pubKeyHash]
		info = {
		    'atEndOfBlock':state._currentBlockIndex - 1, 'balances':balancesByAddress, 'syncOutput':syncOut.getvalue(),
		    'numberOfLTCBuyOffers':state._LTCBuys.size(),
		    'numberOfLTCSellOffers':state._LTCSells.size(),
		    'numberOfPendingExchanges':len(state._pendingExchanges)
		}
		print(json.dumps(info), file=out)
		return

	state = SyncAndReturnState(args.cache_file, startBlockIndex, startBlockHash, host, out=out)
	print("state updated to end of block {}".format(state._currentBlockIndex - 1), file=out)

	transactionBuildLayer = TransactionBuildLayer.TransactionBuildLayer(host)

	def SetFeeAndSend(sourceLookup, baseTX, unspent):
		change = host.getNewNonSwapBillAddress()
		transactionFee = TransactionFee.baseFee
		#if hasattr(sourceLookup, '_asInput'):
			#print(sourceLookup._asInput)
			#print(sourceLookup._amount)
		#print(unspent)
		#print(baseTX.__dict__)
		try:
			filledOutTX = BuildHostedTransaction.AddPaymentFeesAndChange(baseTX, sourceLookup, TransactionFee.dustLimit, transactionFee, unspent, change)
			#print(filledOutTX.__dict__)
			return transactionBuildLayer.sendTransaction(filledOutTX)
		except Host.InsufficientTransactionFees:
			print("Transaction fee increased.")
			try:
				transactionFee += TransactionFee.feeIncrement
				filledOutTX = BuildHostedTransaction.AddPaymentFeesAndChange(baseTX, sourceLookup, TransactionFee.dustLimit, transactionFee, unspent, change)
				return transactionBuildLayer.sendTransaction(filledOutTX)
			except Host.InsufficientTransactionFees:
				raise Exception("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")

	def CheckAndSend(transactionType, details):
		canApply, errorText = state.checkTransaction(transactionType, details)
		if errorText != '':
			raise TransactionNotSuccessfulAgainstCurrentState('Transaction would not complete successfully against current state:', errorText)
		assert canApply
		change = host.getNewNonSwapBillAddress()
		print('attempting to send ' + FormatTransactionForUserDisplay.Format(host, transactionType, details), file=out)
		unspent, sourceLookup = GetUnspent.GetUnspent(transactionBuildLayer, state._balances)
		#print(FormatTransactionForUserDisplay.Format(host, tx), file=out)
		baseTX = TransactionTypes.FromStateTransaction(transactionType, details, sourceLookup)
		decodedType, decodedDetails = TransactionTypes.ToStateTransaction(sourceLookup, baseTX)
		assert decodedType == transactionType
		assert decodedDetails == details
		txID = SetFeeAndSend(sourceLookup, baseTX, unspent)
		print('Transaction sent with transactionID:', file=out)
		print(txID, file=out)

	def CheckAndReturnPubKeyHash(address):
		try:
			pubKeyHash = host.addressFromEndUserFormat(address)
		except Address.BadAddress as e:
			raise BadAddressArgument(address)
		return pubKeyHash

	def GetActiveAccount():
		result = None
		unspent, sourceLookup = GetUnspent.GetUnspent(transactionBuildLayer, state._balances)
		for pubKeyHash in state._balances:
			if not host.addressIsMine(pubKeyHash):
				continue
			if not sourceLookup.addressIsSeeded(pubKeyHash):
				continue
			if result is None or state._balances[pubKeyHash] > state._balances[result]:
				result = pubKeyHash
		return result

	if args.action == 'burn':
		transactionType = 'Burn'
		details = {'amount':int(args.quantity), 'destinationAccount':host.getNewSwapBillAddress()}
		CheckAndSend(transactionType, details)

	elif args.action == 'pay':
		transactionType = 'Pay'
		details = {
		    'sourceAccount':GetActiveAccount(),
		    'changeAccount':host.getNewSwapBillAddress(),
		    'amount':int(args.quantity),
		    'destinationAccount':CheckAndReturnPubKeyHash(args.toAddress),
		    'maxBlock':0xffffffff
		}
		CheckAndSend(transactionType, details)

	elif args.action == 'post_ltc_buy':
		transactionType = 'LTCBuyOffer'
		details = {
		    'sourceAccount':GetActiveAccount(),
		    'changeAccount':host.getNewSwapBillAddress(),
		    'refundAccount':host.getNewSwapBillAddress(),
		    'swapBillOffered':int(args.quantity),
		    'exchangeRate':int(float(args.exchangeRate) * 0x100000000),
		    'receivingAccount':host.getNewNonSwapBillAddress(),
		    'maxBlock':0xffffffff,
		    'maxBlockOffset':0
		}
		CheckAndSend(transactionType, details)

	elif args.action == 'post_ltc_sell':
		transactionType = 'LTCSellOffer'
		details = {
		    'sourceAccount':GetActiveAccount(),
		    'changeAccount':host.getNewSwapBillAddress(),
		    'swapBillDesired':int(args.quantity),
		    'exchangeRate':int(float(args.exchangeRate) * 0x100000000),
		    'receivingAccount':host.getNewSwapBillAddress(),
		    'maxBlock':0xffffffff,
		    'maxBlockOffset':0
		}
		CheckAndSend(transactionType, details)

	elif args.action == 'complete_ltc_sell':
		transactionType = 'LTCExchangeCompletion'
		pendingExchangeID = int(args.pending_exchange_id)
		if not pendingExchangeID in state._pendingExchanges:
			raise ExceptionReportedToUser('No pending exchange with the specified ID.')
		exchange = state._pendingExchanges[pendingExchangeID]
		details = {
		    'pendingExchangeIndex':pendingExchangeID,
		    'destinationAccount':exchange.ltcReceiveAddress,
		    'destinationAmount':exchange.ltc
		}
		CheckAndSend(transactionType, details)

	elif args.action == 'show_balance':
		unspent, sourceLookup = GetUnspent.GetUnspent(transactionBuildLayer, state._balances)
		totalOwned = 0
		totalSpendable = 0
		largestSpendable = 0
		for pubKeyHash in state._balances:
			if not host.addressIsMine(pubKeyHash):
				continue
			balance = state._balances[pubKeyHash]
			totalOwned += balance
			if not sourceLookup.addressIsSeeded(pubKeyHash):
				continue
			totalSpendable += balance
			if balance > largestSpendable:
				largestSpendable = balance
		print('(in swap bill satoshis): ', file=out)
		print('total owned =', totalOwned, file=out)
		print('total spendable =', totalSpendable, file=out)
		print('current active balance =', totalSpendable, file=out)

	elif args.action == 'show_offers':
		print('Buy offers:')
		offers = state._LTCBuys.getSortedExchangeRateAndDetails()
		if len(offers) == 0:
			print('  (no buy offers)')
		for exchangeRate, buyDetails in offers:
			pubKeyHash = buyDetails.refundAccount
			exchangeAmount = buyDetails.swapBillAmount
			rate_Double = float(exchangeRate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			line = '  rate:{:.7f}, swapbill offered:{}, ltc equivalent:{}'.format(rate_Double, exchangeAmount, ltc)
			address = host.formatAddressForEndUser(pubKeyHash)
			validateResults = host._rpcHost.call('validateaddress', address)
			if validateResults['ismine'] == True:
				line += ' (mine)'
			print(line)
		print('Sell offers:')
		offers = state._LTCSells.getSortedExchangeRateAndDetails()
		if len(offers) == 0:
			print('  (no sell offers)')
		for exchangeRate, sellDetails in offers:
			pubKeyHash = sellDetails.receivingAccount
			exchangeAmount = sellDetails.swapBillAmount
			depositAmount = sellDetails.swapBillDeposit
			rate_Double = float(exchangeRate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			line = '  rate:{:.7f}, swapbill desired:{}, ltc equivalent:{}'.format(rate_Double, exchangeAmount, ltc)
			address = host.formatAddressForEndUser(pubKeyHash)
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
			address = host.formatAddressForEndUser(exchange.buyerAddress)
			line = '  buyer = ' + address
			validateResults = host._rpcHost.call('validateaddress', address)
			if validateResults['ismine'] == True:
				line += ' (me)'
			print(line)
			address = host.formatAddressForEndUser(exchange.sellerAddress)
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
