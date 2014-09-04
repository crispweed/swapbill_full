
def GetSeedAccountInfo(protocol):
	infoByProtocol = {
        'bitcoin':(('75ed9fe49c67de7cefa5b5f87b6ddf09be75cad4be992640c5118789cec4c422',1),200),
        'litecoin':(('f92b02286e7b1c1e776cea0a67f48cec0f89243ddd6c4cfbbd43feefc6e73f94',1),20000),
    }
	return infoByProtocol[protocol]
