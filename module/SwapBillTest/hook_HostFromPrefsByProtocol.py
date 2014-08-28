from __future__ import print_function
from SwapBill import HostFromPrefsByProtocol

currentHost = None

def _hook(protocol, configFile, dataDir):
	return currentHost

HostFromPrefsByProtocol.HostFromPrefsByProtocol = _hook
