#!/usr/bin/env python

from __future__ import with_statement, division, print_function

import os
import sys
import struct

try:
	import llfuse
except ImportError:
	HAS_LLFUSE = False
else:
	HAS_LLFUSE = True

__all__ = 'read_index', 'pack', 'unpack', 'unpack_files', 'pack_buffers', 'pack_files', \
          'write_entry_header', 'print_list', 'mount'

# for Python < 3.3 and Windows
def highlevel_sendfile(outfile,infile,offset,size):
	infile.seek(offset,0)
	while size > 0:
		if size > 2 ** 20:
			chunk_size = 2 ** 20
		else:
			chunk_size = size
		size -= chunk_size
		data = infile.read(chunk_size)
		outfile.write(data)
		if len(data) < chunk_size:
			raise IOError("unexpected end of file")

if hasattr(os, 'sendfile'):
	def sendfile(outfile,infile,offset,size):
		try:
			out_fd = outfile.fileno()
			in_fd  = infile.fileno()
		except:
			highlevel_sendfile(outfile,infile,offset,size)
		else:
			# size == 0 has special meaning for some sendfile implentations
			if size > 0:
				os.sendfile(out_fd, in_fd, offset, size)
else:
	sendfile = highlevel_sendfile

def read_index(stream):
	filecount = stream.read(4) # unknown header data
	if len(filecount) < 4:
		raise IOError("unexpected end of file while reading number of files")
	
	filecount, = struct.unpack("<I",filecount)
	i = 0
	while i < filecount:
		namelen = stream.read(1)
		if not namelen:
			break
		namelen, = struct.unpack("B", namelen)
		name = stream.read(namelen)
		if len(name) < namelen:
			raise IOError("unexpected end of file while reading file name")
		name = name.decode("latin1")
		if os.path.sep != "\\":
			name = name.replace("\\",os.path.sep)
		size = stream.read(4)
		offset = stream.tell()
		if len(size) < 4:
			raise IOError("unexpected end of file while reading file size")
		size, = struct.unpack("<I",size)
		yield name, offset, size
		stream.seek(offset + size, 0)
		if offset + size != stream.tell():
			raise IOError("error seeking to %u" % (offset + size))
		i += 1
	
	offset = stream.tell()
	stream.seek(0, 2)
	end = stream.tell()
	if offset < end:
		raise IOError("unexpected trailing %u byte(s)" % (end - offset))

def pack(stream,dirname,remove_ext=True,callback=lambda name: None):
	files = []
	for dirpath, dirnames, filenames in os.walk(dirname):
		for filename in filenames:
			files.append(os.path.join(dirpath,filename))
	_pack_files(stream,files,remove_ext,callback)

def unpack(stream,outdir=".",ext="",callback=lambda name: None):
	for name, offset, size in read_index(stream):
		unpack_file(stream,name,offset,size,outdir,ext,callback)

def shall_unpack(paths,name):
	path = name.split(os.path.sep)
	for i in range(1,len(path)+1):
		prefix = os.path.join(*path[0:i])
		if prefix in paths:
			return True
	return False

def unpack_files(stream,files,outdir=".",ext="",callback=lambda name: None):
	for name, offset, size in read_index(stream):
		if shall_unpack(files,name):
			unpack_file(stream,name,offset,size,outdir,ext,callback)

def unpack_file(stream,name,offset,size,outdir=".",ext="",callback=lambda name: None):
	prefix, name = os.path.split(name)
	prefix = os.path.join(outdir,prefix)
	if not os.path.exists(prefix):
		os.makedirs(prefix)
	name = os.path.join(prefix,name)+ext
	callback(name)
	with open(name,"wb") as fp:
		sendfile(fp,stream,offset,size)

def pack_buffers(stream,buffers,callback=lambda name: None):
	stream.write(struct.pack("<I",len(buffers)))
	for name, data in sorted(buffers,key=lambda item: item[0]):
		callback(name)
		write_entry_header(stream,name,len(data))
		stream.write(data)

