import sys
PY3 = sys.version_info.major > 2

if PY3:
	def Convert(jsonData):
		return jsonData
else:
	def Convert(jsonData):
		if type(jsonData) is dict:
			newDict = {}
			for key in jsonData:
				value = jsonData[key]
				newDict[Convert(key)] = Convert(value)
			return newDict
		if type(jsonData) is list:
			newList = []
			for item in jsonData:
				newList.append(Convert(item))
			return newList
		if type(jsonData) is unicode:
			return jsonData.encode('ascii')
		return jsonData

