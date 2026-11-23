#!/usr/bin/env python3
"""OpenNBT offline framework ABI audit. Original code, stdlib only, no network.

Reads two local .so files (copied off the head unit per docs/SSH_RECON_COMMANDS.md) and checks their exported
symbol names against the F07 precedent documented in docs/FEASIBILITY.md / ref/nbt-android-auto's
docs/history/IDRIVE-HELLO.md: PluginApp, IDispatcher, BasicString, Bundle, post, triggerEvent, updateModel,
TextID, addHandler, ActionDelegate.

This is a name/hash check, not a full ABI/vtable comparison: a name match does not prove layout compatibility,
and C++ name mangling means these are checked as substrings, not exact symbols. Treat a mismatch as a stronger
signal than a match.

Parses ELF32 (32-bit) symbol tables directly (SHT_SYMTAB preferred, falls back to SHT_DYNSYM) using only the
struct/stdlib. Does not execute or load the library.
"""
import argparse
import hashlib
import struct
import sys
from pathlib import Path

ELF_MAGIC = b"\x7fELF"
SHT_SYMTAB, SHT_DYNSYM = 2, 11

KNOWN_SYMBOLS = [
    "PluginApp", "IDispatcher", "BasicString", "Bundle", "post", "triggerEvent",
    "updateModel", "TextID", "addHandler", "ActionDelegate",
]


class ElfFormatError(ValueError):
    pass


def parse_elf32_symbols(data):
    """Returns a sorted list of unique symbol names from an ELF32 little-endian file's symbol table(s)."""
    if len(data) < 52 or data[:4] != ELF_MAGIC:
        raise ElfFormatError("not an ELF file")
    ei_class, ei_data = data[4], data[5]
    if ei_class != 1:
        raise ElfFormatError("not 32-bit ELF (ei_class=%d); this project's targets are ELF32/i386" % ei_class)
    if ei_data != 1:
        raise ElfFormatError("not little-endian ELF (ei_data=%d)" % ei_data)
    # ELF32 header layout (little-endian): e_shoff @ 0x20 (I), e_shentsize @ 0x2E (H), e_shnum @ 0x30 (H)
    e_shoff, = struct.unpack_from("<I", data, 0x20)
    e_shentsize, = struct.unpack_from("<H", data, 0x2E)
    e_shnum, = struct.unpack_from("<H", data, 0x30)
    if e_shoff == 0 or e_shnum == 0:
        raise ElfFormatError("no section headers (stripped?); cannot list symbols")

    def section_header(i):
        off = e_shoff + i * e_shentsize
        name, s_type, flags, addr, offset, size, link, info, align, entsize = struct.unpack_from("<10I", data, off)
        return dict(name=name, type=s_type, offset=offset, size=size, link=link, entsize=entsize)

    names = set()
    for i in range(e_shnum):
        sh = section_header(i)
        if sh["type"] not in (SHT_SYMTAB, SHT_DYNSYM) or sh["entsize"] == 0:
            continue
        strtab = section_header(sh["link"])
        str_off, str_size = strtab["offset"], strtab["size"]
        count = sh["size"] // sh["entsize"]
        for j in range(count):
            sym_off = sh["offset"] + j * sh["entsize"]
            st_name, = struct.unpack_from("<I", data, sym_off)
            if st_name == 0:
                continue
            end = data.index(b"\x00", str_off + st_name, str_off + str_size)
            nm = data[str_off + st_name:end].decode("utf-8", "replace")
            if nm:
                names.add(nm)
    return sorted(names)


def audit_file(path):
    data = Path(path).read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    try:
        symbols = parse_elf32_symbols(data)
        error = None
    except ElfFormatError as e:
        symbols, error = [], str(e)
    matches = {k: any(k in s for s in symbols) for k in KNOWN_SYMBOLS}
    return {
        "path": str(path), "size": len(data), "sha256": sha256, "symbol_count": len(symbols),
        "error": error, "matches": matches,
    }


def format_report(result):
    lines = ["%s (%d bytes, sha256 %s)" % (result["path"], result["size"], result["sha256"])]
    if result["error"]:
        lines.append("  Could not list symbols: %s" % result["error"])
        return "\n".join(lines)
    lines.append("  %d exported symbol names" % result["symbol_count"])
    hit = sum(result["matches"].values())
    lines.append("  F07-precedent name check: %d/%d found" % (hit, len(KNOWN_SYMBOLS)))
    for k, v in result["matches"].items():
        lines.append("    %-14s %s" % (k, "found" if v else "MISSING"))
    if hit < len(KNOWN_SYMBOLS):
        lines.append("  Missing names are a real signal: the framework may not match the F07 precedent"
                      " (see FEASIBILITY.md section 2). A name match alone does not confirm the ABI layout.")
    return "\n".join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("files", nargs="+", help="local .so file(s) copied off the head unit")
    args = p.parse_args(argv)
    for f in args.files:
        print(format_report(audit_file(f)))


if __name__ == "__main__":
    main()
