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

suite = unittest.defaultTestLoader.discover(path.join(scriptPath, 'module', 'SwapBillTest'))
unittest.TextTestRunner().run(suite)