def write_entry_header(stream,name,size):
	name = name.replace(os.path.sep,"\\").encode("utf-8")
	stream.write(struct.pack("B",len(name)))
	stream.write(name)
	stream.write(struct.pack("<I",size))

def pack_files(stream,files_or_dirs,remove_ext=True,callback=lambda name: None):
	files = []
	for name in files_or_dirs:
		if os.path.isdir(name):
			for dirpath, dirnames, filenames in os.walk(name):
				for filename in filenames:
					files.append(os.path.join(dirpath,filename))
		else:
			files.append(name)
	_pack_files(stream,files,remove_ext,callback)

def _pack_files(stream,files,remove_ext=True,callback=lambda name: None):
	files.sort()
	stream.write(struct.pack("<I",len(files)))
	for name in files:
		with open(name,"rb") as infile:
			infile.seek(0,2)
			size = infile.tell()
			if remove_ext:
				name = os.path.splitext(name)[0]
			callback(name)
			write_entry_header(stream,name,size)
			sendfile(stream,infile,0,size)

def human_size(size):
	if size < 2 ** 10:
		return str(size)
	
	elif size < 2 ** 20:
		size = "%.1f" % (size / 2 ** 10)
		unit = "K"

	elif size < 2 ** 30:
		size = "%.1f" % (size / 2 ** 20)
		unit = "M"

	elif size < 2 ** 40:
		size = "%.1f" % (size / 2 ** 30)
		unit = "G"

	elif size < 2 ** 50:
		size = "%.1f" % (size / 2 ** 40)
		unit = "T"

	elif size < 2 ** 60:
		size = "%.1f" % (size / 2 ** 50)
		unit = "P"

	elif size < 2 ** 70:
		size = "%.1f" % (size / 2 ** 60)
		unit = "E"

	elif size < 2 ** 80:
		size = "%.1f" % (size / 2 ** 70)
		unit = "Z"

	else:
		size = "%.1f" % (size / 2 ** 80)
		unit = "Y"
	
	if size.endswith(".0"):
		size = size[:-2]
	
	return size+unit

def print_list(stream,details=False,human=False,delim="\n",ext="",sort_func=None,out=sys.stdout):
	index = read_index(stream)

	if sort_func:
		index = sorted(index,cmp=sort_func)

	if details:
		if human:
			size_to_str = human_size
		else:
			size_to_str = str

		out.write("    Offset       Size Name%s" % delim)
		for name, offset, size in index:
			out.write("%10u %10s %s%s%s" % (offset, size_to_str(size), name, ext, delim))
	else:
		for name, offset, size in index:
			out.write("%s%s%s" % (name, ext, delim))

def add_common_args(parser):
	parser.add_argument('archive', help='FEZ .pak archive')
	parser.add_argument('-0','--print0',action='store_true',default=False,
		help='seperate file names with nil bytes')
	parser.add_argument('-v','--verbose',action='store_true',default=False,
		help='print verbose output')

SORT_ALIASES = {
	"s": "size",
	"S": "-size",
	"o": "offset",
	"O": "-offset",
	"n": "name",
	"N": "-name"
}

CMP_FUNCS = {
	"size":  lambda lhs, rhs: cmp(lhs[2], rhs[2]),
	"-size": lambda lhs, rhs: cmp(rhs[2], lhs[2]),

	"offset":  lambda lhs, rhs: cmp(lhs[1], rhs[1]),
	"-offset": lambda lhs, rhs: cmp(rhs[1], lhs[1]),

	"name":  lambda lhs, rhs: cmp(lhs[0], rhs[0]),
	"-name": lambda lhs, rhs: cmp(rhs[0], lhs[0])
}

def sort_func(sort):
	cmp_funcs = []
	for key in sort.split(","):
		key = SORT_ALIASES.get(key,key)
		try:
			func = CMP_FUNCS[key]
		except KeyError:
			raise ValueError("unknown sort key: "+key)
		cmp_funcs.append(func)

	def do_cmp(lhs,rhs):
		for cmp_func in cmp_funcs:
			i = cmp_func(lhs,rhs)
			if i != 0:
				return i
		return 0

	return do_cmp

