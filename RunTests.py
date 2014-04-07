import sys, unittest
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))

suite = unittest.defaultTestLoader.discover(path.join(scriptPath, 'module', 'SwapBill'))
unittest.TextTestRunner().run(suite)
