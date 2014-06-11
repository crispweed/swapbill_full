from __future__ import print_function
import sys, argparse, binascii, traceback, struct, time, os
supportedVersions = ('2.7', '3.2', '3.3', '3.4')
thisVersion = str(sys.version_info.major) + '.' + str(sys.version_info.minor)
if not thisVersion in supportedVersions:
	print('This version of python (' + thisVersion + ') is not supported. Supported versions are:', supportedVersions)
	exit()
PY3 = sys.version_info.major > 2
if PY3:
	import io
else:
	import StringIO as io
from os import path
try:
	from SwapBill import RawTransaction, Address, TransactionFee
	from SwapBill import TransactionEncoding, BuildHostedTransaction, Sync, Host, TransactionBuildLayer, Wallet
	from SwapBill import FormatTransactionForUserDisplay
	from SwapBill.Sync import SyncAndReturnStateAndOwnedAccounts
	from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser
	from SwapBill.State import InsufficientFundsForTransaction, BadlyFormedTransaction, TransactionFailsAgainstCurrentState
	from SwapBill.HardCodedProtocolConstraints import Constraints
except ImportError as e:
	message = str(e)
	start = 'No module named '
	assert message.startswith(start)
	module = message[len(start):]
	module = module.strip("'")
	print("Please install the '" + module + "' module.")
	print("e.g. (on linux, for this python version) 'sudo pip-{major}.{minor} install {module}'".format(major=sys.version_info.major, minor=sys.version_info.minor, module=module))
	print("or 'easy_install " + module + "'")
	exit()

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
parser.add_argument('--configFile', help='the location of the configuration file')
parser.add_argument('--dataDir', help='the location of the data directory', default='.')
parser.add_argument('--forceRescan', help='force a full block chain rescan', action='store_true')
subparsers = parser.add_subparsers(dest='action', help='the action to be taken')

sp = subparsers.add_parser('burn', help='destroy litecoin to create swapbill')
sp.add_argument('--amount', required=True, help='amount of LTC to be destroyed, in satoshis')

sp = subparsers.add_parser('pay', help='make a swapbill payment')
sp.add_argument('--amount', required=True, help='amount of swapbill to be paid, in satoshis')
sp.add_argument('--toAddress', required=True, help='pay to this address')
sp.add_argument('--blocksUntilExpiry', type=int, default=8, help='if the transaction takes longer than this to go through then the transaction expires (in which case no payment is made and the full amount is returned as change)')

sp = subparsers.add_parser('post_ltc_buy', help='make an offer to buy litecoin with swapbill')
sp.add_argument('--swapBillOffered', required=True, help='amount of swapbill offered')
sp.add_argument('--blocksUntilExpiry', type=int, default=8, help='after this number of blocks the offer expires (and swapbill remaining in any unmatched part of the offer is returned)')
sp.add_argument('--exchangeRate', help='the exchange rate SWP/LTC, in floating point representation (must be greater than 0 and less than 1)')
sp.add_argument('--exchangeRate_AsInteger', help='the exchange rate SWP/LTC, in integer representation (must be greater than 0 and less than 4294967296)')

sp = subparsers.add_parser('post_ltc_sell', help='make an offer to sell litecoin for swapbill')
sp.add_argument('--ltcOffered', required=True, help='amount of ltc offered')
sp.add_argument('--blocksUntilExpiry', type=int, default=2, help='after this number of blocks the offer expires (and swapbill remaining in any unmatched part of the offer is returned)')
sp.add_argument('--exchangeRate', help='the exchange rate SWP/LTC, in floating point representation (must be greater than 0 and less than 1)')
sp.add_argument('--exchangeRate_AsInteger', help='the exchange rate SWP/LTC, in integer representation (must be greater than 0 and less than 4294967296)')

sp = subparsers.add_parser('complete_ltc_sell', help='complete an ltc exchange by fulfilling a pending exchange payment')
sp.add_argument('--pendingExchangeID', required=True, help='the id of the pending exchange payment to fulfill')

sp = subparsers.add_parser('back_ltc_sells', help='commit swapbill to back ltc exchanges')
sp.add_argument('--backingSwapBill', required=True, help='amount of swapbill to commit')
sp.add_argument('--transactionsBacked', required=True, help='the number of transactions you want to back, which then implies a maximum backing amount per transaction')
sp.add_argument('--blocksUntilExpiry', type=int, default=200, help='number of blocks for which the backing amount should remain committed')
sp.add_argument('--commission', help='the rate of commission for backed transactions, in floating point representation (must be greater than or equal to 0 and less than 1)')
sp.add_argument('--commission_AsInteger', help='the rate of commission for backed transactions, in integer representation (must be greater than or equal to 0 and less than 4294967296)')

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

