#!/usr/bin/env python3
"""Writes byte patches into a copy of a NeXT disk image, at the place a file's bytes sit.

ditool reads a NeXT UFS image but writes nothing back, and the experiment
needs a patched kernel inside the image. A file's bytes lie in the image
unchanged, only cut into blocks, so a patch site is found by searching the
image for the bytes that surround it in the extracted file. The search has to
hit exactly once, and the surrounding bytes have to lie in one block, which is
why the context is shortened until it is found rather than asserted to be in
one block.

    imagepatch.py <image> <extracted-file> <file-offset>=<hex-bytes> ...

The image is modified in place, so the caller passes a copy. Every patch is
read back afterwards and compared, and the script fails loudly where a site
is missing, ambiguous, or already different from the extracted file.
"""

import argparse
import sys

CONTEXT_BYTES_FIRST = 48
CONTEXT_BYTES_LEAST = 8
UFS_BLOCK_BYTES = 8192


def find_once(haystack, needle):
    """@returns int or None - The one offset of the needle, None when it occurs zero or several times."""
    first = haystack.find(needle)
    if first == -1:
        return None
    if haystack.find(needle, first + 1) != -1:
        return None
    return first


def locate(image, original, file_offset, length):
    """Finds where the bytes at file_offset of the original lie in the image.

    @param image - The whole image as bytes.
    @param original - The extracted file as bytes.
    @param file_offset - Where the patch starts in the extracted file.
    @param length - How many bytes the patch replaces.
    @returns int - The image offset of the patch site.
    """
    context = CONTEXT_BYTES_FIRST
    while context >= CONTEXT_BYTES_LEAST:
        start = max(0, file_offset - context)
        end = min(len(original), file_offset + length + context)
        needle = original[start:end]
        hit = find_once(image, needle)
        if hit is not None:
            return hit + (file_offset - start)
        context //= 2
    raise SystemExit("patch at file offset 0x%x: no unique place in the image, even with %d bytes of context"
                     % (file_offset, CONTEXT_BYTES_LEAST))


def parse_patch(text):
    """@returns (int, bytes) - A patch given as <file-offset>=<hex-bytes>."""
    offset_text, _equals, hex_text = text.partition("=")
    if not hex_text:
        raise SystemExit("a patch reads <file-offset>=<hex-bytes>, not %r" % text)
    return int(offset_text, 0), bytes.fromhex(hex_text)


def main():
    """Applies every patch to the image and reads each one back."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("image")
    parser.add_argument("original")
    parser.add_argument("patches", nargs="+", type=parse_patch)
    arguments = parser.parse_args()

    with open(arguments.original, "rb") as handle:
        original = handle.read()
    with open(arguments.image, "rb") as handle:
        image = handle.read()
    sites = []
    for file_offset, new_bytes in arguments.patches:
        image_offset = locate(image, original, file_offset, len(new_bytes))
        old_bytes = image[image_offset:image_offset + len(new_bytes)]
        expected = original[file_offset:file_offset + len(new_bytes)]
        if old_bytes != expected:
            raise SystemExit("image offset 0x%x holds %s where the extracted file has %s"
                             % (image_offset, old_bytes.hex(), expected.hex()))
        if image_offset // UFS_BLOCK_BYTES != (image_offset + len(new_bytes) - 1) // UFS_BLOCK_BYTES:
            raise SystemExit("patch at image offset 0x%x crosses a block boundary" % image_offset)
        sites.append((file_offset, image_offset, old_bytes, new_bytes))

    with open(arguments.image, "r+b") as handle:
        for file_offset, image_offset, old_bytes, new_bytes in sites:
            handle.seek(image_offset)
            handle.write(new_bytes)
            print("file 0x%06x -> image 0x%09x: %s -> %s" % (file_offset, image_offset, old_bytes.hex(), new_bytes.hex()))

    with open(arguments.image, "rb") as handle:
        for _file_offset, image_offset, _old_bytes, new_bytes in sites:
            handle.seek(image_offset)
            if handle.read(len(new_bytes)) != new_bytes:
                raise SystemExit("image offset 0x%x did not take the patch" % image_offset)
    print("%d patches written and read back" % len(sites))
    return 0


if __name__ == "__main__":
    sys.exit(main())
