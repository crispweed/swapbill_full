from __future__ import print_function
from SwapBill import TransactionEncoding

def FromStateTransactionWrapper(originalFunction):
	def Wrapper(transactionType, sourceAccounts, outputs, outputPubKeyHashes, originalDetails):
		tx = originalFunction(transactionType, sourceAccounts, outputs, outputPubKeyHashes, originalDetails)
		transactionType_Check, sourceAccounts_Check, outputs_Check, details_Check = TransactionEncoding.ToStateTransaction(tx)
		assert transactionType_Check == transactionType
		assert sourceAccounts_Check == sourceAccounts
		assert outputs_Check == outputs
		if details_Check != originalDetails:
			print('originalDetails:', originalDetails)
			print('details_Check:', details_Check)
		assert details_Check == originalDetails
		return tx
	return Wrapper
TransactionEncoding.FromStateTransaction = FromStateTransactionWrapper(TransactionEncoding.FromStateTransaction)

