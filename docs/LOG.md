# OpenNBT log

Every command and result, one change at a time. No car or head-unit access so far.

## 2026-11-18 - Phase 0

| # | Command / action | Result |
|---|---|---|
| 1 | `git init -b main` in project folder; `git remote add origin https://github.com/JoeeDeveloper/OpenNBT.git` | OK. Not pushed. |
| 2 | Created `docs/`, `ref/`, `.local/`; wrote `.gitignore` (`.local/`, `ref/`, `*.so`, captures, logs, keys, `backups/`) | OK |
| 3 | `git clone --depth 1` of `JayJay3071/nbt-android-auto`, `inotbarnacle/ID6_apps_prerelease`, `Sq00ky/Supra-iDrive6-Android-Auto` into `ref/<name>/` | OK. Read-only, nothing executed. |
| 4 | Read reference files listed in the prompt (see FEASIBILITY.md for which) | `sysetshell`, `SYS_DEBUG`, `setk` appear in none of them. No diesel signals in the Evo repo. |
| 5 | Wrote `docs/FEASIBILITY.md` | Done |

Not yet read in full: `ref/ID6_apps_prerelease/source/native/src/collector.c`, `gauge_core.c`, `most/*`; `ref/nbt-android-auto/tools/nbt_request.py`, `src/android_auto/knob/ref/` (MOST/DSI client, PolyForm); the Supra NBT-AAD repo; the BimmerGestalt RHMI docs site.

Note for Phase 1+: Phase 0 touched nothing on the car or head unit.

## 2026-11-18 - Phase 1 prep (host only, no car)

| # | Action | Result |
|---|---|---|
| 6 | User answers: engine unknown, no BMW diagnostic data, Win11 + ENET cable, no FeatureInstaller/QNX/VirtualBox yet | Recorded in docs/PREP.md |
| 7 | Wrote `tools/hsfz_probe.py` (original code): only OBD `01xx` / UDS `22xxxx` accepted, needs `--yes-parked`, fresh connection per request, 0.2 s spacing, max 12, VIN DID redacted, captures to `.local/captures/` | Done, never run against a car |
| 8 | Wrote `tests/test_hsfz_probe.py` (fake gateway on loopback) and `python -m unittest discover tests` | 11 tests pass |
| 9 | Wrote `docs/PREP.md` | Done |

Known unverified in the probe: the UDP discovery frame (`00 00 00 00 00 11` to port 6811) is from memory, not from a reference.

## 2026-11-23 - recon command (host only, no car yet)

| # | Action | Result |
|---|---|---|
| 10 | Added `recon` to `tools/hsfz_probe.py`: fixed 12-request read-only sweep (22 F101/F150/F18C/F187/F189 on ECUs 10, 63, 60, 12), ASCII decode of printable replies, shared runner with `read`. ECU addresses/DIDs are UNVERIFIED general knowledge. | 14 tests pass |
| 11 | Added `tools/opennbt_gui.py` (tkinter, demo mode), `tools/analyze_capture.py`, `tools/fake_gateway.py`; `run_requests` gained `port`/`on_row`. GUI NOT run here: no tkinter/display on this Linux box, syntax-checked only. | 16 tests pass |
| 12 | Grepped refs for ECU addresses/DIDs/gateway IPs; wrote `docs/CAR_CHECKLIST.md` and `run_gui.bat`. Recon plan unchanged (nothing in refs contradicts it; most of it is still unconfirmed). | Done |
| 13 | Added README, GitHub Actions CI (ubuntu+windows, py3.9/3.13, unittest + py_compile of the GUI), dependabot for actions, issue/PR templates, SECURITY.md | Pending first CI run |
| 14 | First real recon on a car (gateway found by discovery; ECUs 10/63/60/12 answered). Added SVK-like decoder to analyze_capture.py, redaction of F18C serials, fixed redact/ascii ordering so `read 22F190` no longer errors. | 18 tests pass |
| 15 | Searched refs for module ids/build strings: nothing comparable (only NBTevo SWFL ids). Wrote docs/PHASE2_PLAN.md (plan only; SSH unlock is the single modifying step and is owner-run). | Done |
| 16 | Owner worked through Phase 2 gates (accepted risk, maintainer connected, recovery route confirmed, proceeding without a coding backup, OneDrive captures deleted). Wrote docs/SSH_RECON_COMMANDS.md (fixed read-only command list) and tools/audit_framework_abi.py (offline ELF32 symbol/hash audit vs F07 precedent names). | 23 tests pass |

## 2026-11-24 - Project pivot: free BMW coding over UDS

