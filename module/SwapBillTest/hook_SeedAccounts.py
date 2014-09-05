from SwapBill import SeedAccounts

def _hook(protocol):
	return None, None, None, None, None

SeedAccounts.GetSeedAccountInfo = _hook

