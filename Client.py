from __future__ import print_function
import sys
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import ClientMain
from SwapBill.ExceptionReportedToUser import ExceptionReportedToUser

try:
	ClientMain.Main(startBlockIndex=241432, startBlockHash='3fa2cf2d644b74b7f6407a1d3a9d15ad98f85da9adecbac0b1560c11c0393eed')
except ExceptionReportedToUser as e:
	print("Operation failed:", e)
