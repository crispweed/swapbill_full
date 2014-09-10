from __future__ import print_function
from SwapBillTest import MockHost
from SwapBill import HostFromPrefsByProtocol
from SwapBill import ProtocolParameters

currentHostByProtocol = {}

def _hook(protocol, dataDir):
	return currentHostByProtocol[protocol]

HostFromPrefsByProtocol.HostFromPrefsByProtocol = _hook

def Reset():
	for key in ProtocolParameters.byHost:
		params = ProtocolParameters.byHost[key]
		currentHostByProtocol[key] = MockHost.MockHost(params['startBlock'], params['startBlockHash'])

def Reset_BeforeStartBlock():
	for key in ProtocolParameters.byHost:
		params = ProtocolParameters.byHost[key]
		currentHostByProtocol[key] = MockHost.MockHost(params['startBlock']-1, 'madeUpBlockHash')
	
Reset()
