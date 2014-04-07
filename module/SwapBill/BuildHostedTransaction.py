from __future__ import print_function
import struct
from SwapBill import ControlAddressEncoding, Address
from SwapBill.ChooseInputs import ChooseInputs

def _build_Common(config, swapBillTransaction, unspent, forceIncludeLast, reSeedAddress, changeAddress, seedDestination):
	unspentAmounts, unspentAsInputs = unspent

	if sum(unspentAmounts) < (config.minimumTransactionAmount + config.transactionFee):
		print('Unspent outputs are not sufficient with the configured minimum transaction amount.')
		print('Configured minimum transaction ({}) plus configured transaction fee ({}) = {})'.format(config.minimumTransactionAmount, config.transactionFee, config.minimumTransactionAmount + config.transactionFee))
		print('Unspent outputs reported by litecoind sum to {}'.format(sum(unspentAmounts)))
		return None

	if hasattr(swapBillTransaction, 'controlAddressAmount'):
		targetAmounts = [swapBillTransaction.controlAddressAmount]
	else:
		targetAmounts = [config.dustOutputAmount]
	controlAddressData = ControlAddressEncoding.Encode(swapBillTransaction)
	targetAddresses = [Address.FromData(config.addressVersion, controlAddressData)]

	if hasattr(swapBillTransaction, 'destinationAddress'):
		if seedDestination:
			destinationAmount = config.seedAmount
		else:
			destinationAmount = config.dustOutputAmount
		targetAddresses.append(swapBillTransaction.destinationAddress)
		targetAmounts.append(destinationAmount)

	if sum(targetAmounts) < config.minimumTransactionAmount:
		backingAmount = config.minimumTransactionAmount - sum(targetAmounts)
		targetAddresses.append(changeAddress)
		targetAmounts.append(backingAmount)

	totalRequired = sum(targetAmounts) + config.transactionFee
	if sum(unspentAmounts) < totalRequired:
		print('Unspent outputs are not sufficient for the requested transaction.')
		print('Total required, with fee ({}) = {}'.format(config.transactionFee, totalRequired))
		print('Unspent outputs reported by litecoind sum to {}'.format(sum(unspentAmounts)))
		return None

	if forceIncludeLast:
		outputAssignments, outputsTotal = ChooseInputs(unspentAmounts[:-1], totalRequired)
		outputAssignments.append(len(unspentAmounts) - 1)
		outputsTotal += unspentAmounts[-1]
	else:
		outputAssignments, outputsTotal = ChooseInputs(unspentAmounts, totalRequired)
	inputs = []
	for i in outputAssignments:
		inputs.append(unspentAsInputs[i])

	if outputsTotal > totalRequired:
		overSupply = outputsTotal - totalRequired
		if targetAddresses[-1] == changeAddress:
			targetAmounts[-1] += overSupply
		else:
			targetAddresses.append(changeAddress)
			targetAmounts.append(overSupply)

	if not reSeedAddress is None:
		if targetAddresses[-1] == changeAddress:
			## use change to reseed
			if targetAmounts[-1] <= config.seedAmount:
				targetAddresses[-1] = reSeedAddress
			else:
				targetAmounts[-1] -= config.seedAmount
				targetAmounts.append(config.seedAmount)
				targetAddresses.append(reSeedAddress)

	return inputs, targetAddresses, targetAmounts

def Build_FundedByAccount(config, swapBillTransaction, fundingAccountUnspent, changeAddress, seedDestination):
	assert not hasattr(swapBillTransaction, 'sourceAddress')
	return _build_Common(config, swapBillTransaction, fundingAccountUnspent, False, None, changeAddress, seedDestination)

def Build_WithSourceAddress(config, swapBillTransaction, sourceAddress, sourceAddressSingleUnspent, backerAccountUnspent, changeAddress, seedDestination):
	assert swapBillTransaction.sourceAddress == sourceAddress
	sourceUnspentAmount, sourceUnspentAsInput = sourceAddressSingleUnspent
	unspentAmounts, unspentAsInputs = backerAccountUnspent
	unspentAmounts.append(sourceUnspentAmount)
	unspentAsInputs.append(sourceUnspentAsInput)
	return _build_Common(config, swapBillTransaction, (unspentAmounts, unspentAsInputs), True, sourceAddress, changeAddress, seedDestination)

def Build_Native(config, fundingAccountUnspent, destination, amount, changeAddress):
	pass