sp = subparsers.add_parser('get_ltc_sell_backers', help='get information about funds currently commited to backing ltc sell operations')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

sp = subparsers.add_parser('get_state_info', help='get some general state information')
sp.add_argument('-i', '--includepending', help='include transactions that have been submitted but not yet confirmed (based on host memory pool)', action='store_true')

def ExchangeRateFromArgs(args):
	if args.exchangeRate is not None:
		if args.exchangeRate_AsInteger is not None:
			raise ExceptionReportedToUser("Either exchangeRate or exchangeRate_AsInteger should be specified, not both.")
		return int(float(args.exchangeRate) * 0x100000000)
	if args.exchangeRate_AsInteger is None:
		raise ExceptionReportedToUser("One of exchangeRate or exchangeRate_AsInteger must be specified.")
	return int(args.exchangeRate_AsInteger)
def CommissionFromArgs(args):
	if args.commission is not None:
		if args.commission_AsInteger is not None:
			raise ExceptionReportedToUser("Either commision or commission_AsInteger should be specified, not both.")
		return int(float(args.commission) * 0x100000000)
	if args.commission_AsInteger is None:
		raise ExceptionReportedToUser("One of commission or commission_AsInteger must be specified.")
	return int(args.commission_AsInteger)

def Main(startBlockIndex, startBlockHash, useTestNet, commandLineArgs=sys.argv[1:], host=None, keyGenerator=None, out=sys.stdout):
	args = parser.parse_args(commandLineArgs)

	if not path.isdir(args.dataDir):
		raise ExceptionReportedToUser("The following path (specified for data directory parameter) is not a valid path to an existing directory: " + args.dataDir)

	dataDir = path.join(args.dataDir, 'swapBillData')
	if not path.exists(dataDir):
		try:
			os.mkdir(dataDir)
		except Exception as e:
			raise ExceptionReportedToUser("Failed to create directory " + dataDir + ":", e)

	wallet = Wallet.Wallet(path.join(dataDir, 'wallet.txt'), privateKeyAddressVersion=b'\xef', keyGenerator=keyGenerator) # litecoin testnet private key address version

	if host is None:
		host = Host.Host(useTestNet=useTestNet, dataDirectory=dataDir, configFile=args.configFile)

	includePending = hasattr(args, 'includepending') and args.includepending

	if args.action == 'get_state_info':
		syncOut = io.StringIO()
		startTime = time.clock()
		state, ownedAccounts = SyncAndReturnStateAndOwnedAccounts(dataDir, startBlockIndex, startBlockHash, wallet, host, includePending=includePending, forceRescan=args.forceRescan, out=syncOut)
		elapsedTime = time.clock() - startTime
		formattedBalances = {}
		for account in state._balances.balances:
			key = host.formatAccountForEndUser(account)
			formattedBalances[key] = state._balances.balanceFor(account)
		info = {
		    'totalCreated':state._totalCreated,
		    'atEndOfBlock':state._currentBlockIndex - 1, 'balances':formattedBalances, 'syncOutput':syncOut.getvalue(),
		    'syncTime':elapsedTime,
		    'numberOfLTCBuyOffers':state._ltcBuys.size(),
		    'numberOfLTCSellOffers':state._ltcSells.size(),
		    'numberOfPendingExchanges':len(state._pendingExchanges),
		    'numberOfOutputs':len(ownedAccounts.accounts)
		}
		return info

	state, ownedAccounts = SyncAndReturnStateAndOwnedAccounts(dataDir, startBlockIndex, startBlockHash, wallet, host, includePending=includePending, forceRescan=args.forceRescan, out=out)

	transactionBuildLayer = TransactionBuildLayer.TransactionBuildLayer(host, ownedAccounts)

	def SetFeeAndSend(baseTX, baseTXInputsAmount, unspent):
		change = host.getNewNonSwapBillAddress()
		maximumSignedSize = TransactionFee.startingMaximumSize
		transactionFee = TransactionFee.startingFee
		try:
			filledOutTX = BuildHostedTransaction.AddPaymentFeesAndChange(baseTX, baseTXInputsAmount, TransactionFee.dustLimit, transactionFee, unspent, change)
			return transactionBuildLayer.sendTransaction(filledOutTX, maximumSignedSize)
		except Host.MaximumSignedSizeExceeded:
			print("Transaction fee increased.", file=out)
			try:
				maximumSignedSize += TransactionFee.sizeStep
				transactionFee += TransactionFee.feeStep
				filledOutTX = BuildHostedTransaction.AddPaymentFeesAndChange(baseTX, baseTXInputsAmount, TransactionFee.dustLimit, transactionFee, unspent, change)
				return transactionBuildLayer.sendTransaction(filledOutTX, maximumSignedSize)
			except Host.MaximumSignedSizeExceeded:
				raise ExceptionReportedToUser("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")

	def CheckAndSend_Common(transactionType, sourceAccounts, outputs, outputPubKeys, details):
		change = host.getNewNonSwapBillAddress()
		print('attempting to send ' + FormatTransactionForUserDisplay.Format(host, transactionType, outputs, outputPubKeys, details), file=out)
		baseTX = TransactionEncoding.FromStateTransaction(transactionType, sourceAccounts, outputs, outputPubKeys, details)
		backingUnspent = transactionBuildLayer.getUnspent()
		baseInputsAmount = 0
		for i in range(baseTX.numberOfInputs()):
			txID = baseTX.inputTXID(i)
			vOut = baseTX.inputVOut(i)
			baseInputsAmount += ownedAccounts.accounts[(txID, vOut)][0]
		txID = SetFeeAndSend(baseTX, baseInputsAmount, backingUnspent)
		return {'transaction id':txID}

	def CheckAndSend_Funded(transactionType, outputs, outputPubKeys, details):
		TransactionEncoding.FromStateTransaction(transactionType, [], outputs, outputPubKeys, details) # for initial parameter checking
		transactionBuildLayer.startTransactionConstruction()
		swapBillUnspent = transactionBuildLayer.getSwapBillUnspent(state)
		sourceAccounts = []
		while True:
			try:
				state.checkTransaction(transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=sourceAccounts)
			except InsufficientFundsForTransaction:
				pass
			except (BadlyFormedTransaction, TransactionFailsAgainstCurrentState) as e:
				raise TransactionNotSuccessfulAgainstCurrentState('Transaction would not complete successfully against current state: ' + str(e))
			else:
				break
			if not swapBillUnspent:
				raise ExceptionReportedToUser('Insufficient swapbill for transaction.')
			transactionBuildLayer.swapBillUnspentUsed(swapBillUnspent[0])
			sourceAccounts.append(swapBillUnspent[0])
			swapBillUnspent = swapBillUnspent[1:]
		return CheckAndSend_Common(transactionType, sourceAccounts, outputs, outputPubKeys, details)

	def CheckAndSend_UnFunded(transactionType, outputs, outputPubKeys, details):
		TransactionEncoding.FromStateTransaction(transactionType, None, outputs, outputPubKeys, details) # for initial parameter checking
		transactionBuildLayer.startTransactionConstruction()
		try:
			state.checkTransaction(transactionType, outputs=outputs, transactionDetails=details, sourceAccounts=None)
		except (BadlyFormedTransaction, TransactionFailsAgainstCurrentState) as e:
			raise TransactionNotSuccessfulAgainstCurrentState('Transaction would not complete successfully against current state: ' + str(e))
		return CheckAndSend_Common(transactionType, None, outputs, outputPubKeys, details)

	def CheckAndReturnPubKeyHash(address):
		try:
			pubKeyHash = host.addressFromEndUserFormat(address)
		except Address.BadAddress as e:
			raise BadAddressArgument(address)
		return pubKeyHash

	if args.action == 'burn':
		if int(args.amount) < TransactionFee.dustLimit:
			raise ExceptionReportedToUser('Burn amount is below dust limit.')
		transactionType = 'Burn'
		outputs = ('destination',)
		outputPubKeyHashes = (wallet.addKeyPairAndReturnPubKeyHash(),)
		details = {'amount':int(args.amount)}
		return CheckAndSend_Funded(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'pay':
		transactionType = 'Pay'
		outputs = ('change', 'destination')
		outputPubKeyHashes = (wallet.addKeyPairAndReturnPubKeyHash(), CheckAndReturnPubKeyHash(args.toAddress))
		details = {
		    'amount':int(args.amount),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend_Funded(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'post_ltc_buy':
		transactionType = 'LTCBuyOffer'
		outputs = ('ltcBuy',)
		outputPubKeyHashes = (wallet.addKeyPairAndReturnPubKeyHash(),)
		details = {
		    'swapBillOffered':int(args.swapBillOffered),
		    'exchangeRate':ExchangeRateFromArgs(args),
		    'receivingAddress':host.getNewNonSwapBillAddress(),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend_Funded(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'post_ltc_sell':
		transactionType = 'LTCSellOffer'
		outputs = ('ltcSell',)
		outputPubKeyHashes = (wallet.addKeyPairAndReturnPubKeyHash(),)
		details = {
		    'ltcOffered':int(args.ltcOffered),
		    'exchangeRate':ExchangeRateFromArgs(args),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend_Funded(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'complete_ltc_sell':
		transactionType = 'LTCExchangeCompletion'
		pendingExchangeID = int(args.pendingExchangeID)
		if not pendingExchangeID in state._pendingExchanges:
			raise ExceptionReportedToUser('No pending exchange with the specified ID.')
		exchange = state._pendingExchanges[pendingExchangeID]
		details = {
		    'pendingExchangeIndex':pendingExchangeID,
		    'destinationAddress':exchange.ltcReceiveAddress,
		    'destinationAmount':exchange.ltc
		}
		return CheckAndSend_UnFunded(transactionType, (), (), details)

	elif args.action == 'back_ltc_sells':
		transactionType = 'BackLTCSells'
		outputs = ('ltcSellBacker',)
		outputPubKeyHashes = (wallet.addKeyPairAndReturnPubKeyHash(),)
		details = {
		    'backingAmount':int(args.backingSwapBill),
		    'transactionsBacked':int(args.transactionsBacked),
		    'ltcReceiveAddress':host.getNewNonSwapBillAddress(),
		    'commission':CommissionFromArgs(args),
		    'maxBlock':state._currentBlockIndex + args.blocksUntilExpiry
		}
		return CheckAndSend_Funded(transactionType, outputs, outputPubKeyHashes, details)

	elif args.action == 'get_receive_address':
		pubKeyHash = wallet.addKeyPairAndReturnPubKeyHash()
		return {'receive_address': host.formatAddressForEndUser(pubKeyHash)}

	elif args.action == 'get_balance':
		total = 0
		for account in ownedAccounts.accounts:
			amount = state._balances.balanceFor(account)
			total += amount
		spendable = total
		if transactionBuildLayer.checkIfThereIsAtLeastOneOutstandingTradeRef(state):
			spendable -= Constraints.minimumSwapBillBalance
			assert spendable >= 0
		return {'spendable':spendable, 'total':total}

	elif args.action == 'get_buy_offers':
		result = []
		for offer in state._ltcBuys.getSortedOffers():
			mine = offer.refundAccount in ownedAccounts.tradeOfferChangeCounts
			exchangeAmount = offer._swapBillOffered
			rate_Double = float(offer.rate) / 0x100000000
			ltc = int(exchangeAmount * rate_Double)
			result.append(('exchange rate as float (approximation)', rate_Double, {'exchange rate as integer':offer.rate, 'swapbill offered':exchangeAmount, 'ltc equivalent':ltc, 'mine':mine}))
		return result

	elif args.action == 'get_sell_offers':
		result = []
		for offer in state._ltcSells.getSortedOffers():
			mine = offer.receivingAccount in ownedAccounts.tradeOfferChangeCounts
			ltc = offer._ltcOffered
			depositAmount = offer._swapBillDeposit
			rate_Double = float(offer.rate) / 0x100000000
			swapBillEquivalent = int(ltc / rate_Double)
			result.append(('exchange rate as float (approximation)', rate_Double, {'exchange rate as integer':offer.rate, 'ltc offered':ltc, 'deposit paid':depositAmount, 'swapbill equivalent':swapBillEquivalent, 'mine':mine}))
		return result

	elif args.action == 'get_pending_exchanges':
		result = []
		for key in state._pendingExchanges:
			d = {}
			exchange = state._pendingExchanges[key]
			d['I am seller (and need to complete)'] = exchange.sellerReceivingAccount in ownedAccounts.tradeOfferChangeCounts
			d['I am buyer (and waiting for payment)'] = exchange.buyerAccount in ownedAccounts.tradeOfferChangeCounts
			d['deposit paid by seller'] = exchange.swapBillDeposit
			d['swap bill paid by buyer'] = exchange.swapBillAmount
			d['outstanding ltc payment amount'] = exchange.ltc
			d['expires on block'] = exchange.expiry
			result.append(('pending exchange index', key, d))
		return result

	elif args.action == 'get_ltc_sell_backers':
		result = []
		for key in state._ltcSellBackers:
			d = {}
			backer = state._ltcSellBackers[key]
			d['I am backer'] = backer.refundAccount in ownedAccounts.tradeOfferChangeCounts
			d['backing amount'] = backer.backingAmount
			d['maximum per transaction'] = backer.transactionMax
			d['expires on block'] = backer.expiry
			commission_Double = float(backer.commission) / 0x100000000
			d['commission as float (approximation)'] = commission_Double
			d['commission as integer'] = backer.commission
			result.append(('ltc sell backer index', key, d))
		return result

	else:
		parser.print_help()
