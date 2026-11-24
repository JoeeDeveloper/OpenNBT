# OpenNBT

Hobbyist, read-only-first diagnostics for an original (pre-Evo) BMW **NBT** head unit over HSFZ/UDS. Started as
research into a native QNX plugin to show diesel/DME data on the car's screen; as of November 2026 the project's
primary direction has pivoted toward making the tool do as much as possible with the car **for free** —
BimmerCode-style reads (and eventually generic coding scaffolding) over UDS, with no paid subscription and no
FSC/feature-activation bypass. The QNX plugin idea is parked, not abandoned (see [#6](https://github.com/JoeeDeveloper/OpenNBT/issues/6)).

**Status:** Phase 1 (read-only recon) is done and confirmed against a real car. Phase 2 (SSH unlock, for the
original plugin path) is drafted and gated, awaiting the owner's own go/no-go. Phase 4 (free coding reads/writes)
is the current focus — see [open issues](https://github.com/JoeeDeveloper/OpenNBT/issues) for the live roadmap,
[docs/FEASIBILITY.md](docs/FEASIBILITY.md) for the original plugin's go/no-go reasoning, and
[docs/LOG.md](docs/LOG.md) for every step taken.

[![CI](https://github.com/JoeeDeveloper/OpenNBT/actions/workflows/ci.yml/badge.svg)](https://github.com/JoeeDeveloper/OpenNBT/actions/workflows/ci.yml)

Roadmap and open questions are tracked in [GitHub Issues](https://github.com/JoeeDeveloper/OpenNBT/issues). Captures from other owners' cars are welcome via the issue template.

## What exists

| File | Purpose |
|---|---|
| `tools/hsfz_probe.py` | Read-only HSFZ/UDS probe: `discover`, `recon`, `idscan` (fixed identification sweeps), `read` |
| `tools/opennbt_gui.py` | tkinter GUI around the probe, with a demo mode (no car) |
| `tools/analyze_capture.py` | Summarizes `.local/captures/*.jsonl` per ECU |
| `tools/fake_gateway.py` | Fake HSFZ gateway on loopback for demos and tests (invented replies) |
| `tests/` | Unit tests against the fake gateway |
| `docs/CAR_CHECKLIST.md` | What to do at the car |

Python 3.8+ and the standard library only. The GUI needs tkinter (included with Windows Python; `python3-tk` on Debian/Ubuntu).

## Safety model

- The probe sends only OBD service `01` and UDS service `22` (read data by identifier). Anything else is refused before a socket is opened.
- Nothing is sent without `--yes-parked` (parked, handbrake on, ignition on, engine off). The GUI requires the same tick-box.
- At most 12 requests per run, spaced 0.2 s, one fresh connection each.
- VIN reads are redacted, and captures go to `.local/captures/` (gitignored).
- The ECU addresses and DIDs used by `recon` are partly **unverified** guesses; see the checklist for what the reference repos confirm.

## Quick start

```
python -m unittest discover tests
python tools/opennbt_gui.py            # tick "Demo mode" to try it without a car
python tools/hsfz_probe.py recon --gateway <169.254.x.x> --local <laptop 169.254.x.x> --yes-parked
python tools/hsfz_probe.py idscan --gateway <169.254.x.x> --local <laptop 169.254.x.x> --yes-parked
python tools/analyze_capture.py
```

On Windows, `run_gui.bat` starts the GUI.

## Not in scope

FeatureInstaller/FSC feature-activation bypass, and anything requiring a paid subscription (BimmerCode, BimmerStudio,
or similar). SSH access and writing to the head unit are separate, explicitly gated steps owned and run by the car's
owner, not by this project — see [docs/PHASE2_PLAN.md](docs/PHASE2_PLAN.md). Building the QNX plugin needs a licensed
QNX 6.5 SDP and is currently parked. This is not related to NBTevo Tool or any FSC-bypass project.

## Disclaimer

Use at your own risk, on your own car, parked. No warranty. Not affiliated with BMW.

## License

Source files are headed as MIT. A `LICENSE` file has not been added yet.
