#!/usr/bin/env python3
"""OpenNBT generic UDS write scaffolding (MIT). Original code. INERT by default.

Deliberately kept out of hsfz_probe.py, whose exchange() refuses anything but OBD 01xx/UDS 22xxxx before a
socket is even opened -- that guarantee is tested (test_exchange_refuses_write_service) and documented in the
README's safety model. This module is the opposite: it CAN send UDS WriteDataByIdentifier (0x2E) and
SecurityAccess (0x27), so every one of its gates is load-bearing, not advisory:

  - VIN gate: reads the target's VIN (22F190) and refuses unless it matches --confirm-vin. Never printed.
  - Backup-before-write: always reads and saves the current value of the target DID before touching it.
  - Dry-run by default: without --commit, nothing is sent except the VIN check and the backup read (both 22xxxx
    reads). --commit alone is not enough; --i-understand-this-writes-to-the-ecu must also be given.
  - No seed-key algorithm for any BMW ECU is shipped or known. security_access() raises unless the caller
    supplies one; the CLI does not attempt SecurityAccess at all, so a protected DID will just come back with
    NRC 0x33 (security access denied) -- a normal, handled outcome, not a bug.
  - VIN and ECU-serial DIDs can never be write targets (refused unconditionally).

This is scaffolding for issue #9, not wired to any specific BMW coding payload. Writing anything to a real
ECU is the owner's own explicit decision.
"""
import argparse
import json
import socket
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hsfz_probe as hp  # noqa: E402

WRITE_SID = 0x2E
SECURITY_SID = 0x27


def _did_hex(did):
    did = did.replace(" ", "").upper()
    if len(did) != 4 or not all(c in "0123456789ABCDEF" for c in did):
        raise argparse.ArgumentTypeError("DID must be 2 bytes hex, e.g. 2A10 (got %r)" % did)
    return did


def _refuse_sensitive_did(did_hex_str):
    key = "22" + did_hex_str.lower()
    if key in hp.VIN_DIDS or key in hp.SERIAL_DIDS:
        raise ValueError("refusing: %s is a VIN/serial identifier, never a write target" % did_hex_str)


def send_and_wait(sock, ecu, uds, reply_timeout=hp.REPLY_TIMEOUT_S, pending_total=hp.PENDING_TOTAL_S):
    """Like hp.exchange but without the read-only guard: this module is the one place allowed to write.
    Positive-response echo length differs by service: WriteDataByIdentifier echoes the 2-byte DID only (never
    the data just written); SecurityAccess echoes the 1-byte sub-function level only (never the seed/key)."""
    sid = uds[0]
    if sid == WRITE_SID:
        echo = uds[1:3]
    elif sid == SECURITY_SID:
        echo = uds[1:2]
    else:
        echo = uds[1:]
    prefix = bytes((sid + 0x40,)) + echo
    sock.sendall(hp.build_frame(ecu, uds))
    deadline = time.monotonic() + reply_timeout
    hard_stop = time.monotonic() + pending_total
    while True:
        length, control = struct.unpack(">IH", hp._recv_exact(sock, 6, deadline))
        if length > 8192:
            raise ValueError("oversized frame")
        payload = hp._recv_exact(sock, length, deadline)
        if control == hp.CTRL_ALIVE_REQ:
            sock.sendall(struct.pack(">IHBB", 2, hp.CTRL_ALIVE_RESP, 0, hp.TESTER))
            continue
        if control != hp.CTRL_DATA or len(payload) < 3 or payload[0] != ecu or payload[1] != hp.TESTER:
            continue
        reply = payload[2:]
        if reply.startswith(prefix):
            return {"reply": reply.hex(" "), "data": reply[len(prefix):].hex(" ")}
        if len(reply) == 3 and reply[0] == 0x7F and reply[1] == sid:
            if reply[2] == 0x78:  # response pending: wait, bounded
                deadline = min(time.monotonic() + reply_timeout, hard_stop)
                if time.monotonic() >= hard_stop:
                    raise TimeoutError("response pending too long")
                continue
            return {"reply": reply.hex(" "), "nrc": "%02X" % reply[2]}


def read_vin(sock, ecu):
    """Returns the raw VIN string. Caller must never print or store this -- compare it and discard."""
    res = hp.exchange(sock, ecu, bytes.fromhex("22F190"))
    data = res.get("data")
    if not data:
        raise ValueError("VIN read failed: %s" % res)
    return bytes.fromhex(data.replace(" ", "")).decode("ascii", "replace")


