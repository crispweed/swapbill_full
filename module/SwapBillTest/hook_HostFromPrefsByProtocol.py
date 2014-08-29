from __future__ import print_function
from SwapBill import HostFromPrefsByProtocol

currentHostByProtocol = {}

def _hook(protocol, configFile, dataDir):
	return currentHostByProtocol[protocol]

HostFromPrefsByProtocol.HostFromPrefsByProtocol = _hook
