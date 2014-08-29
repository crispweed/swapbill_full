from __future__ import print_function
from SwapBillTest import MockHost
from SwapBill import HostFromPrefsByProtocol
from SwapBill.HardCodedProtocolConstraints import Constraints

currentHostByProtocol = {}

def _hook(protocol, dataDir):
	return currentHostByProtocol[protocol]

HostFromPrefsByProtocol.HostFromPrefsByProtocol = _hook

def Reset():
	for key in Constraints.paramsByHost:
		params = Constraints.paramsByHost[key]
		currentHostByProtocol[key] = MockHost.MockHost(params['startBlock'], params['startBlockHash'])
	
Reset()
