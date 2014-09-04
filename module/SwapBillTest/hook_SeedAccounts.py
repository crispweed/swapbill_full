from SwapBill import SeedAccounts

def _hook(protocol):
	return None, None

SeedAccounts.GetSeedAccountInfo = _hook

