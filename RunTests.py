import sys, unittest
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True

## the following can be used to help find uncommented print statements
class RaisingOutputStream(object):
	def write(self, s):
		raise Exception('RaisingOutputStream.write() called!')
#sys.stdout = RaisingOutputStream()

basePath = path.join(scriptPath, 'module', 'SwapBillTest')

if len(sys.argv) > 1:
	if len(sys.argv) > 2:
		unittest.defaultTestLoader.testMethodPrefix = sys.argv[2]
	suite = unittest.defaultTestLoader.discover(basePath, pattern=sys.argv[1])
else:
	suite = unittest.defaultTestLoader.discover(basePath)

unittest.TextTestRunner().run(suite)