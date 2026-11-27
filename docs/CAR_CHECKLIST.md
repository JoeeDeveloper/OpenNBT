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

## Update after `idscan` (2026-11-27, same car, different laptop)
- The GUI gained a second button for `idscan` (mirrors `recon`); 38 tests passed before publishing.
- F188 and F191 (ECUSoftwareNumber / ECUHardwareNumber) returned NRC 31 (not supported) on all four ECUs (10, 63, 60, 12).
- F18B (ECUManufacturingDate) answered on all four: `15 03 02` (0x10), `15 03 13` (0x63), `15 03 13` (0x60),
  `15 03 16` (0x12). INFERRED decode (not confirmed against any reference): byte1 = year-2000 in hex (0x15 = 2021),
  byte2 = month (0x03 = March), byte3 = day in hex (0x02/0x13/0x16 = 2/19/22) — i.e. gateway built 2021-03-02,
  head unit and cluster both 2021-03-19, DME 2021-03-22. Plausible (different suppliers, nearby dates) but unverified.
- Ad hoc `read 22F18A 22F199 22F19D` (ECUInstallationDate, programmingDate, CVN) on the head unit (0x63) and DME
  (0x12): F18A answered on the head unit only (`00 00 20`) — does not fit the F18B date decode, left
  uninterpreted. F199 and F19D came back NRC 31 on both ECUs tried.

## Next time at the car
No fixed plan queued. FA/VO/SVT still has no confirmed free UDS path (see docs/LOG.md, 2026-11-24). Untried
standard Annex C DIDs remain (F180-F186, F192-F198 except F18A/F199/F19D above) if there's ever a reason to look
further, but nothing here promises they'd answer.
