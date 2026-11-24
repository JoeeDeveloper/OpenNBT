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