| # | Action | Result |
|---|---|---|
| 17 | Owner decision: primary direction pivots from the QNX HMI plugin toward free BMW coding (BimmerCode-style reads/writes over UDS/HSFZ) — no paid subscription, no FSC bypass. Two uploaded `.BIN` update-patch files were analysed (static, read-only; not committed, deleted from scratch after). They implement a symlink/path-traversal unlock in the head unit's own USB-update daemon ("NBTCarHU") matching a named, BMW-patched (2019) vulnerability later confirmed via a published VicOne write-up the owner linked. | Logged on issue #5; no code change |
| 18 | GitHub housekeeping: closed #1 and #2 (confirmed done on the real car), labelled #6 (QNX toolchain) `deprioritized` (parked, not abandoned), opened #9 (Phase 4: free coding reads + write scaffolding) as the active roadmap item. Set repo description/topics. Updated README to reflect the pivot. | Done |
| 19 | Researched a free UDS read path for FA (vehicle order) and SVT for issue #9: antoniovazquezblanco.github.io/BMW-Hacking (vehicle_order, glossary) and emdzej.github.io/ediabasx-docs-sgbd (`d_svt.grp`, `D_FAH.grp`). Neither page gives a DID, routine id, or ECU for FA; "SVT" there means System-Verbau-Tabelle (installation table), not software versions, and the two `.grp` files hit by name are KWP2000 ECU-identification lookups, not FA or version reads. No confirmed simple UDS path found for either — not implementing a guessed DID for something this central. | No code change from this step |
| 20 | Added `idscan` to `tools/hsfz_probe.py`: a second fixed 12-request sweep of standard ISO 14229-1 Annex C identification DIDs not already in `recon` (F188 ECUSoftwareNumber, F191 ECUHardwareNumber, F18B ECUManufacturingDate) across the same 4 ECUs. Same safety model (`--yes-parked`, one connection per request, spaced). Not yet run against a real car. | 26 tests pass |
| 21 | Added `tools/uds_write.py` (new module, kept out of `hsfz_probe.py` so that module's read-only guarantee stays true): generic WriteDataByIdentifier/SecurityAccess support, gated by a VIN-match read, mandatory backup-before-write, dry-run by default (`--commit` + `--i-understand-this-writes-to-the-ecu` both required to actually send). No BMW seed-key algorithm shipped or known; `security_access()` raises without one. Not wired to any coding payload. Not yet run against a real car. | 38 tests pass |

## 2026-11-27 - `idscan` run on the real car

| # | Action | Result |
|---|---|---|
| 22 | Added an `idscan` button to `tools/opennbt_gui.py` (mirrors `recon`, same safety gating). | 38 tests pass; published |
| 23 | Ran `idscan` on the real car (ECUs 10/63/60/12, different laptop/ENET adapter this time). F188/F191 (ECUSoftwareNumber/ECUHardwareNumber): NRC 31 on all four. F18B (ECUManufacturingDate) answered on all four — `15 03 02`/`15 03 13`/`15 03 13`/`15 03 16`. | Logged in docs/CAR_CHECKLIST.md |
| 23a | Owner supplied this car's DVLA record (first registered 05 Oct 2015). An initial hex decode of F18B's bytes gave 2021, which doesn't fit; re-reading the same bytes as **BCD** gives 2015-03-(02/13/13/16) for the four ECUs — consistent with the October 2015 registration. Corrected the decode in docs/CAR_CHECKLIST.md. F18A still doesn't decode under either reading. | Corrected |
| 24 | Ad hoc `read 22F18A 22F199 22F19D` on the head unit and DME: F18A (ECUInstallationDate) answered on the head unit only (`00 00 20`, doesn't fit the F18B decode, left uninterpreted); F199 (programmingDate) and F19D (CVN) refused (NRC 31) on both. | Logged in docs/CAR_CHECKLIST.md |

## 2026-11-27 - Research: a safe write target for `uds_write.py`

| # | Action | Result |
|---|---|---|
| 25 | Researched whether any BMW UDS DID is documented as writable (service 0x2E) without a prior SecurityAccess (0x27) unlock, on ZGW (0x10), NBT Evo HU (0x63), cluster (0x60), or DME (0x12). Checked generic UDS references (no BMW specifics), emdzej.github.io/ediabasx-docs-sgbd job listings for `g_zgw`, `entrynav`/`entry`, `nbtevo`, `mevd172` (N55 DME family) and the older KWP2000 `mrkomb18` for contrast, BMW enthusiast forums, and public BMW security research (KeenLab, BlackHat 2019 ZGW/BDC talk — PDF text wasn't extractable). Found real `0x2E` job/DID lists on several ECUs (NBT Evo HU: `$1000` test-stamp write, generic `STEUERN`; N55 DME: a block of DIDs `0x5F75`-`0x5FF5`) but **no source states, either way, whether any of them need SecurityAccess first** — the SGBD docs don't render that gating in prose. One gist of captured ZGW traffic shows a `0x2E` write to `0x172A` (static/dynamic IP config) with no `0x27` visible nearby, but absence of evidence isn't confirmation. **Dead end**: no DID should be treated as "known writable without security" on any of these ECUs. `uds_write.py` keeps requiring `security_access()` by default; no code change. | No code change |
