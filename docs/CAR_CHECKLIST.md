# At-the-car checklist (read-only recon)

Before: laptop charged, car battery maintainer on if possible, handbrake on, parked, ignition on, engine off.

1. Plug ENET into the OBD port and the laptop. Wait ~30 s for a 169.254.x.x address.
2. `ipconfig` -> note the Ethernet IPv4 (laptop IP). Do not share the MAC.
3. Run the GUI (double-click `run_gui.bat`), or CLI `python tools\hsfz_probe.py recon --gateway <gw> --local <laptop> --yes-parked`.
4. Gateway address: try `discover` first (frame unverified). If nothing, the refs show the NBT head unit itself answering SSH at **169.254.199.99** (ID6/Evo: .119), which is the HU, not necessarily the HSFZ gateway. Report what `ipconfig` shows and which of these respond; do not scan the network.
5. Send the printed lines (VIN is redacted automatically). Then `python tools\analyze_capture.py` for the summary.
6. Photograph the head-unit version screen.
7. Stop. No FeatureInstaller, no SSH logins, no writes tonight.

## What the references confirm about `recon` (checked 2026-11-23)
- DME address 0x12 over HSFZ: confirmed in `ID6 .../diag_link.c` (tester 0xF4, control 0x0001, alive-check 0x0012/0x0013 all match our probe).
- 0x63 appears as the head unit's own diagnostic source address (`ID6 docs/MOST.md`), so a head-unit target of 0x63 is plausible, still unverified as a *target*.
- Not found in any reference: gateway 0x10, cluster 0x60 as targets, and DIDs F101, F150, F18C, F187, F189. These stay unverified guesses; negative responses are expected and informative.

## Update after first real recon (2026-11-23, one NBT car, F-series, label NBT_L15184A)
- Discovery frame (`00 00 00 00 00 11` to UDP 6811) works: the gateway answered with a 56-byte reply. Confirmed on one car.
- Over HSFZ via the gateway, ECUs **0x10, 0x63, 0x60, 0x12** all answered, so those addresses are confirmed as targets.
- DIDs **F101, F150, F18C** answered on all four ECUs. **F187 and F189** returned NRC 31 (not supported) on the head unit and DME.
- F101 decodes as a list of 8-byte records (class, 4-byte module id, 3-byte version); the count field matched the number of records on all three ECUs. The head-unit versions (3.3.1, 3.5.1, 3.7.1) are consistent with the on-screen Media/Phone `003.003.001`. Class names (BTLD/SWFL/HWEL...) are INFERRED, not confirmed.
- F150 returns 3 bytes per ECU (meaning unknown). No readable HMI build string was returned, so the framework ABI question is still open.
- F18C (ECU serial) is now redacted in captures, like the VIN.

## Next time at the car: `idscan`
`python tools\hsfz_probe.py idscan --gateway <gw> --local <laptop> --yes-parked` tries three more standard
ISO 14229-1 identification DIDs (F188, F191, F18B) on the same four ECUs — 12 more read-only requests, same
safety model as `recon`. F187/F189 (same standard range) already came back NRC 31 on the head unit and DME, so
expect some refusals; any that answer add free, already-standardized ECU identification data.
