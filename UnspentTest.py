from __future__ import print_function
import sys, argparse, binascii, traceback, struct, time
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import Host, TransactionTypes, TransactionFee, BuildHostedTransaction, ScriptPubKeyLookup, Address
from SwapBill.Sync import SyncAndReturnState

class Config(object):
	pass
config = Config()
config.blocksBehindForCachedState = 20
config.startBlockIndex = 241432
## from: litecoind -testnet getblockhash 241432
config.startBlockHash = '3fa2cf2d644b74b7f6407a1d3a9d15ad98f85da9adecbac0b1560c11c0393eed'

host = Host.Host(useTestNet=True)

unspent = host.getNonSwapBillUnspent({})
#print('unspent before:', unspent)
print('number of unspent before:', len(unspent[1]))

def CheckAndReturnPubKeyHash(address):
	try:
		pubKeyHash = Address.ToPubKeyHash(host._addressVersion, address)
	except Address.BadAddress as e:
		print('Bad address:', address)
		print(e)
		exit()
	return pubKeyHash

def CheckAndSend_FromAddress(tx):
	state = SyncAndReturnState(config, host)
	source = tx.source
	if hasattr(tx, 'consumedAmount'):
		requiredAmount = tx.consumedAmount()
	else:
		requiredAmount = tx.amount
	if not source in state._balances or state._balances[source] < requiredAmount:
		print('Insufficient swapbill balance for source address.')
		exit()
	sourceSingleUnspent = host.getSingleUnspentForAddress(source)
	if sourceSingleUnspent == None:
		print('No unspent outputs reported by litecoind for the specified from address.')
		print("This could be because a transaction is in progress and needs to be confirmed (in which case you may just need to wait)," +
			  " or it's also possible that all litecoin seeded to this address has been spent (in which case you will need to reseed).")
		exit()
	backerUnspent = host.getNonSwapBillUnspent(state._balances)
	scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(backerUnspent[1], sourceSingleUnspent[1])
	change = host.getNewNonSwapBillAddress()
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

fromAddress = 'mpE1iVsytmgaKqcjW3LasEps47MdJJrDb9'

source = CheckAndReturnPubKeyHash(fromAddress)
exchangeRate = int(0.3 * 0x100000000)
tx = TransactionTypes.LTCSellOffer()
swapBillToBuy = 1000000
tx.init_FromUserRequirements(source=source, swapBillDesired=swapBillToBuy, exchangeRate=exchangeRate)
CheckAndSend_FromAddress(tx)



#scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
#target = host.getNewSwapBillAddress()
#burnTX = TransactionTypes.Burn()
#burnTX.init_FromUserRequirements(burnAmount=100000, target=target)
#change = host.getNewNonSwapBillAddress()
#print('attempting to send swap bill transaction:', burnTX)
#transactionFee = TransactionFee.baseFee
#try:
	#litecoinTX = BuildHostedTransaction.Build_FundedByAccount(TransactionFee.dustLimit, transactionFee, burnTX, unspent, change)
	#txID = host.sendTransaction(litecoinTX, scriptPubKeyLookup)
#except Host.InsufficientTransactionFees:
	#print("Failed: Unexpected failure to meet transaction fee requirement. (Lots of dust inputs?)")
#except Host.SigningFailed:
	#print("Failed: Transaction could not be signed")
#except BuildHostedTransaction.ControlAddressBelowDustLimit:
	#print("Failed: Burn quantity is below configured dust limit")
#else:
	#print('Transaction sent with transactionID:')
	#print(txID)

	#s = set()
	#print("transaction inputs:")
	#for i in range(litecoinTX.numberOfInputs()):
		#print(litecoinTX.inputTXID(i), '-', litecoinTX.inputVOut(i))
		#s.add((litecoinTX.inputTXID(i), litecoinTX.inputVOut(i)))

	##print("checking against originally listed unspent (as control)")

	##for entry in unspent[1]:
		##key = (entry[0], entry[1])
		##if key in s:
			##print("unspent still listed:", key)

	#print("checking immediately")

	#unspentAfter = host.getNonSwapBillUnspent({})
	#print('number of unspent after:', len(unspentAfter[1]))
	#for entry in unspentAfter[1]:
		#key = (entry[0], entry[1])
		#if key in s:
			#print("unspent still listed:" + key)

	#print("waiting 10 seconds")
	#time.sleep(10)

	#print("checking again")

	#unspentAfter = host.getNonSwapBillUnspent({})
	#for entry in unspentAfter[1]:
		#key = (entry[0], entry[1])
		#if key in s:
			#print("unspent still listed:" + key)
