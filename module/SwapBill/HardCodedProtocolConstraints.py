class Constraints(object):
	minimumSwapBillBalance = 10000000
	depositDivisor = 16
	paramsByHost = {
	    'bitcoin':{
	        'startBlock':274350,
	        'startBlockHash':'0000000085668e8f7c910f1fbdac5db77794e979a917e4105fe0bb37042204bd',
	        'minimumHostExchangeAmount':10000,
	        'blocksForExchangeCompletion':15
	    },
	    'litecoin':{
	        'startBlock':305846,
	        'startBlockHash':'f7598a6372065a3707b1ea31921dc281af40fd50ef54dc123f7d51a7c33fd252',
	        'minimumHostExchangeAmount':1000000,
	        'blocksForExchangeCompletion':50
	    }
	}
