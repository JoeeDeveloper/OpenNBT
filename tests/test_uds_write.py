"""Host tests for tools/uds_write.py against a scripted fake gateway. No car needed, nothing real is written.
Run: python -m unittest discover tests"""
import json
import socket
import struct
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import uds_write as uw  # noqa: E402
import hsfz_probe as hp  # noqa: E402


def frame(src, dst, payload):
    return struct.pack(">IHBB", len(payload) + 2, 1, src, dst) + payload


def fake_gateway(script, ecu=0x12):
    """script(conn, uds_bytes_received) -> None, sending whatever frames it likes. Returns (port, thread)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)

    def run():
        conn, _ = srv.accept()
        try:
            with conn:
                try:
                    while True:
                        hdr = conn.recv(6)
                        if len(hdr) < 6:
                            return
                        length, _ctrl = struct.unpack(">IH", hdr)
                        body = conn.recv(length)
                        script(conn, body[2:])  # strip src/dst, keep uds bytes
                except (OSError, ConnectionError):
                    return
        finally:
            srv.close()

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return srv.getsockname()[1], t


VIN = "WBA00000000000001"


def connect(port):
    return socket.create_connection(("127.0.0.1", port), timeout=2)


class WriteScaffolding(unittest.TestCase):
    def test_refuses_vin_as_write_target(self):
        with self.assertRaises(ValueError):
            uw._refuse_sensitive_did("F190")

    def test_refuses_serial_as_write_target(self):
        with self.assertRaises(ValueError):
            uw._refuse_sensitive_did("F18C")

    def test_did_validation(self):
        self.assertEqual(uw._did_hex("2a10"), "2A10")
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            uw._did_hex("zz")
        with self.assertRaises(argparse.ArgumentTypeError):
            uw._did_hex("2A1")

    def test_backup_then_dry_run_sends_no_write_frame(self):
        requests = []

        def script(conn, uds):
            requests.append(uds.hex())
            if uds == bytes.fromhex("222A10"):
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("622A10AABB")))
            else:
                self.fail("unexpected request in dry-run: %s" % uds.hex())

        port, t = fake_gateway(script)
        try:
            with tempfile.TemporaryDirectory() as d, connect(port) as s:
                plan = uw.write_did(s, 0x12, "2A10", "CC DD", d, commit=False)
                backup = json.loads(Path(plan["backup"]).read_text())
        finally:
            t.join(2)
        self.assertTrue(plan["dry_run"])
        self.assertEqual(plan["old_value_hex"], "aa bb")
        self.assertEqual(plan["new_value_hex"], "CCDD")
        self.assertEqual(requests, ["222a10"])  # only the backup read, never a 2E write
        self.assertEqual(backup["value_hex"], "aa bb")

    def test_commit_sends_write_after_backup(self):
        requests = []

        def script(conn, uds):
            requests.append(uds.hex())
            if uds == bytes.fromhex("222A10"):
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("622A10AABB")))
            elif uds == bytes.fromhex("2E2A10CCDD"):
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("6E2A10")))

        port, t = fake_gateway(script)
        try:
            with tempfile.TemporaryDirectory() as d, connect(port) as s:
                plan = uw.write_did(s, 0x12, "2A10", "CCDD", d, commit=True)
        finally:
            t.join(2)
        self.assertFalse(plan["dry_run"])
        self.assertEqual(requests, ["222a10", "2e2a10ccdd"])
        self.assertNotIn("nrc", plan["result"])

    def test_write_refused_without_backup(self):
        def script(conn, uds):
            conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("7F2231")))  # backup read refused

        port, t = fake_gateway(script)
        try:
            with tempfile.TemporaryDirectory() as d, connect(port) as s:
                with self.assertRaises(ValueError):
                    uw.write_did(s, 0x12, "2A10", "CCDD", d, commit=True)
        finally:
            t.join(2)

    def test_security_access_refuses_without_algorithm(self):
        with self.assertRaises(ValueError):
            uw.security_access(None, 0x12, 0x01, None)

    def test_security_access_rejects_even_level(self):
        with self.assertRaises(ValueError):
            uw.security_access(None, 0x12, 0x02, lambda seed: seed)

    def test_security_access_success_with_toy_algorithm(self):
        def script(conn, uds):
            if uds == bytes.fromhex("2701"):
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("6701DEADBEEF")))
            elif uds[:2] == bytes.fromhex("2702"):
                key = uds[2:]
                expected = bytes(b ^ 0xFF for b in bytes.fromhex("DEADBEEF"))
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("670200" if key == expected else "7F2735")))

        port, t = fake_gateway(script)
        try:
            with connect(port) as s:
                ok, nrc = uw.security_access(s, 0x12, 0x01, lambda seed: bytes(b ^ 0xFF for b in seed))
        finally:
            t.join(2)
        self.assertTrue(ok)
        self.assertIsNone(nrc)

    def test_security_access_wrong_key_rejected(self):
        def script(conn, uds):
            if uds == bytes.fromhex("2701"):
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("6701DEADBEEF")))
            elif uds[:2] == bytes.fromhex("2702"):
                conn.sendall(frame(0x12, hp.TESTER, bytes.fromhex("7F2735")))  # invalid key

        port, t = fake_gateway(script)
        try:
            with connect(port) as s:
                ok, nrc = uw.security_access(s, 0x12, 0x01, lambda seed: b"\x00\x00\x00\x00")
        finally:
            t.join(2)
        self.assertFalse(ok)
        self.assertEqual(nrc, "35")

    def test_cli_requires_both_commit_flags(self):
        with self.assertRaises(SystemExit):
            uw.main(["write", "--gateway", "169.254.10.3", "--ecu", "12", "--did", "2A10", "--data", "AA",
                     "--confirm-vin", "X", "--yes-parked", "--commit"])

    def test_cli_refuses_without_parked(self):
        with self.assertRaises(SystemExit):
            uw.main(["write", "--gateway", "169.254.10.3", "--ecu", "12", "--did", "2A10", "--data", "AA",
                     "--confirm-vin", "X"])


if __name__ == "__main__":
    unittest.main()
