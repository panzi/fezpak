fezpak
======

Because I am the way I am the first thing what I did after I bought FEZ is not
to play it, but to reverse engineer the package format so I can listen to the
music outside of the game.

Basic usage:

	fezpak.py list <archive>           - list contens of .pak archive
	fezpak.py pack <archive> files...  - create a new .pak archive
	fezpak.py unpack <archive>         - extract .pak archive

File Format
-----------

The .pak file format is extremely simple. It has no file magic. The "header" is
just the number of entries it contains. A entry is just a file name (with `\\`
as path seperator) and the contens of the file. All integers are encoded as
little endian.

File names don't have extensions (like `.ogg`). I don't know if this has a special
reason just happens to be the way the FEZ developers named the files.

**Note:** File names may conflict with directory names. If you unpack such an archive
you need to specify `-x EXT` to add an extension to all extracted files and resolve
the name confilct.


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


### Header

	Offset  Size  Type        Description
	     0     4  uint32_t    number of entries (N)
		 1   N/A  Entry[N]    entries

### Entry

	Offset  Size  Type        Description
	     0     1  uint8_t     file name size (N)
	     1     N  char[N]     file name, the path seperator is "\"
	   N+1     4  uint32_t    file size (S)
       N+5     S  uint8_t[S]  file data
