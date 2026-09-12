#!/usr/bin/env python3
"""Read a NeXT UFS (4.3BSD FFS, big endian) disk image well enough to list
directories and pull small files out of it.

Only what the icon hunt needs: direct and single-indirect blocks, which covers
anything up to a few megabytes."""

import struct, sys, os, mmap

SBOFF = 8192
UFS_MAGIC = 0x011954
ROOT_INO = 2


class UFS:
    def __init__(self, path, base=0):
        """@param base - Byte offset of the partition inside the image. A NeXT
        image starts with a dlV3 disk label, so the filesystem is not at 0."""
        self.file = open(path, "rb")
        whole = mmap.mmap(self.file.fileno(), 0, access=mmap.ACCESS_READ)
        self.base = base
        self.mm = _Slice(whole, base)
        sb = self.mm[SBOFF:SBOFF + 2048]
        magic, = struct.unpack_from(">I", sb, 1372)
        if magic != UFS_MAGIC:
            raise SystemExit("no UFS superblock at %d (magic %#x)" % (SBOFF, magic))
        (self.sblkno, self.cblkno, self.iblkno, self.dblkno,
         self.cgoffset, self.cgmask) = struct.unpack_from(">6i", sb, 8)
        self.ncg, self.bsize, self.fsize, self.frag = struct.unpack_from(">4i", sb, 44)
        self.inopb, = struct.unpack_from(">i", sb, 120)
        self.ipg, self.fpg = struct.unpack_from(">2i", sb, 184)
        self.nindir, = struct.unpack_from(">i", sb, 116)

    def cgstart(self, cg):
        """The first fragment of cylinder group cg."""
        return cg * self.fpg + (self.cgoffset * (cg & ~self.cgmask))

    def inode(self, ino):
        """@returns (mode, size, list of block numbers)."""
        cg, index = divmod(ino, self.ipg)
        base = (self.cgstart(cg) + self.iblkno) * self.fsize
        off = base + index * 128
        raw = self.mm[off:off + 128]
        mode, = struct.unpack_from(">H", raw, 0)
        size, = struct.unpack_from(">Q", raw, 8)
        direct = list(struct.unpack_from(">12i", raw, 40))
        indirect = list(struct.unpack_from(">3i", raw, 88))
        return mode, size, direct, indirect

    def read(self, ino):
        mode, size, direct, indirect = self.inode(ino)
        out = bytearray()
        for blk in direct:
            if blk == 0 or len(out) >= size:
                break
            out += self.mm[blk * self.fsize: blk * self.fsize + self.bsize]
        if len(out) < size and indirect[0]:
            table = self.mm[indirect[0] * self.fsize: indirect[0] * self.fsize + self.bsize]
            for blk, in struct.iter_unpack(">i", table):
                if blk == 0 or len(out) >= size:
                    break
                out += self.mm[blk * self.fsize: blk * self.fsize + self.bsize]
        return bytes(out[:size])

    def listdir(self, ino):
        """@returns list of (name, inode)."""
        data = self.read(ino)
        entries, pos = [], 0
        while pos + 8 <= len(data):
            child, reclen, namlen = struct.unpack_from(">IHH", data, pos)
            if reclen < 8 or pos + reclen > len(data):
                break
            if child:
                name = data[pos + 8: pos + 8 + namlen].decode("latin-1")
                entries.append((name, child))
            pos += reclen
        return entries

    def walk(self, ino=ROOT_INO, path="", depth=0, maxdepth=12):
        if depth > maxdepth:
            return
        for name, child in self.listdir(ino):
            if name in (".", ".."):
                continue
            full = path + "/" + name
            mode, size, _, _ = self.inode(child)
            kind = mode & 0o170000
            if kind == 0o040000:
                yield full + "/", child, 0
                yield from self.walk(child, full, depth + 1, maxdepth)
            elif kind == 0o100000:
                yield full, child, size

    def resolve(self, path):
        ino = ROOT_INO
        for part in path.strip("/").split("/"):
            if not part:
                continue
            found = dict(self.listdir(ino)).get(part)
            if found is None:
                return None
            ino = found
        return ino


class _Slice:
    """A view of the image that hides the partition offset."""

    def __init__(self, mm, base):
        self.mm, self.base = mm, base

    def __getitem__(self, key):
        if isinstance(key, slice):
            return self.mm[self.base + key.start: self.base + key.stop]
        return self.mm[self.base + key]


if __name__ == "__main__":
    fs = UFS(sys.argv[1], int(os.environ.get("UFS_BASE", "163840")))
    command = sys.argv[2]
    if command == "ls":
        for name, ino, size in fs.walk():
            print("%10d %8d %s" % (ino, size, name))
    elif command == "cat":
        ino = fs.resolve(sys.argv[3])
        if ino is None:
            raise SystemExit("not found: " + sys.argv[3])
        sys.stdout.buffer.write(fs.read(ino))
    elif command == "get":
        ino = int(sys.argv[3])
        sys.stdout.buffer.write(fs.read(ino))
