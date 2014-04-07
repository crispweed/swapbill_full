from __future__ import print_function
import sys, time, requests, json

class Host(object):

	def __init__(self, url):
		self._url = url
		self._request_session = requests.Session()

	def __connect(self, payload, headers):
		TRIES = 12
		for i in range(TRIES):
			try:
				response = self._request_session.post(self._url, data=json.dumps(payload), headers=headers)
				if i > 0: print('Successfully connected.', file=sys.stderr)
				return response
			except requests.exceptions.ConnectionError:
				print('Could not connect to litecoind. Sleeping for five seconds. (Try {}/{})'.format(i+1, TRIES), file=sys.stderr)
				time.sleep(5)
		return None

	def call_ReturnResultOrError(self, method, *params):
		headers = {'content-type': 'application/json'}
		payload = {
	        "method": method,
	        "params": list(params),
	        "jsonrpc": "2.0",
	        "id": 0,
	    }
		response = self.__connect(payload, headers)
		if response == None:
			raise Exception('Cannot connect to litecoind for remote procedure call.')
		elif response.status_code not in (200, 500):
			raise Exception('RPC connection failure: ' + str(response.status_code) + ' ' + response.reason)
		response_json = response.json()
		if 'error' in response_json.keys() and response_json['error'] != None:
			return (False, response_json['error'])
		return (True, response_json['result'])

	def call(self, method, *params):
		(success, resultOrError) = self.call_ReturnResultOrError(method, *params)
		if success:
			return resultOrError
		raise Exception('Error in remote procedure call: {}'.format(resultOrError))
