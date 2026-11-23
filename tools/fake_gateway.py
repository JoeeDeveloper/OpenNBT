#!/usr/bin/env python3
"""OpenNBT fake HSFZ gateway for demo/testing on loopback. Not a model of any real car: replies are invented."""
import socket
import struct
import threading

DEMO_ECUS = {0x10: "ZGW-DEMO", 0x63: "HU-DEMO", 0x12: "DME-DEMO"}  # 0x60 is deliberately absent -> NRC 31


def _serve(conn):
    with conn:
        try:
            while True:
                hdr = conn.recv(6)
                if len(hdr) < 6:
                    return
                length, ctrl = struct.unpack(">IH", hdr)
                body = conn.recv(length)
                if ctrl != 1 or len(body) < 4:
                    continue
                src, dst, uds = body[0], body[1], body[2:]
                if dst not in DEMO_ECUS:
                    resp = bytes((0x7F, uds[0], 0x31))
                else:
                    text = ("%s %s" % (DEMO_ECUS[dst], uds[1:].hex())).encode()
                    resp = bytes((uds[0] + 0x40,)) + uds[1:] + text
                conn.sendall(struct.pack(">IHBB", len(resp) + 2, 1, dst, src) + resp)
        except OSError:
            return


def start(host="127.0.0.1"):
    """Starts a background gateway on a free port. Returns (port, stop_fn)."""
    srv = socket.socket()
    srv.bind((host, 0))
    srv.listen(8)
    srv.settimeout(0.2)
    stop = threading.Event()

    def loop():
        while not stop.is_set():
            try:
                c, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            threading.Thread(target=_serve, args=(c,), daemon=True).start()
        srv.close()

    threading.Thread(target=loop, daemon=True).start()
    return srv.getsockname()[1], stop.set
