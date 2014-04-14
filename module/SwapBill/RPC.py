from __future__ import print_function
import time, requests, json
#from SwapBill.ConvertJSONToNativeStrings import Convert

class Host(object):
	def __init__(self, url):
		self._session = requests.Session()
		self._url = url
		self._headers = {'content-type': 'application/json'}
	def call(self, rpcMethod, *params):
		#payload = json.dumps({"method": rpcMethod, "params": list(params), "jsonrpc": "2.0", "id": 0})
		payload = json.dumps({"method": rpcMethod, "params": list(params), "jsonrpc": "2.0"})
		tries = 10
		hadConnectionFailures = False
		while True:
			try:
				response = self._session.get(self._url, headers=self._headers, data=payload)
				#response = requests.get(self._url, headers=self._headers, data=payload)
			except requests.exceptions.ConnectionError:
				tries -= 1
				if tries == 0:
					raise Exception('Failed to connect for remote procedure call.')
				hadFailedConnections = True
				print("Couldn't connect for remote procedure call, will sleep for ten seconds and then try again ({} more tries)".format(tries))
				time.sleep(10)
			else:
				if hadConnectionFailures:
					print('Connected for remote procedure call after retry.')
				break
		if response.status_code != 200:
			raise Exception('RPC connection failure: ' + str(response.status_code) + ' ' + response.reason)
		responseJSON = response.json()
		if 'error' in responseJSON and responseJSON['error'] != None:
			raise Exception('Error in RPC call: ' + str(responseJSON['error']))
		#return Convert(responseJSON['result'])
		return responseJSON['result']