if HAS_LLFUSE:
	from collections import OrderedDict
	import errno
	import weakref
	import stat
	import mmap

	class Entry(object):
		__slots__ = 'inode','_parent','__weakref__'

		def __init__(self,inode,parent=None):
			self.inode  = inode
			self.parent = parent

		@property
		def parent(self):
			return self._parent() if self._parent is not None else None

		@parent.setter
		def parent(self,parent):
			self._parent = weakref.ref(parent) if parent is not None else None

	class Dir(Entry):
		__slots__ = 'children',

		def __init__(self,inode,children=None,parent=None):
			Entry.__init__(self,inode,parent)
			if children is None:
				self.children = OrderedDict()
			else:
				self.children = children
				for child in children.values():
					child.parent = self

		def __repr__(self):
			return 'Dir(%r, %r)' % (self.inode, self.children)

	class File(Entry):
		__slots__ = 'offset', 'size'

		def __init__(self,inode,offset,size,parent=None):
			Entry.__init__(self,inode,parent)
			self.offset = offset
			self.size   = size

		def __repr__(self):
			return 'File(%r, %r, %r)' % (self.inode, self.offset, self.size)

	DIR_SELF   = '.'.encode(sys.getfilesystemencoding())
	DIR_PARENT = '..'.encode(sys.getfilesystemencoding())

	class Operations(llfuse.Operations):
		__slots__ = 'archive','root','inodes','arch_st','data'

		def __init__(self, archive, ext=""):
			super(Operations, self).__init__()
			self.archive = archive
			self.arch_st = os.fstat(archive.fileno())
			self.root    = Dir(1)
			self.inodes  = {self.root.inode: self.root}
			self.root.parent = self.root

			encoding = sys.getfilesystemencoding()
			inode = self.root.inode + 1
			for filename, offset, size in read_index(archive):
				path = filename.split(os.path.sep)
				path, name = path[:-1], path[-1]
				name += ext
				name = name.encode(encoding)

				parent = self.root
				for i, comp in enumerate(path):
					comp = comp.encode(encoding)
					try:
						entry = parent.children[comp]
					except KeyError:
						entry = parent.children[comp] = self.inodes[inode] = Dir(inode, parent=parent)
						inode += 1
						
					if type(entry) is not Dir:
						raise ValueError("name conflict in archive: %r is not a directory" % os.path.join(*path[:i+1]))

					parent = entry
				
				if name in parent.children:
					raise ValueError("name conflict in archive: %r already exists" % filename)

				parent.children[name] = self.inodes[inode] = File(inode, offset, size, parent)
				inode += 1

			archive.seek(0, 0)
			self.data = mmap.mmap(archive.fileno(), 0, access=mmap.ACCESS_READ)

		def destroy(self):
			self.data.close()
			self.archive.close()

		def lookup(self, parent_inode, name):
			try:
				if name == DIR_SELF:
					entry = self.inodes[parent_inode]

				elif name == DIR_PARENT:
					entry = self.inodes[parent_inode].parent

				else:
					entry = self.inodes[parent_inode].children[name]

			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)
			else:
				return self._getattr(entry)

		def _getattr(self, entry):
			attrs = llfuse.EntryAttributes()

			attrs.st_ino        = entry.inode
			attrs.st_rdev       = 0
			attrs.generation    = 0
			attrs.entry_timeout = 300
			attrs.attr_timeout  = 300

			if type(entry) is Dir:
				nlink = 2 if entry is not self.root else 1
				size  = 5

				for name, child in entry.children.items():
					size += len(name) + 1
					if type(child) is Dir:
						nlink += 1

				attrs.st_mode  = stat.S_IFDIR | 0o555
				attrs.st_nlink = nlink
				attrs.st_size  = size
			else:
				attrs.st_nlink = 1
				attrs.st_mode  = stat.S_IFREG | 0o444
				attrs.st_size  = entry.size

			arch_st = self.arch_st
			attrs.st_uid     = arch_st.st_uid
			attrs.st_gid     = arch_st.st_gid
			attrs.st_blksize = arch_st.st_blksize
			attrs.st_blocks  = 1 + ((attrs.st_size - 1) // attrs.st_blksize) if attrs.st_size != 0 else 0
			attrs.st_atime   = arch_st.st_atime
			attrs.st_mtime   = arch_st.st_mtime
			attrs.st_ctime   = arch_st.st_ctime

			return attrs

		def getattr(self, inode):
			try:
				entry = self.inodes[inode]
			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)
			else:
				return self._getattr(entry)

		def access(self, inode, mode, ctx):
			try:
				entry = self.inodes[inode]
			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)
			else:
				st_mode = 0o555 if type(entry) is Dir else 0o444
				return (st_mode & mode) == mode

		def opendir(self, inode):
			try:
				entry = self.inodes[inode]
			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)
			else:
				if type(entry) is not Dir:
					raise llfuse.FUSEError(errno.ENOTDIR)

				return inode

		def readdir(self, inode, offset):
			try:
				entry = self.inodes[inode]
			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)
			else:
				if type(entry) is not Dir:
					raise llfuse.FUSEError(errno.ENOTDIR)

				names = list(entry.children)[offset:] if offset > 0 else entry.children
				for name in names:
					child = entry.children[name]
					yield name, self._getattr(child), child.inode

		def releasedir(self, fh):
			pass

		def statfs(self):
			attrs = llfuse.StatvfsData()

			arch_st = self.arch_st
			attrs.f_bsize  = arch_st.st_blksize
			attrs.f_frsize = arch_st.st_blksize
			attrs.f_blocks = arch_st.st_blocks
			attrs.f_bfree  = 0
			attrs.f_bavail = 0

			attrs.f_files  = len(self.inodes)
			attrs.f_ffree  = 0
			attrs.f_favail = 0

			return attrs

		def open(self, inode, flags):
			try:
				entry = self.inodes[inode]
			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)
			else:
				if type(entry) is Dir:
					raise llfuse.FUSEError(errno.EISDIR)

				if flags & 3 != os.O_RDONLY:
					raise llfuse.FUSEError(errno.EACCES)

				return inode

		def read(self, fh, offset, length):
			try:
				entry = self.inodes[fh]
			except KeyError:
				raise llfuse.FUSEError(errno.ENOENT)

			if offset > entry.size:
				return bytes()

			i = entry.offset + offset
			j = i + min(entry.size - offset, length)
			return self.data[i:j]

