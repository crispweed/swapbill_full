from __future__ import print_function
import unittest, os
from SwapBill import FileBackedList

file = 'testFile.txt'

class Test(unittest.TestCase):
	def test(self):
		if os.path.exists(file):
			os.remove(file)
		l = FileBackedList.FileBackedList(file)
		entries = [b'123', b'456']
		for entry in entries:
			l.addEntry(entry)
		for entry in entries:
			self.assertTrue(l.hasEntry(entry))
		self.assertFalse(l.hasEntry(b'notAdded'))
		entries.append(b'78')
		l.addEntry(b'78')
		l = FileBackedList.FileBackedList(file)
		for entry in entries:
			self.assertTrue(l.hasEntry(entry))
		self.assertFalse(l.hasEntry(b'notAdded'))
		os.remove(file)