def backup_did(sock, ecu, did_hex_str, backup_dir):
    """Reads the current value of did_hex_str and saves it. Returns (path, hex_value)."""
    res = hp.exchange(sock, ecu, bytes.fromhex("22" + did_hex_str))
    if "nrc" in res:
        raise ValueError("backup read refused (NRC %s): cannot safely write without a backup" % res["nrc"])
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    row = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "ecu": "%02X" % ecu, "did": did_hex_str,
        "value_hex": res["data"],
    }
    path = backup_dir / ("backup-%02X-%s-%s.json" % (ecu, did_hex_str, time.strftime("%Y%m%d-%H%M%S")))
    path.write_text(json.dumps(row, indent=2))
    return path, res["data"]


def security_access(sock, ecu, level, seed_key_fn):
    """Generic ISO 14229 SecurityAccess. level must be an odd (request-seed) sub-function. seed_key_fn(seed_bytes)
    -> key_bytes is required: no BMW seed-key algorithm is known or shipped here."""
    if seed_key_fn is None:
        raise ValueError("no seed-key algorithm supplied; refusing SecurityAccess (none is known for this ECU)")
    if level % 2 == 0:
        raise ValueError("security_access level must be an odd request-seed sub-function")
    res = send_and_wait(sock, ecu, bytes([SECURITY_SID, level]))
    if "nrc" in res:
        return False, res["nrc"]
    seed = bytes.fromhex(res["data"].replace(" ", ""))
    if seed == bytes(len(seed)):  # all-zero seed conventionally means "already unlocked"
        return True, None
    key = seed_key_fn(seed)
    res2 = send_and_wait(sock, ecu, bytes([SECURITY_SID, level + 1]) + key)
    if "nrc" in res2:
        return False, res2["nrc"]
    return True, None


def write_did(sock, ecu, did_hex_str, data_hex, backup_dir, commit=False):
    """Always backs up first. Without commit=True, sends nothing else and returns the dry-run plan."""
    _refuse_sensitive_did(did_hex_str)
    data_hex = data_hex.replace(" ", "")
    backup_path, old_hex = backup_did(sock, ecu, did_hex_str, backup_dir)
    plan = {
        "ecu": "%02X" % ecu, "did": did_hex_str, "old_value_hex": old_hex, "new_value_hex": data_hex,
        "backup": str(backup_path), "dry_run": not commit,
    }
    if commit:
        uds = bytes.fromhex(("%02X" % WRITE_SID) + did_hex_str) + bytes.fromhex(data_hex)
        plan["result"] = send_and_wait(sock, ecu, uds)
    return plan


def cmd_write(args):
    if not args.yes_parked:
        sys.exit("refusing: add --yes-parked to confirm parked, handbrake on, ignition on")
    if args.commit and not args.i_understand_this_writes_to_the_ecu:
        sys.exit("refusing: --commit also needs --i-understand-this-writes-to-the-ecu")
    with socket.create_connection((args.gateway, hp.HSFZ_PORT), timeout=2,
                                  source_address=(args.local, 0) if args.local else None) as s:
        vin = read_vin(s, args.ecu)
        vin_ok = vin.strip().upper() == args.confirm_vin.strip().upper()
        del vin  # never kept, never printed
        if not vin_ok:
            sys.exit("refusing: --confirm-vin does not match this car's VIN")
        print("VIN check: OK", file=sys.stderr)
        plan = write_did(s, args.ecu, args.did, args.data, args.backup_dir, commit=args.commit)
    print(json.dumps(plan, indent=2))
    if plan["dry_run"]:
        print("DRY RUN: nothing was sent to the ECU beyond the VIN check and the backup read. "
              "Add --commit (and --i-understand-this-writes-to-the-ecu) to actually send it.", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="backup-then-write one DID on one ECU; dry-run unless --commit")
    w.add_argument("--gateway", required=True, type=hp.link_local)
    w.add_argument("--local", type=hp.link_local)
    w.add_argument("--ecu", required=True, type=lambda x: int(x, 16), help="hex ECU address")
    w.add_argument("--did", required=True, type=_did_hex, help="2-byte hex DID, e.g. 2A10")
    w.add_argument("--data", required=True, type=lambda x: x.replace(" ", ""), help="hex bytes to write")
    w.add_argument("--confirm-vin", required=True, help="must match the target's actual VIN")
    w.add_argument("--backup-dir", default=str(Path(__file__).resolve().parent.parent / ".local" / "backups"))
    w.add_argument("--commit", action="store_true", help="actually send the write (default: dry run)")
    w.add_argument("--i-understand-this-writes-to-the-ecu", action="store_true")
    w.add_argument("--yes-parked", action="store_true")
    w.set_defaults(fn=cmd_write)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
