#!/bin/sh
# Runs Ghidra headless on the NeXT boot ROM and the NeXTSTEP 3.3 kernel, so
# their code can be read as decompiled C.
#
#     ghidra.sh import-rom
#     ghidra.sh import-kernel
#     ghidra.sh decompile rom|kernel <output file> <address>...
#
# The project sits in ~/Library/Caches, because Ghidra refuses a project path
# with an element that starts with a dot, such as ~/.cache. The ROM is mapped at
# 0x01000000, the address its code runs at. The kernel file holds __TEXT and
# __DATA back to back from file offset 0, mapped at 0x04000000, so a raw import
# of those bytes puts every address where the kernel expects it. Its __bss and
# __common follow as a zero-filled block, and macho68k.py supplies the names.
set -eu

playground="$HOME/.cache/previously-playground"
tools="$(cd "$(dirname "$0")" && pwd)"
project_dir="$HOME/Library/Caches/previously-playground-ghidra"
project=nextstep
rom="$playground/build/src/Previous.app/Contents/Resources/Rev_3.3_v74.BIN"
kernel="$playground/ns33-files/sdmach"

# From `macho68k.py info sdmach`: __TEXT and __DATA end at file offset
# 0xb3d64, and __bss plus __common run from 0x040b3d64 to 0x040ca9b0.
kernel_file_bytes=0xb3d64
kernel_zero_filled=0x040b3d64:0x16c4c

export JAVA_HOME=/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home
headless=/opt/homebrew/opt/ghidra/libexec/support/analyzeHeadless
log="$project_dir/headless.log"
mkdir -p "$project_dir"

case "${1:-}" in
    import-rom)
        "$headless" "$project_dir" "$project" -import "$rom" -overwrite \
            -loader BinaryLoader -loader-baseAddr 0x01000000 \
            -processor 68000:BE:32:default -cspec default \
            -scriptPath "$tools/ghidra" -preScript SeedFunctions.java seed=link > "$log" 2>&1
        grep -E 'seeded|named|ERROR|Import succeeded' "$log" || true
        ;;
    import-kernel)
        "$playground/venv/bin/python" "$tools/macho68k.py" symbols "$kernel" . > "$project_dir/sdmach.symbols"
        "$headless" "$project_dir" "$project" -import "$kernel" -overwrite \
            -loader BinaryLoader -loader-baseAddr 0x04000000 -loader-length "$kernel_file_bytes" \
            -processor 68000:BE:32:default -cspec default \
            -scriptPath "$tools/ghidra" -preScript SeedFunctions.java seed=link \
            "bss=$kernel_zero_filled" "symbols=$project_dir/sdmach.symbols" > "$log" 2>&1
        grep -E 'seeded|named|ERROR|Import succeeded' "$log" || true
        ;;
    decompile)
        case "$2" in
            rom) program="$(basename "$rom")" ;;
            kernel) program="$(basename "$kernel")" ;;
            *) echo "decompile rom|kernel <output file> <address>..." >&2; exit 2 ;;
        esac
        output="$3"
        shift 3
        "$headless" "$project_dir" "$project" -process "$program" -noanalysis -readOnly \
            -scriptPath "$tools/ghidra" -postScript Decompile.java "$output" "$@" > "$log" 2>&1
        grep -E 'ERROR' "$log" || true
        ;;
    *)
        echo "usage: ghidra.sh import-rom | import-kernel | decompile rom|kernel <output file> <address>..." >&2
        exit 2
        ;;
esac
