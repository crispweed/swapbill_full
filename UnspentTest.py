from __future__ import print_function
import sys, argparse, binascii, traceback, struct, time
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import Host, TransactionTypes, TransactionFee, BuildHostedTransaction, ScriptPubKeyLookup

host = Host.Host(useTestNet=True)

unspent = host.getNonSwapBillUnspent({})
#print('unspent before:', unspent)
print('number of unspent before:', len(unspent[1]))

scriptPubKeyLookup = ScriptPubKeyLookup.Lookup(unspent[1])
target = host.getNewSwapBillAddress()
burnTX = TransactionTypes.Burn()
burnTX.init_FromUserRequirements(burnAmount=100000, target=target)
change = host.getNewChangeAddress()
print('attempting to send swap bill transaction:', burnTX)
transactionFee = TransactionFee.baseFee
try:
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

	s = set()
	print("transaction inputs:")
	for i in range(litecoinTX.numberOfInputs()):
		print(litecoinTX.inputTXID(i), '-', litecoinTX.inputVOut(i))
		s.add((litecoinTX.inputTXID(i), litecoinTX.inputVOut(i)))

	#print("checking against originally listed unspent (as control)")

	#for entry in unspent[1]:
		#key = (entry[0], entry[1])
		#if key in s:
			#print("unspent still listed:", key)

	print("checking immediately")

	unspentAfter = host.getNonSwapBillUnspent({})
	print('number of unspent after:', len(unspentAfter[1]))
	for entry in unspentAfter[1]:
		key = (entry[0], entry[1])
		if key in s:
			print("unspent still listed:" + key)

	print("waiting 10 seconds")
	time.sleep(10)

	print("checking again")

	unspentAfter = host.getNonSwapBillUnspent({})
	for entry in unspentAfter[1]:
		key = (entry[0], entry[1])
		if key in s:
			print("unspent still listed:" + key)
