class Constraints(object):
	minimumSwapBillBalance = 10000000
	depositDivisor = 16
	paramsByHost = {
	    'bitcoin':{
	        'startBlock':278806,
	        'startBlockHash':'0000000041c3b90e37151337a4c24c122ffa4293741fe0091829a56bcbcb25ec',
	        'minimumHostExchangeAmount':10000,
	        'blocksForExchangeCompletion':15
	    },
	    'litecoin':{
	        'startBlock':381056,
	        'startBlockHash':'001fcb8344b4da5b8d309c6771d94dcd4dfb002073048920fab75d3fc23c9d22',
	        'minimumHostExchangeAmount':1000000,
	        'blocksForExchangeCompletion':50
	    }
	}