#			self.archive.seek(entry.offset + offset, 0)
#			return self.archive.read(min(entry.size - offset, length))
			
		def release(self, fh):
			pass

	def mount(archive,mountpt,ext="",debug=False):
		with open(archive,"rb") as fp:
			ops = Operations(fp,ext)
			args = ['fsname=fezpak']
			if debug:
				args.append('debug')
			llfuse.init(ops, mountpt, args)
			try:
				llfuse.main(single=False)
			finally:
				llfuse.close()

def main(argv):
	import argparse

	# from https://gist.github.com/sampsyo/471779
	class AliasedSubParsersAction(argparse._SubParsersAction):

		class _AliasedPseudoAction(argparse.Action):
			def __init__(self, name, aliases, help):
				dest = name
				if aliases:
					dest += ' (%s)' % ','.join(aliases)
				sup = super(AliasedSubParsersAction._AliasedPseudoAction, self)
				sup.__init__(option_strings=[], dest=dest, help=help) 

		def add_parser(self, name, **kwargs):
			if 'aliases' in kwargs:
				aliases = kwargs['aliases']
				del kwargs['aliases']
			else:
				aliases = []

			parser = super(AliasedSubParsersAction, self).add_parser(name, **kwargs)

			# Make the aliases work.
			for alias in aliases:
				self._name_parser_map[alias] = parser
			# Make the help text reflect them, first removing old help entry.
			if 'help' in kwargs:
				help = kwargs.pop('help')
				self._choices_actions.pop()
				pseudo_action = self._AliasedPseudoAction(name, aliases, help)
				self._choices_actions.append(pseudo_action)

			return parser

	parser = argparse.ArgumentParser(description='pack, unpack and list FEZ .pak archives')
	parser.register('action', 'parsers', AliasedSubParsersAction)
	parser.set_defaults(print0=False,verbose=False)

	subparsers = parser.add_subparsers(metavar='command')

	pack_parser = subparsers.add_parser('pack',aliases=('c',),help="pack archive")
	pack_parser.set_defaults(command='pack')
	pack_parser.add_argument('-X','--remove-extension',dest='remove_ext',action='store_true',default=False,
		help='remove file name extensions')
	add_common_args(pack_parser)
	pack_parser.add_argument('files', metavar='file', nargs='*', help='files and directories to pack')

	unpack_parser = subparsers.add_parser('unpack',aliases=('x',),help='unpack archive')
	unpack_parser.set_defaults(command='unpack')
	unpack_parser.add_argument('-x','--extension',type=str,default='',metavar="EXT",
		help='add extension to names of unpacked files')
	unpack_parser.add_argument('-C','--dir',type=str,default='.',
		help='directory to write unpacked files')
	add_common_args(unpack_parser)
	unpack_parser.add_argument('files', metavar='file', nargs='*', help='files and directories to unpack')

	list_parser = subparsers.add_parser('list',aliases=('l',),help='list archive contens')
	list_parser.set_defaults(command='list')
	list_parser.add_argument('-u','--human-readable',dest='human',action='store_true',default=False,
		help='print human readable file sizes')
	list_parser.add_argument('-d','--details',action='store_true',default=False,
		help='print file offsets and sizes')
	list_parser.add_argument('-s','--sort',dest='sort_func',type=sort_func,default=None,
		help='sort file list')
	list_parser.add_argument('-x','--extension',type=str,default='',metavar="EXT",
		help='add extension to file names')
	add_common_args(list_parser)

	mount_parser = subparsers.add_parser('mount',aliases=('m',),help='fuse mount archive')
	mount_parser.set_defaults(command='mount')
	mount_parser.add_argument('-x','--extension',type=str,default='',metavar="EXT",
		help='add extension to names of files')
	mount_parser.add_argument('-d','--debug',action='store_true',default=False,
		help='print debug output')
	mount_parser.add_argument('archive', help='FEZ .pak archive')
	mount_parser.add_argument('mountpt', help='mount point')

	args = parser.parse_args(argv)

	delim = '\0' if args.print0 else '\n'

	if args.verbose:
		callback = lambda name: sys.stdout.write("%s%s" % (name, delim))
	else:
		callback = lambda name: None

	if args.command == 'list':
		with open(args.archive,"rb") as stream:
			print_list(stream,args.details,args.human,delim,args.extension,args.sort_func)
	
	elif args.command == 'unpack':
		with open(args.archive,"rb") as stream:
			if args.files:
				unpack_files(stream,set(name.strip(os.path.sep) for name in args.files),args.dir,args.extension,callback)
			else:
				unpack(stream,args.dir,args.extension,callback)
	
	elif args.command == 'pack':
		with open(args.archive,"wb") as stream:
			pack_files(stream,args.files or ['.'],args.remove_ext,callback)

	elif args.command == 'mount':
		if not HAS_LLFUSE:
			raise ValueError('the llfuse python module is needed for this feature')

		mount(args.archive,args.mountpt,args.extension,args.debug)

	else:
		raise ValueError('unknown command: %s' % args.command)

if __name__ == '__main__':
	try:
		main(sys.argv[1:])
	except Exception as exc:
		sys.stderr.write("%s\n" % exc)
