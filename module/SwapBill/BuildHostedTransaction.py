from __future__ import print_function
import struct
from SwapBill import ControlAddressEncoding, HostTransaction
from SwapBill.ChooseInputs import ChooseInputs
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

class InsufficientFunds(ExceptionReportedToUser):
	pass
class ControlAddressBelowDustLimit(Exception):
	pass

def _build_Common(dustLimit, transactionFee, swapBillTransaction, unspent, forceIncludeLast, reSeedPubKeyHash, changePubKeyHash):
	unspentAmounts, unspentAsInputs = unspent

	hostedTX = HostTransaction.InMemoryTransaction()

	if hasattr(swapBillTransaction, 'controlAddressAmount'):
		if swapBillTransaction.controlAddressAmount < dustLimit:
			raise ControlAddressBelowDustLimit()
		outAmounts = [swapBillTransaction.controlAddressAmount]
	else:
		outAmounts = [dustLimit]
	controlAddressData = ControlAddressEncoding.Encode(swapBillTransaction)
	outDestinations = [controlAddressData]

	if hasattr(swapBillTransaction, 'destination'):
		outDestinations.append(swapBillTransaction.destination)
		if hasattr(swapBillTransaction, 'destinationAmount'):
			outAmounts.append(swapBillTransaction.destinationAmount)
		else:
			outAmounts.append(dustLimit)

	if not reSeedPubKeyHash is None:
		outDestinations.append(reSeedPubKeyHash)
		outAmounts.append(dustLimit)

	totalRequired = sum(outAmounts) + transactionFee
	if sum(unspentAmounts) < totalRequired:
		raise InsufficientFunds('Not enough funds available for the transaction, total required:', totalRequired, 'transaction fee:', transactionFee, 'sum of unspent:', sum(unspentAmounts))

	if forceIncludeLast:
		#assert config.maxInputs > 0
		if totalRequired > unspentAmounts[-1]:
			#outputAssignments, outputsTotal = ChooseInputs(maxInputs=config.maxInputs - 1, unspentAmounts=unspentAmounts[:-1], amountRequired=totalRequired - unspentAmounts[-1])
			outputAssignments, outputsTotal = ChooseInputs(maxInputs=len(unspentAmounts), unspentAmounts=unspentAmounts[:-1], amountRequired=totalRequired - unspentAmounts[-1])
		else:
			outputAssignments = []
			outputsTotal = 0
		outputAssignments.append(len(unspentAmounts) - 1)
		outputsTotal += unspentAmounts[-1]
	else:
		#outputAssignments, outputsTotal = ChooseInputs(maxInputs=config.maxInputs, unspentAmounts=unspentAmounts, amountRequired=totalRequired)
		outputAssignments, outputsTotal = ChooseInputs(maxInputs=len(unspentAmounts), unspentAmounts=unspentAmounts, amountRequired=totalRequired)
	#assert len(outputAssignments) <= config.maxInputs

	#if outputsTotal < totalRequired:
		#print('Cannot pay for transaction within the current maximum inputs constraint (maximum {} inputs).'.format(config.maxInputs))
		#print('Available unspent output amounts reported by litecoind:')
		#print(unspentAmounts)
		#return None

	for i in outputAssignments:
		hostedTX.addInput(unspentAsInputs[i][0], unspentAsInputs[i][1])

	if outputsTotal > totalRequired:
		overSupply = outputsTotal - totalRequired
		if overSupply >= dustLimit:
			outDestinations.append(changePubKeyHash)
			outAmounts.append(overSupply)
		elif outDestinations[-1] == reSeedPubKeyHash:
			outAmounts[-1] += overSupply

	hostedTX.addOutputsFromSeparateLists(outDestinations, outAmounts)

	return hostedTX

def Build_FundedByAccount(dustLimit, transactionFee, swapBillTransaction, fundingAccountUnspent, changePubKeyHash):
	assert not hasattr(swapBillTransaction, 'source')
	return _build_Common(dustLimit, transactionFee, swapBillTransaction, fundingAccountUnspent, False, None, changePubKeyHash)

def Build_WithSourceAddress(dustLimit, transactionFee, swapBillTransaction, sourceAddressSingleUnspent, backerAccountUnspent, changePubKeyHash):
	sourceUnspentAmount, sourceUnspentAsInput = sourceAddressSingleUnspent
	unspentAmounts, unspentAsInputs = backerAccountUnspent
	unspentAmounts = list(unspentAmounts)
	unspentAsInputs = list(unspentAsInputs)
	unspentAmounts.append(sourceUnspentAmount)
	unspentAsInputs.append(sourceUnspentAsInput)
	return _build_Common(dustLimit, transactionFee, swapBillTransaction, (unspentAmounts, unspentAsInputs), True, swapBillTransaction.source, changePubKeyHash)

def Build_Native(addressVersion, dustLimit, transactionFee, fundingAccountUnspent, destination, amount, changePubKeyHash):
	pass
