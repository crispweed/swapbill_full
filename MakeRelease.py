from __future__ import print_function
import sys, shutil, os
from os import path
scriptPath = path.dirname(path.abspath(__file__))
sys.path.append(path.join(scriptPath, 'module'))
sys.dont_write_bytecode = True

privateRoot = scriptPath

publicRoot = path.join(scriptPath, '..', 'public_swapbill')
if not path.exists(publicRoot):
	os.mkdir(publicRoot)

for entry in os.listdir(publicRoot):
	if entry == '.git':
		continue
	pathedEntry = path.join(publicRoot, entry)
	if path.isdir(pathedEntry):
		shutil.rmtree(pathedEntry)
		continue
	assert path.isfile(pathedEntry)
	os.remove(pathedEntry)

for entry in ('Client.py', 'README.md'):
	shutil.copy2(path.join(privateRoot, entry), path.join(publicRoot, entry))
shutil.copytree(path.join(privateRoot, 'module', 'SwapBill'), path.join(publicRoot, 'module', 'SwapBill'))

docsFrom = path.join(privateRoot, 'docs')
docsTo = path.join(publicRoot, 'docs')
os.mkdir(docsTo)

for entry in os.listdir(docsFrom):
	if entry in ('makefile', '_build'):
		continue
	pathedEntry = path.join(docsFrom, entry)
	if path.isdir(pathedEntry):
		shutil.copytree(pathedEntry, path.join(docsTo, entry))
	else:
		shutil.copy2(pathedEntry, path.join(docsTo, entry))
