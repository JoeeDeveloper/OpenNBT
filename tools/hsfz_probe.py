#!/usr/bin/env python3
"""OpenNBT read-only HSFZ probe (MIT). Original code.

Sends ONLY OBD service 01 (e.g. 010C) and UDS service 22 (e.g. 22F190). Anything else is refused before a socket
is opened. Parked, ignition on, handbrake on. Nothing is sent unless --yes-parked is given.

  discover  UDP broadcast to find the gateway address (frame layout is UNVERIFIED, see DISCOVERY_REQUEST)
  read      one fresh TCP connection per request, spaced, bounded, captures to .local/captures/ (gitignored)

VIN (DID F190) and discovery payloads are never printed or stored; they are replaced by a marker.
"""
import argparse
import json
import re
import socket
import struct
import sys
import time
from ipaddress import IPv4Address
from pathlib import Path

HSFZ_PORT = 6801
DISCOVERY_PORT = 6811
# UNVERIFIED: header-only frame (len 0, control 0x0011). Not confirmed in any reference; check against your gateway.
DISCOVERY_REQUEST = struct.pack(">IH", 0, 0x0011)
CTRL_DATA, CTRL_ALIVE_REQ, CTRL_ALIVE_RESP = 0x0001, 0x0012, 0x0013
TESTER = 0xF4
MAX_REQUESTS = 12
SPACING_S = 0.2
REPLY_TIMEOUT_S = 2.0
PENDING_TOTAL_S = 5.0
READ_RE = re.compile(r"^(01[0-9A-Fa-f]{2}|22[0-9A-Fa-f]{4})$")
VIN_DIDS = {"22f190"}


def parse_request(text):
    text = text.replace(" ", "")
    if not READ_RE.match(text):
        raise argparse.ArgumentTypeError("read-only only: OBD 01xx or UDS 22xxxx (got %r)" % text)
    return bytes.fromhex(text)


def link_local(text):
    a = IPv4Address(text)
    if not a.is_link_local:
        raise argparse.ArgumentTypeError("expected a 169.254.x.x address")
    return str(a)


def build_frame(ecu, uds, control=CTRL_DATA):
    return struct.pack(">IHBB", len(uds) + 2, control, TESTER, ecu) + uds


def _recv_exact(sock, n, deadline):
    buf = bytearray()
    while len(buf) < n:
        left = deadline - time.monotonic()
        if left <= 0:
            raise TimeoutError("no reply")
        sock.settimeout(left)
        part = sock.recv(n - len(buf))
        if not part:
            raise ConnectionError("gateway closed connection")
        buf.extend(part)
    return bytes(buf)


def exchange(sock, ecu, uds, reply_timeout=REPLY_TIMEOUT_S, pending_total=PENDING_TOTAL_S):
    """Returns dict: reply/data (positive) or nrc (negative). Raises TimeoutError."""
    if not READ_RE.match(uds.hex()):
        raise ValueError("refusing non read-only request")
    sock.sendall(build_frame(ecu, uds))
    prefix = bytes((uds[0] + 0x40,)) + uds[1:]
    deadline = time.monotonic() + reply_timeout
    hard_stop = time.monotonic() + pending_total
    while True:
        length, control = struct.unpack(">IH", _recv_exact(sock, 6, deadline))
        if length > 8192:
            raise ValueError("oversized frame")
        payload = _recv_exact(sock, length, deadline)
        if control == CTRL_ALIVE_REQ:
            sock.sendall(struct.pack(">IHBB", 2, CTRL_ALIVE_RESP, 0, TESTER))
            continue
        if control != CTRL_DATA or len(payload) < 3 or payload[0] != ecu or payload[1] != TESTER:
            continue
        reply = payload[2:]
        if reply.startswith(prefix):
            return {"reply": reply.hex(" "), "data": reply[len(prefix):].hex(" ")}
        if len(reply) == 3 and reply[0] == 0x7F and reply[1] == uds[0]:
            if reply[2] == 0x78:  # response pending: wait, bounded
                deadline = min(time.monotonic() + reply_timeout, hard_stop)
                if time.monotonic() >= hard_stop:
                    raise TimeoutError("response pending too long")
                continue
            return {"reply": reply.hex(" "), "nrc": "%02X" % reply[2]}


def redact(request_hex, result):
    if request_hex.replace(" ", "").lower() in VIN_DIDS:
        for k in ("reply", "data"):
            if k in result:
                result[k] = "<redacted VIN>"
    return result


def cmd_read(args):
    if not args.yes_parked:
        sys.exit("refusing: add --yes-parked to confirm parked, handbrake on, ignition on, read-only")
    if len(args.requests) > MAX_REQUESTS:
        sys.exit("at most %d requests per run" % MAX_REQUESTS)
    out_dir = Path(args.capture_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / ("capture-%s.jsonl" % time.strftime("%Y%m%d-%H%M%S"))
    with out.open("a", encoding="utf-8") as fh:
        for req in args.requests:
            row = {"t": time.strftime("%H:%M:%S"), "ecu": "%02X" % args.ecu, "request": req.hex(" ")}
            try:
                # fresh connection per request: a late reply can never match a later request
                with socket.create_connection((args.gateway, HSFZ_PORT), timeout=2,
                                              source_address=(args.local, 0) if args.local else None) as s:
                    row.update(redact(req.hex(), exchange(s, args.ecu, req)))
            except (TimeoutError, OSError, ValueError) as e:
                row["error"] = "%s: %s" % (type(e).__name__, e)
            line = json.dumps(row)
            print(line, flush=True)
            fh.write(line + "\n")
            time.sleep(SPACING_S)
    print("saved", out, file=sys.stderr)


def cmd_discover(args):
    if not args.yes_parked:
        sys.exit("refusing: add --yes-parked. This sends one UDP broadcast frame (format unverified).")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    if args.local:
        s.bind((args.local, 0))
    s.settimeout(3)
    s.sendto(DISCOVERY_REQUEST, ("169.254.255.255", DISCOVERY_PORT))
    found = set()
    end = time.monotonic() + 3
    while time.monotonic() < end:
        try:
            data, addr = s.recvfrom(4096)
        except socket.timeout:
            break
        if addr[0] not in found:
            found.add(addr[0])
            # payload may contain the VIN and MAC: never printed or stored
            print(json.dumps({"gateway_candidate": addr[0], "reply_bytes": len(data)}))
    if not found:
        print("no reply (frame format is unverified; this does not prove there is no gateway)")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover")
    d.add_argument("--local", type=link_local, help="laptop ENET address")
    d.add_argument("--yes-parked", action="store_true")
    d.set_defaults(fn=cmd_discover)
    r = sub.add_parser("read")
    r.add_argument("--gateway", required=True, type=link_local)
    r.add_argument("--local", type=link_local)
    r.add_argument("--ecu", default="12", type=lambda x: int(x, 16), help="hex ECU address, default 12 (DME)")
    r.add_argument("--capture-dir", default=str(Path(__file__).resolve().parent.parent / ".local" / "captures"))
    r.add_argument("--yes-parked", action="store_true")
    r.add_argument("requests", nargs="+", type=parse_request)
    r.set_defaults(fn=cmd_read)
    args = p.parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
