#!/usr/bin/env python3
"""OpenNBT capture analyzer. Reads .local/captures/*.jsonl and prints a plain summary. Read-only, offline.

Does NOT decode SVK/I-level binary (format unverified). It shows raw bytes, printable text, and any
I-level-looking string (e.g. F020-14-03-503) found in the text.
"""
import json
import re
import sys
from collections import OrderedDict
from pathlib import Path

ECU_NAMES = {"10": "gateway (ZGW)", "63": "head unit (guess)", "60": "cluster (guess)", "12": "DME/DDE"}
NRC = {"10": "general reject", "11": "service not supported", "12": "sub-function not supported",
       "22": "conditions not correct", "31": "request out of range (DID not supported)",
       "33": "security access denied", "78": "response pending"}
# INFERRED from captured layout, not from a reference: only the classes below are named; others print as hex.
PROCESS_CLASS = {0x01: "HWEL", 0x02: "HWAP", 0x05: "CAFD", 0x06: "BTLD", 0x07: "FLSL", 0x08: "SWFL"}
ILEVEL_RE = re.compile(r"[A-Z]{1,4}\d{2,3}-\d{2}-\d{2}-\d{3}")


def load_rows(path):
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def decode_svk(data_hex):
    """Decode a 22 F101 reply body (after the 62 F1 01 prefix). INFERRED layout, verified only by consistency:
    bytes 2-3 = record count, records = the last count*8 bytes, each = class(1) + module id(4) + version(3).
    Returns None if it does not fit that layout."""
    try:
        raw = bytes.fromhex(data_hex.replace(" ", ""))
    except ValueError:
        return None
    if len(raw) < 4:
        return None
    count = int.from_bytes(raw[2:4], "big")
    if count == 0 or len(raw) < 4 + count * 8:
        return None
    body = raw[len(raw) - count * 8:]
    recs = []
    for i in range(count):
        r = body[i * 8:(i + 1) * 8]
        ver = None if r[5:8] == b"\xff\xff\xff" else "%d.%d.%d" % tuple(r[5:8])
        recs.append({"class": PROCESS_CLASS.get(r[0], "0x%02X" % r[0]), "id": "0x%04X" % int.from_bytes(r[1:5], "big"),
                     "version": ver})
    return {"count": count, "header": raw[:len(raw) - count * 8].hex(" "), "records": recs}


def classify(row):
    if "error" in row:
        return "no answer (%s)" % row["error"].split(":")[0]
    if "nrc" in row:
        return ("refused: NRC %s %s" % (row["nrc"], NRC.get(row["nrc"], ""))).rstrip()
    return "OK"


def summarize(rows):
    by_ecu = OrderedDict()
    for r in rows:
        by_ecu.setdefault(r["ecu"], []).append(r)
    out = []
    for ecu, rs in by_ecu.items():
        ok = sum(1 for r in rs if "reply" in r and "nrc" not in r)
        out.append("ECU %s - %s: %d/%d answered" % (ecu, ECU_NAMES.get(ecu, "unknown"), ok, len(rs)))
        for r in rs:
            line = "  %-10s %s" % (r["request"], classify(r))
            if "data" in r:
                line += "  data=%s" % r["data"]
            if "ascii" in r:
                line += "  text=%r" % r["ascii"]
            if r["request"] == "22 f1 01" and "data" in r:
                svk = decode_svk(r["data"])
                if svk:
                    out.append(line)
                    line = "    SVK-like list, %d entries (layout inferred):" % svk["count"]
                    for rec in svk["records"]:
                        line += "\n      %-5s %s  %s" % (rec["class"], rec["id"], rec["version"] or "-")
            hit = ILEVEL_RE.search(r.get("ascii", ""))
            if hit:
                line += "  I-LEVEL?=%s" % hit.group(0)
            out.append(line)
    if not rows:
        out.append("empty capture")
    elif not any("reply" in r and "nrc" not in r for r in rows):
        out.append("\nNothing answered positively: check the gateway address, cable, ignition state and ECU addresses.")
    return "\n".join(out)


def latest_capture(directory):
    files = sorted(Path(directory).glob("capture-*.jsonl"))
    return files[-1] if files else None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    path = argv[0] if argv else latest_capture(Path(__file__).resolve().parent.parent / ".local" / "captures")
    if not path:
        sys.exit("no capture found; pass a path to a .jsonl file")
    print(summarize(load_rows(path)))


if __name__ == "__main__":
    main()
