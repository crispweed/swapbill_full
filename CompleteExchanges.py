from __future__ import print_function
import sys, time
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import ClientMain
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

def getMatchingExchange(result, backerID):
	for s, key, d in result:
		if d.get('backer id', None) != backerID:
			continue
		if d['blocks until expiry'] > 40:
			# not enough confirmations
			continue
		return key, d
	return None, None

while True:
	for host in ['litecoin', 'bitcoin']:
		try:
			#-i option is important here, as this prevents us completing the same exchange multiple times!
			result = ClientMain.Main(commandLineArgs=['--host', host, 'get_pending_exchanges', '-i'])
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
			result = ClientMain.Main(commandLineArgs=['--host', host, 'complete_sell', '--pendingExchangeID', str(exchangeID)])
		except ExceptionReportedToUser as e:
			print("complete_sell failed:", e)
		time.sleep(40)
