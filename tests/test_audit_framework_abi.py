"""Host tests for tools/audit_framework_abi.py. No car, no real BMW binaries: builds a minimal synthetic
ELF32 .so in memory with a hand-built symbol table. Run: python -m unittest discover tests
"""
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import audit_framework_abi as audit  # noqa: E402


def build_minimal_elf32(symbol_names):
    """A tiny ELF32 LE file: ELF header + one SHT_SYMTAB section (linked to one SHT_STRTAB) + a null section.
    Not a loadable/runnable library -- only enough structure for parse_elf32_symbols to read."""
    strtab = b"\x00"
    sym_offsets = []
    for name in symbol_names:
        sym_offsets.append(len(strtab))
        strtab += name.encode() + b"\x00"

    # Elf32_Sym: st_name(I), st_value(I), st_size(I), st_info(B), st_other(B), st_shndx(H) = 16 bytes
    symtab = struct.pack("<IIIBBH", 0, 0, 0, 0, 0, 0)  # index 0 is always null/reserved
    for off in sym_offsets:
        symtab += struct.pack("<IIIBBH", off, 0, 0, 0, 0, 0)

    ehsize = 52
    shentsize = 40
    # Section layout after the ELF header: [0]=null, [1]=symtab, [2]=strtab
    sh_null = struct.pack("<10I", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
    symtab_off = ehsize + 3 * shentsize
    strtab_off = symtab_off + len(symtab)
    sh_symtab = struct.pack("<10I", 0, audit.SHT_SYMTAB, 0, 0, symtab_off, len(symtab), 2, 0, 0, 16)
    sh_strtab = struct.pack("<10I", 0, 3, 0, 0, strtab_off, len(strtab), 0, 0, 0, 0)  # type 3 = SHT_STRTAB
    shoff = ehsize

    e_ident = b"\x7fELF" + bytes([1, 1, 1, 0]) + b"\x00" * 8
    header = e_ident + struct.pack(
        "<HHIIIIIHHHHHH",
        2, 3, 1, 0, 0, shoff, 0, ehsize, 0, 0, shentsize, 3, 2,
    )
    assert len(header) == ehsize, len(header)
    body = header + sh_null + sh_symtab + sh_strtab + symtab + strtab
    return body


class Audit(unittest.TestCase):
    def test_parses_known_and_unknown_symbols(self):
        names = ["_ZN9PluginAppC1E", "triggerEvent", "unrelatedThing", "addHandler"]
        data = build_minimal_elf32(names)
        got = audit.parse_elf32_symbols(data)
        self.assertEqual(got, sorted(names))

    def test_audit_file_reports_matches_and_misses(self):
        names = ["PluginApp", "triggerEvent"]  # only some of KNOWN_SYMBOLS present
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "libFake.so"
            p.write_bytes(build_minimal_elf32(names))
            result = audit.audit_file(p)
        self.assertIsNone(result["error"])
        self.assertTrue(result["matches"]["PluginApp"])
        self.assertTrue(result["matches"]["triggerEvent"])
        self.assertFalse(result["matches"]["addHandler"])
        self.assertEqual(result["symbol_count"], 2)
        self.assertEqual(len(result["sha256"]), 64)
        report = audit.format_report(result)
        self.assertIn("MISSING", report)
        self.assertIn("found", report)

    def test_non_elf_file_reports_error_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "not_a_lib.so"
            p.write_bytes(b"not an elf file at all")
            result = audit.audit_file(p)
        self.assertIn("not an ELF file", result["error"])
        self.assertEqual(result["symbol_count"], 0)
        self.assertIn("Could not list symbols", audit.format_report(result))

    def test_wrong_elf_class_reports_error(self):
        data = bytearray(build_minimal_elf32(["x"]))
        data[4] = 2  # claim 64-bit
        with self.assertRaises(audit.ElfFormatError):
            audit.parse_elf32_symbols(bytes(data))

    def test_all_known_symbols_present(self):
        data = build_minimal_elf32(audit.KNOWN_SYMBOLS)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "libFull.so"
            p.write_bytes(data)
            result = audit.audit_file(p)
        self.assertTrue(all(result["matches"].values()))
        self.assertNotIn("MISSING", audit.format_report(result))


if __name__ == "__main__":
    unittest.main()
