#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Copyright (c) 2016 pyReScene
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

# Enable Unicode string literals by default because non-ASCII strings are
# used and Python 3.2 does not support the u"" syntax. Also, Python 2.6's
# bytearray.fromhex() only accepts Unicode strings. However the "struct"
# module does not support Unicode format strings until Python 3, so they have
# to be wrapped in str() calls.
from __future__ import unicode_literals

import unittest
from rescene.rar5 import *
from rescene import rar5

# for running nose tests
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class TestRar5Reader(unittest.TestCase):
	""" For testing Rar5Reader.
		Rar5Reader parses the incoming file or stream. """

	path = os.path.join(os.pardir, os.pardir, "test_files")
	folder = "rar5"
	
	def test_read_rar4(self):
		rfile = os.path.join(self.path, "store_little", "store_little.rar")
		rr = Rar5Reader(rfile)
		self.assertRaises(ValueError, rr.next)

	def test_read_nothing(self):
		"""We expect None back if we read one time to much."""
		rfile = os.path.join(self.path, "whatever", "file.rar")
		self.assertRaises(ArchiveNotFoundError, Rar5Reader, rfile)

	def test_read_sfx(self):
		stream = io.BytesIO()
		stream.write(b"Random binary data...")
		stream.name = "name to imitate real file"
		rr = Rar5Reader(stream)
		self.assertRaises(StopIteration, rr.next)
		stream.seek(0, os.SEEK_SET)
		rr = Rar5Reader(stream)
		self.assertRaises(StopIteration, rr.next)
		# TODO: SFX support not implemented

	def test_read_all_blocks(self):
		rfile = os.path.join(self.path, self.folder, "rar5_compressed.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
		rfile = os.path.join(self.path, self.folder, "rar5_test.rar")
		for r in Rar5Reader(rfile):
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
			
	def test_read_more(self):
		rfile = os.path.join(self.path, self.folder, "rar5_test.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
			print(r.explain())
		
	def test_read_more_weird(self):
		rfile = os.path.join(self.path, self.folder, "txt.rar")
		rr = Rar5Reader(rfile)
		for r in rr:
			block_info = r.explain()
			self.assertTrue(block_info, "Must not be None or empty")
			print(r.explain())

	def test_stackoverflow(self):
		data = b"\x33\x92\xb5\xe5\x0a\x01\x05\x06\x00\x05\x01\x01\x00"
		stream = io.BytesIO(data)
		block = BlockFactory.create(stream, False)

class TestParseRarBlocks(unittest.TestCase):
	""" For use with Rar5Reader.
		Rar5Reader parses the incoming file or stream. """

	def test_marker_rar5_start(self):
		header = b"Rar!\x1A\x07\x01\x00"
		stream = io.BytesIO(header)
		block = BlockFactory.create(stream, is_start_file=True)
		self.assertTrue(isinstance(block, MarkerBlock), "incorrect block type")
		self.assertTrue(isinstance(block.basic_header, Rar5HeaderMarker),
			"marker block: bad type for header")
		self.assertTrue(not block.is_srr, "bad default file format")
		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.header_size, 8)
		self.assertEqual(h.size_data, 0)
		self.assertEqual(h.size_extra, 0)
		self.assertEqual(h.type, BLOCK_MARKER)

	def test_marker_rar4_start(self):
		header = b"Rar!\x1A\x07\x00"
		stream = io.BytesIO(header)
		self.assertRaises(
			ValueError, 
			BlockFactory.create,
			stream,
			is_start_file=True)
		
	def test_end_of_archive_header(self):
		crc = 0x12345678
		hcrc32_enc = struct.pack('<L', crc)
		htype = BLOCK_END
		htype_enc = encode_vint(htype)
		hflags = RAR_SKIP
		hflags_enc = encode_vint(hflags)
		heoa_flags = END_NOT_LAST_VOLUME
		heoa_flags_enc = encode_vint(heoa_flags)

		hsize = len(htype_enc) + len(hflags_enc) + len(heoa_flags_enc)
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(b"whatever")
		stream.write(hcrc32_enc)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(heoa_flags_enc)
		stream.seek(len(b"whatever"), os.SEEK_SET)
		block = BlockFactory.create(stream, is_start_file=False)
		is_end_block = isinstance(block, EndArchiveBlock)
		self.assertTrue(is_end_block, "archive end block expected")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")
		self.assertFalse(block.is_srr, "bad default file format")

		h = block.basic_header
		self.assertEqual(h.block_position, len(b"whatever"))
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_END)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(block.end_of_archive_flags, heoa_flags)
		self.assertEqual(block.is_last_volume(), False)

	def test_main_archive_header(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_MAIN
		htype_enc = encode_vint(htype)
		hflags = RAR_EXTRA ^ RAR_SPLIT_AFTER
		self.assertFalse(hflags & RAR_DATA, "never possible on main")
		hflags_enc = encode_vint(hflags)
		harchive_flags = ARCHIVE_VOLUME ^ ARCHIVE_NUMBER
		harchive_flags_enc = encode_vint(harchive_flags)
		hvolume_number = 1
		hvolume_number_enc = encode_vint(hvolume_number)

		locator_record = io.BytesIO()
		ltype = encode_vint(LOCATOR_RECORD)
		lflags = encode_vint(LOCATOR_QUICK ^ LOCATOR_RR)
		quick_open_offset = 12345
		lqoo = encode_vint(quick_open_offset)
		recovery_record_offset = 23456
		lrro = encode_vint(recovery_record_offset)
		lsize = len(ltype) + len(lflags) + len(lqoo) + len(lrro)
		locator_record.write(encode_vint(lsize))
		locator_record.write(ltype)
		locator_record.write(lflags)
		locator_record.write(lqoo)
		locator_record.write(lrro)
		locator_record.seek(0)
		extra_area = locator_record.read()
		hextra_size = encode_vint(len(extra_area))

		hsize = (4 + 3 + len(htype_enc) + len(hflags_enc) +
			len(hextra_size) + len(harchive_flags_enc) + 1)
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hextra_size)
		stream.write(harchive_flags_enc)
		stream.write(hvolume_number_enc)
		stream.write(extra_area)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		is_main_block = isinstance(block, MainArchiveBlock)
		self.assertTrue(is_main_block, "incorrect block type")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")
		self.assertFalse(block.is_srr, "bad default file format")

		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_MAIN)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(h.size_extra, len(extra_area))

		self.assertEqual(block.archive_flags, harchive_flags)
		self.assertEqual(block.volume_number, hvolume_number)
		self.assertEqual(block.quick_open_offset, quick_open_offset)
		self.assertEqual(block.recovery_record_offset, recovery_record_offset)
		self.assertEqual(block.undocumented_value, 0)
		
		self.assertEqual(h.size_data, 0)

	def test_encryption_header(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_ENCRYPTION
		htype_enc = encode_vint(htype)
		hflags = 0
		hflags_enc = encode_vint(hflags)
		enc_version = 0  # AES-265
		henc_version = encode_vint(enc_version)
		enc_flags = ENCRYPTION_PASSWORD_CHECK
		henc_flags= encode_vint(enc_flags)
		kdf_count = 13
		hkdf_count = struct.pack('<B', kdf_count)  # 1 byte
		salt = b"0123456701234567"  # 16 bytes
		check_value = b"012345678912"  # 12 bytes
		
		hsize = (4 + len(htype_enc) + len(hflags_enc) +
			len(henc_version) + len(henc_flags) + 1 + 16 + 12)
		hsize_enc = encode_vint(hsize)
		self.assertEqual(len(hsize_enc), 1, "not same size")
		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(henc_version)
		stream.write(henc_flags)
		stream.write(hkdf_count)
		stream.write(salt)
		stream.write(check_value)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		is_enc_block = isinstance(block, FileEncryptionBlock)
		self.assertTrue(is_enc_block, "incorrect block type")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")

		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_ENCRYPTION)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(h.size_extra, 0)
		self.assertEqual(h.size_data, 0)
		self.assertEqual(block.encryption_version, enc_version)
		self.assertEqual(block.encryption_flags, enc_flags)
		self.assertEqual(block.kdf_count, hkdf_count)
		self.assertEqual(block.salt, salt)
		self.assertEqual(block.check_value, check_value)

	def test_file_header(self):
		crc = 0x12345678
		hcrc32 = struct.pack('<L', crc)
		htype = BLOCK_FILE
		htype_enc = encode_vint(htype)
		hflags = RAR_EXTRA ^ RAR_DATA ^ RAR_SPLIT_AFTER
		hflags_enc = encode_vint(hflags)
		extra_size = 11
		data_size = 22
		hextra_size = encode_vint(extra_size)
		hdata_size = encode_vint(data_size)

		hfile_flags = FILE_UNIX_TIME ^ FILE_CRC32 
		hfile_flags_enc = encode_vint(hfile_flags)
		hunpacked_size = data_size
		hunpacked_size_enc = encode_vint(hunpacked_size)
		attributes = 0
		hattributes_enc = encode_vint(attributes)
		mtime = 0
		hmtime = struct.pack('<L', mtime)
		data_crc32 = 0x12345678
		hdata_crc32 = struct.pack('<L', data_crc32)
		compression_info = 0
		hcompression_info_enc = encode_vint(compression_info)
		host_os = 1  # Unix
		hhost_os_enc = encode_vint(host_os)
		name = b"test_file_name.ext"
		name_length = len(name)
		hname_length_enc = encode_vint(name_length)
		
		extra = b"x" * extra_size
		data = b"y" * data_size
		
		# size starts from header type
		hsize = (len(htype_enc) + len(hflags_enc) +
			len(hextra_size) + len(hdata_size) +
			len(hfile_flags_enc) + len(hunpacked_size_enc) +
			len(hattributes_enc) + 8 + len(hcompression_info_enc) +
			len(hhost_os_enc) +
			len(hname_length_enc) + len(name) + 
			extra_size)
		hsize_enc = encode_vint(hsize)

		stream = io.BytesIO()
		stream.write(hcrc32)
		stream.write(hsize_enc)
		stream.write(htype_enc)
		stream.write(hflags_enc)
		stream.write(hextra_size)
		stream.write(hdata_size)
		stream.write(hfile_flags_enc)
		stream.write(hunpacked_size_enc)
		stream.write(hattributes_enc)
		stream.write(hmtime)
		stream.write(hdata_crc32)
		stream.write(hcompression_info_enc)
		stream.write(hhost_os_enc)
		stream.write(hname_length_enc)
		stream.write(name)
		stream.write(extra)
		stream.write(data)
		stream.seek(0, os.SEEK_SET)

		block = BlockFactory.create(stream, is_start_file=False)
		is_file_block = isinstance(block, FileServiceBlock)
		self.assertTrue(is_file_block, "incorrect block type")
		is_header = isinstance(block.basic_header, Rar5HeaderBlock)
		self.assertTrue(is_header, "bad type for header")
		self.assertFalse(block.is_srr, "bad default file format")

		h = block.basic_header
		self.assertEqual(h.block_position, 0)
		self.assertEqual(h.crc32, crc)
		self.assertEqual(h.header_size, hsize)
		self.assertEqual(h.type, BLOCK_FILE)
		self.assertEqual(h.flags, hflags)
		self.assertEqual(h.size_extra, extra_size)
		self.assertEqual(h.size_data, data_size)

		self.assertEqual(block.file_flags, hfile_flags)
		self.assertEqual(block.unpacked_size, hunpacked_size)
		self.assertEqual(block.attributes, attributes)
		self.assertEqual(block.mtime, mtime)
		self.assertEqual(block.datacrc32, data_crc32)
		self.assertEqual(block.algorithm, 0)
		self.assertEqual(block.solid, 0)
		self.assertEqual(block.method, 0)
		self.assertEqual(block.dict_size, 0)
		self.assertEqual(block.host_os, host_os)
		self.assertEqual(block.name, name)
		self.assertEqual(block.extra_area_size, extra_size)
		self.assertEqual(h.size_data, data_size)

	def test_file_encryption_record(self):
		rtype = 0x01
		type_enc = encode_vint(rtype)
		version = 0  # AES-265
		version_enc = encode_vint(version)
		flags = RECORD_PASSWORD_CHECK 
		flags_enc = encode_vint(flags)
		kdf_count = S_BYTE.pack(1)
		salt = b"0123456701234567"  # 16 bytes
		iv = b"0123456701234567"  # 16 bytes
		check_value = b"012345678901"  # 12 bytes
		
		size = (len(type_enc) + len(version_enc) + 
			len(flags_enc) + 1 + 16 + 16 + 12)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(version_enc)
		stream.write(flags_enc)
		stream.write(kdf_count)
		stream.write(salt)
		stream.write(iv)
		stream.write(check_value)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.version, version)
		self.assertEqual(record.flags, flags)
		self.assertEqual(record.kdf_count, kdf_count)
		self.assertEqual(record.salt, salt)
		self.assertEqual(record.iv, iv)
		self.assertEqual(record.check_value, check_value)

	def test_file_hash_record(self):
		rtype = 0x02
		type_enc = encode_vint(rtype)
		rhash = 0
		hash_enc = encode_vint(rhash)
		hash_data = b"0" * 32
		
		size = (len(type_enc) + len(hash_enc) + 
			len(hash_data))

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(hash_enc)
		stream.write(hash_data)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.hash, rhash)
		self.assertEqual(record.hash_data, hash_data)

	def test_file_time_record(self):
		rtype = 0x03
		type_enc = encode_vint(rtype)
		rflags = TIME_UNIX ^ TIME_MODIFICATION ^ TIME_CREATION
		flags_enc = encode_vint(rflags)
		mtime = b"0" * 4
		ctime = b"1" * 4
		
		size = len(type_enc) + len(flags_enc) + len(mtime) + len(ctime)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(flags_enc)
		stream.write(mtime)
		stream.write(ctime)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.mtime, mtime)
		self.assertEqual(record.ctime, ctime)

	def test_file_version_record(self):
		rtype = 0x04
		type_enc = encode_vint(rtype)
		rflags = 0
		flags_enc = encode_vint(rflags)
		file_version_number = 42
		version_enc = encode_vint(file_version_number) 
		
		size = len(type_enc) + len(flags_enc) + len(version_enc)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(flags_enc)
		stream.write(version_enc)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.version_number, file_version_number)

	def test_file_redirection_record(self):
		rtype = 0x05
		type_enc = encode_vint(rtype)
		redirection_type = 1
		redirection_type_enc = encode_vint(redirection_type)
		rflags = LINK_DIRECTORY
		flags_enc = encode_vint(rflags)
		name = b"test_file_name.ext"
		name_length = len(name)
		name_length_enc = encode_vint(name_length)
		
		size = (len(type_enc) + len(redirection_type_enc) + 
			len(flags_enc) + len(name_length_enc) + name_length)

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(redirection_type_enc)
		stream.write(flags_enc)
		stream.write(name_length_enc)
		stream.write(name)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.redirection_type, redirection_type)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.name, name)

	def test_file_unix_owner_record(self):
		rtype = 0x06
		type_enc = encode_vint(rtype)
		rflags = UNIX_USER ^ UNIX_USER_ID ^ UNIX_GROUP ^ UNIX_GROUP_ID
		flags_enc = encode_vint(rflags)
		user_name = b"gfy"
		group_name = b"root"
		user_name_len_enc = encode_vint(len(user_name))
		group_name_len_enc = encode_vint(len(group_name))
		user_id = 1337
		user_id_enc = encode_vint(user_id)
		group_id = 1337
		group_id_enc = encode_vint(group_id)

		size = (len(type_enc) + len(flags_enc) + 
			len(user_name_len_enc) + len(user_name) +
			len(group_name_len_enc) + len(group_name) +
			len(user_id_enc) + len(group_id_enc))

		stream = io.BytesIO()
		stream.write(encode_vint(size))
		stream.write(type_enc)
		stream.write(flags_enc)
		stream.write(user_name_len_enc)
		stream.write(user_name)
		stream.write(group_name_len_enc)
		stream.write(group_name)
		stream.write(user_id_enc)
		stream.write(group_id_enc)
		stream.seek(0)

		record = file_service_record_factory(stream)
		self.assertEqual(record.type, rtype)
		self.assertEqual(record.size, size)
		self.assertEqual(record.flags, rflags)
		self.assertEqual(record.owner, user_name)
		self.assertEqual(record.group, group_name)
		self.assertEqual(record.user_id, user_id)
		self.assertEqual(record.group_id, group_id)

	def test_file_unix_service_data_record(self):
		pass

class TestRar5Vint(unittest.TestCase):
	"""Tests the rar 5 vint"""
	def test_read_vint(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\x81")
		stream.write(b"\x01")
		stream.seek(0)
		number = read_vint(stream)
		self.assertEqual(number, 16384 + 129, "128 bit is in the next byte")

	def test_read_vint_single_byte_all_bits(self):
		stream = io.BytesIO()
		stream.write(b"\x7F")  # first bit not set
		stream.seek(0)
		number = read_vint(stream)
		self.assertEqual(number, 255 - 128, "max value single vint byte")

	def test_read_vint_zeros(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\x82")
		stream.write(b"\x00")  # allocated bits without influence
		stream.seek(0)
		number = read_vint(stream)
		self.assertEqual(number, 257, "256 bit is in the next byte")
		
	def test_write_vint(self):
		stream = io.BytesIO()
		stream.write(b"\x81")
		stream.write(b"\xF1")
		stream.write(b"\x81")
		stream.write(b"\x01")
		stream.seek(0)
		number = read_vint(stream)
		serialized = encode_vint(number)
		tnumber = read_vint(io.BytesIO(serialized))
		self.assertEqual(tnumber, number, "encoding to vint and back failed")
