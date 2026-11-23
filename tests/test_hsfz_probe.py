"""Host tests for tools/hsfz_probe.py against a fake gateway. No car needed. Run: python -m unittest discover tests"""
import argparse
import socket
import struct
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import hsfz_probe as hp  # noqa: E402


def frame(src, dst, payload, control=1):
    return struct.pack(">IHBB", len(payload) + 2, control, src, dst) + payload


def fake_gateway(script):
    """script(conn, request_payload) sends frames. Returns (port, thread, received list)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    got = []

    def run():
        conn, _ = srv.accept()
        with conn:
            hdr = conn.recv(6)
            length, ctrl = struct.unpack(">IH", hdr)
            body = conn.recv(length)
            got.append((ctrl, body))
            script(conn, body)
        srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], t, got


def ask(script, uds, ecu=0x12, **kw):
    port, t, got = fake_gateway(script)
    with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
        try:
            return hp.exchange(s, ecu, uds, **kw), got
        finally:
            t.join(2)


class Probe(unittest.TestCase):
    def test_request_validation(self):
        for ok in ("010C", "0105", "22F190", "22 43 00"):
            hp.parse_request(ok)
        for bad in ("2E4300", "2F0101", "3101", "1003", "14FFFFFF", "19020C", "0100FF", "22F1", "", "zz"):
            with self.assertRaises(argparse.ArgumentTypeError, msg=bad):
                hp.parse_request(bad)

    def test_frame_layout(self):
        self.assertEqual(hp.build_frame(0x12, bytes.fromhex("010C")).hex(), "000000040001f412010c")

    def test_positive(self):
        res, got = ask(lambda c, b: c.sendall(frame(0x12, 0xF4, bytes.fromhex("410c1a f8".replace(" ", "")))), bytes.fromhex("010C"))
        self.assertEqual(res["data"], "1a f8")
        self.assertEqual(got[0][1], bytes.fromhex("f412010c"))

    def test_negative(self):
        res, _ = ask(lambda c, b: c.sendall(frame(0x12, 0xF4, bytes.fromhex("7f2231"))), bytes.fromhex("224300"))
        self.assertEqual(res["nrc"], "31")

    def test_pending_then_positive(self):
        def s(c, b):
            c.sendall(frame(0x12, 0xF4, bytes.fromhex("7f2278")))
            c.sendall(frame(0x12, 0xF4, bytes.fromhex("62430001 02".replace(" ", ""))))
        res, _ = ask(s, bytes.fromhex("224300"))
        self.assertEqual(res["data"], "01 02")

    def test_alive_check_answered_and_foreign_frames_ignored(self):
        acks = []

        def s(c, b):
            c.sendall(struct.pack(">IHBB", 2, 0x12, 0xF4, 0x00))
            c.sendall(frame(0x18, 0xF4, bytes.fromhex("410c0000")))  # other ECU: ignore
            acks.append(c.recv(8))
            c.sendall(frame(0x12, 0xF4, bytes.fromhex("410c0001")))
        res, _ = ask(s, bytes.fromhex("010C"))
        self.assertEqual(res["data"], "00 01")
        self.assertEqual(acks[0], struct.pack(">IHBB", 2, 0x13, 0, 0xF4))

    def test_timeout(self):
        with self.assertRaises(TimeoutError):
            ask(lambda c, b: __import__("time").sleep(1), bytes.fromhex("010C"), reply_timeout=0.3)

    def test_oversized_frame_rejected(self):
        with self.assertRaises(ValueError):
            ask(lambda c, b: c.sendall(struct.pack(">IH", 99999, 1)), bytes.fromhex("010C"))

    def test_exchange_refuses_write_service(self):
        with self.assertRaises(ValueError):
            hp.exchange(None, 0x12, bytes.fromhex("2E4300"))

    def test_vin_redacted(self):
        r = hp.redact("22f190", {"reply": "62 f1 90 aa", "data": "aa"})
        self.assertEqual(r["data"], "<redacted VIN>")
        self.assertEqual(hp.redact("22f187", {"data": "aa"})["data"], "aa")

    def test_recon_plan_is_read_only_and_bounded(self):
        self.assertLessEqual(len(hp.RECON_PLAN), hp.MAX_REQUESTS)
        for ecu, did in hp.RECON_PLAN:
            hp.parse_request(did)
            self.assertNotIn(did.lower(), hp.VIN_DIDS)

    def test_add_ascii(self):
        self.assertEqual(hp.add_ascii({"data": "41 42 43"})["ascii"], "ABC")
        self.assertNotIn("ascii", hp.add_ascii({"data": "00 01 ff"}))
        self.assertNotIn("ascii", hp.add_ascii({"nrc": "31"}))

    def test_recon_refuses_without_confirmation(self):
        with self.assertRaises(SystemExit):
            hp.main(["recon", "--gateway", "169.254.10.3"])

    def test_cli_refuses_without_confirmation(self):
        with self.assertRaises(SystemExit):
            hp.main(["read", "--gateway", "169.254.10.3", "010C"])
        with self.assertRaises(SystemExit):
            hp.main(["discover"])


if __name__ == "__main__":
    unittest.main()
