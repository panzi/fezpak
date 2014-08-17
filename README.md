fezpak
======

Because I am the way I am the first thing what I did after I bought [FEZ](http://fezgame.com/)
is not to play it, but to reverse engineer the package format so I can listen to the
music outside of the game.

Basic usage:

	fezpak.py list <archive>                 - list contens of .pak archive
	fezpak.py pack <archive> [files...]      - create a new .pak archive
	fezpak.py unpack <archive>               - extract .pak archive
	fezpak.py mount <archive> <mount-point>  - mount archive as read-only file system

The `mount` command depends on the [llfuse](https://code.google.com/p/python-llfuse/)
Python package. If it's not available the rest is still working.

This script is compatible with Python 2.7 and 3 (tested with 2.7.5 and 3.3.2).

File Format
-----------

The .pak file format is extremely simple. It has no file magic. The "header" is
just the number of entries it contains. A entry is just a file name (with `\`
as path seperator) and the contens of the file. All integers are encoded as
little endian.

File names don't have extensions (like `.ogg`). I don't know if this has a special
reason just happens to be the way the FEZ developers named the files.

**Note:** File names may conflict with directory names. If you unpack such an archive
you need to specify `-x EXT` or `--guess-extension` to add file name extension to all
extracted files in order resolve the name confilct.

Sometimes there is the exact same file name twice in the archive. In this case the
second occurance will overwrite the first when unpacking. When the archive is mounted
as a file system name conflict resolution is a bit different. In this case `~number`
is added between the file name and the extension. `number` is the first number that
doesn't produce a confict.

I noticed that all doubled file names in the archives of FEZ contain the exact same
content, so I guess their existance is a mistake.


	┌──────────────────────────────┐
	│                              │
	│ Header                       │
	│                              │
	│    number of entries         │
	│                              │
	│ ┌──────────────────────────┐ │
	│ │                          │ │
	│ │ Entry                    │ │
	│ │                          │ │
	│ │    file name size        │ │
	│ │    file name             │ │
	│ │    file size             │ │
	│ │    file data             │ │
	│ │                          │ │
	│ └──────────────────────────┘ │
	│                              │
	│ ...                          │
	│                              │
	└──────────────────────────────┘


### Archive

	Offset  Size  Type        Description
	     0     4  uint32_t    number of entries (N)
		 1   N/A  Entry[N]    entries

### Entry

	Offset  Size  Type        Description
	     0     1  uint8_t     file name size (N)
	     1     N  char[N]     file name, the path seperator is "\"
	   N+1     4  uint32_t    file size (S)
       N+5     S  uint8_t[S]  file data

Related Projects
----------------

 * [psypak](https://github.com/panzi/psypak): unpack, list and mount Psychonauts .pkg archives
 * [bgebf](https://github.com/panzi/bgebf): unpack, list and mount Beyond Good and Evil .bf archives
 * [unvpk](https://bitbucket.org/panzi/unvpk): extract, list, check and mount Valve .vpk archives
 * [u4pak](https://github.com/panzi/u4pak): unpack, list and mount Unreal Engine 4 .pak archives
 * [t2fbq](https://github.com/panzi/t2fbq): unpack, list and mount Trine 2 .fbq archives

BSD License
-----------
Copyright (c) 2014 Mathias Panzenböck

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
