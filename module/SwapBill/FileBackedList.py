from __future__ import print_function
import ecdsa, hashlib, os, binascii

class FileBackedList(object):
	def __init__(self, fileName):
		self._fileName = fileName
		self._entries = []
		if os.path.exists(fileName):
			with open(fileName, mode='r') as f:
				lines = f.readlines()
				for line in lines:
					assert line[-1:] == '\n'
					lineHex = line[:-1]
					byteBuffer = binascii.unhexlify(lineHex.encode('ascii'))
					self._entries.append(byteBuffer)

	def addEntry(self, byteBuffer):
		self._entries.append(byteBuffer)
		with open(self._fileName, mode='a') as f:
			f.write(binascii.hexlify(byteBuffer).decode('ascii'))
			f.write('\n')

	def hasEntry(self, byteBuffer):
		return byteBuffer in self._entries
