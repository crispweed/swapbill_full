from __future__ import print_function
import sys
from os import path
from collections import deque
from SwapBill import State, RawTransaction, TransactionEncoding, PickledCache, OwnedAccounts, ControlAddressPrefix
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

stateVersion = 0.8
ownedAccountsVersion = 0.2

def _processTransactions(host, state, ownedAccounts, transactions, applyToState, reportPrefix, out):
	for txID, hostTXHex in transactions:
		hostTXBytes = RawTransaction.FromHex(hostTXHex)
		hostTX, scriptPubKeys = RawTransaction.Decode(hostTXBytes)
		if RawTransaction.UnexpectedFormat_Fast(hostTXBytes, ControlAddressPrefix.prefix):
			continue
		report = ownedAccounts.updateForSpent(hostTX, state)
		try:
			transactionType, sourceAccounts, outputs, transactionDetails = TransactionEncoding.ToStateTransaction(hostTX)
			appliedSuccessfully = True
		except (TransactionEncoding.NotValidSwapBillTransaction, TransactionEncoding.UnsupportedTransaction):
			appliedSuccessfully = False
			transactionType = 'InvalidTransaction'
		if appliedSuccessfully:
			insufficientFunds = False
			try:
				if not state.checkTransaction(transactionType, outputs, transactionDetails, sourceAccounts=sourceAccounts)[0]:
					appliedSuccessfully = False
			except State.InsufficientFundsForTransaction:
				insufficientFunds = True
		if not appliedSuccessfully:
			if report != '':
				print(reportPrefix + ': ' + transactionType + ' failed to decode or apply', file=out)
				print(report, end="", file=out)
			continue
		if applyToState:
			#print(reportPrefix + ': ' + txID)
			inBetweenReport = ownedAccounts.checkForTradeOfferChanges(state)
			assert inBetweenReport == ''
			state.applyTransaction(transactionType, txID, outputs, transactionDetails, sourceAccounts=sourceAccounts)
			report += ownedAccounts.checkForTradeOfferChanges(state)
			report += ownedAccounts.updateForNewOutputs(host, state, txID, hostTX, outputs, scriptPubKeys)
		if report != '':
			print(reportPrefix + ': ' + transactionType, file=out)
			print(report, end="", file=out)
			if insufficientFunds:
				report += ' (failed due to insufficient swapbill, all funds directed to change output)\n'

def _processBlock(host, state, ownedAccounts, blockHash, reportPrefix, out):
	transactions = host.getBlockTransactions(blockHash)
	_processTransactions(host, state, ownedAccounts, transactions, True, reportPrefix, out)
	inBetweenReport = ownedAccounts.checkForTradeOfferChanges(state)
	assert inBetweenReport == ''
	state.advanceToNextBlock()
	tradeOffersChanged = ownedAccounts.checkForTradeOfferChanges(state)
	if tradeOffersChanged:
		print('trade offer or pending exchange expired', file=out)

def SyncAndReturnStateAndOwnedAccounts(cacheDirectory, startBlockIndex, startBlockHash, host, includePending, forceRescan, out):
	loaded = False
	if not forceRescan:
		try:
			(blockIndex, blockHash, state) = PickledCache.Load(cacheDirectory, 'State', stateVersion)
			ownedAccounts = PickledCache.Load(cacheDirectory, 'OwnedAccounts', ownedAccountsVersion)
			loaded = True
		except PickledCache.LoadFailedException as e:
			print('Failed to load from cache, full index generation required (' + str(e) + ')', file=out)
	if loaded and host.getBlockHashAtIndexOrNone(blockIndex) != blockHash:
		print('The block corresponding with cached state has been orphaned, full index generation required.', file=out)
		loaded = False
	if loaded and not state.startBlockMatches(startBlockHash):
		print('Start config does not match config from loaded state, full index generation required.', file=out)
		loaded = False
	if loaded:
		print('Loaded cached state data successfully', file=out)
	else:
		blockIndex = startBlockIndex
		blockHash = host.getBlockHashAtIndexOrNone(blockIndex)
		if blockHash is None:
			raise ExceptionReportedToUser('Block chain has not reached the swapbill start block (' + str(startBlockIndex) + ').')
		if blockHash != startBlockHash:
			raise ExceptionReportedToUser('Block hash for swapbill start block does not match.')
		state = State.State(blockIndex, blockHash)
		ownedAccounts = OwnedAccounts.OwnedAccounts()

	print('State update starting from block', blockIndex, file=out)

	toProcess = deque()
	mostRecentHash = blockHash
	while True:
		nextBlockHash = host.getNextBlockHash(mostRecentHash)
		if nextBlockHash is None:
			break
		## hard coded value used here for number of blocks to lag behind with persistent state
		if len(toProcess) == 20:
			## advance cached state
			_processBlock(host, state, ownedAccounts, blockHash, 'committed', out=out)
			popped = toProcess.popleft()
			blockIndex += 1
			blockHash = popped
		mostRecentHash = nextBlockHash
		toProcess.append(mostRecentHash)

	PickledCache.Save((blockIndex, blockHash, state), stateVersion, cacheDirectory, 'State')
	PickledCache.Save(ownedAccounts, ownedAccountsVersion, cacheDirectory, 'OwnedAccounts')

	print("Committed state updated to start of block {}".format(state._currentBlockIndex), file=out)

	while len(toProcess) > 0:
		## advance in memory state
		_processBlock(host, state, ownedAccounts, blockHash, 'in memory', out=out)
		popped = toProcess.popleft()
		blockIndex += 1
		blockHash = popped
	_processBlock(host, state, ownedAccounts, blockHash, 'in memory', out=out)
	blockIndex += 1

	assert state._currentBlockIndex == blockIndex
	print("In memory state updated to end of block {}".format(state._currentBlockIndex - 1), file=out)

	# note that the best block chain may have changed during the above
	# and so the following set of memory pool transactions may not correspond to the actual block chain endpoint we synchronised to
	# and this may then result in us trying to make double spends, in certain situations
	# the host should then refuse these transactions, and so this is not a disaster
	# (and double spend situations can probably also arise more generally in the case of block chain forks, with it not possible for us to always prevent this)
	# but we can potentially be more careful about this by checking best block chain after getting memory pool transactions
	# and restarting the block chain traversal if this does not match up
	memPoolTransactions = host.getMemPoolTransactions()
	_processTransactions(host, state, ownedAccounts, memPoolTransactions, includePending, 'in memory pool', out)

	return state, ownedAccounts

#def LoadAndReturnStateWithoutUpdate(config):
	#try:
		#blockIndex, blockHash, state = _load()
	#except ReindexingRequiredException as e:
		#print('Could not load cached state, so returning empty initial state! (' + str(e) + ')')
	#return state
