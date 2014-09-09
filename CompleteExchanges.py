from __future__ import print_function
import sys, time
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import ClientMain
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser
from SwapBill.HardCodedProtocolConstraints import Constraints

def getMatchingExchange(result, backerID):
	for s, key, d in result:
		if d.get('backer id', None) != backerID:
			continue
		if d['blocks until expiry'] > Constraints.blocksForExchangeCompletion - 10:
			# not enough confirmations
			continue
		return key, d
	return None, None

startBlockIndex=305846
startBlockHash='f7598a6372065a3707b1ea31921dc281af40fd50ef54dc123f7d51a7c33fd252'

while True:
	try:
		#-i option is important here, as this prevents us completing the same exchange multiple times!
		result = ClientMain.Main(commandLineArgs=['get_pending_exchanges', '-i'], startBlockIndex=startBlockIndex, startBlockHash=startBlockHash)
	except ExceptionReportedToUser as e:
		print("get_pending_exchanges failed:", e)
		time.sleep(40)
		continue
	exchangeID, exchangeDetails = getMatchingExchange(result, 0)
	if exchangeID is None:
		time.sleep(40)
		continue
	# go ahead and complete
	try:
		result = ClientMain.Main(commandLineArgs=['complete_sell', '--pendingExchangeID', str(exchangeID)], startBlockIndex=startBlockIndex, startBlockHash=startBlockHash)
	except ExceptionReportedToUser as e:
		print("complete_sell failed:", e)
	time.sleep(40)
