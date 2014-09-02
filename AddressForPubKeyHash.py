from __future__ import print_function
import sys, argparse, traceback, struct
import csv
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True
from SwapBill import Address
from SwapBill import Util

pubKeyHash = Util.fromHex(sys.argv[1])
print(Address.FromPubKeyHash(b'\x6f', pubKeyHash))
