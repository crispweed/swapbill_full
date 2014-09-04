from SwapBill import Util

def GetSeedAccountInfo(protocol):
	infoByProtocol = {
        'bitcoin':(('75ed9fe49c67de7cefa5b5f87b6ddf09be75cad4be992640c5118789cec4c422',1),20000000000,Util.fromHex('4df3b872247f30b65c92c35a00573f8993ceb25f'), '76a9141060f72f86f6f3bb7a91b2064bc5671adcc0fcd988ac'),
        'litecoin':(('f92b02286e7b1c1e776cea0a67f48cec0f89243ddd6c4cfbbd43feefc6e73f94',1),2000000000000,Util.fromHex('1060f72f86f6f3bb7a91b2064bc5671adcc0fcd9'), '76a9144df3b872247f30b65c92c35a00573f8993ceb25f88ac'),
    }
	return infoByProtocol[protocol]
