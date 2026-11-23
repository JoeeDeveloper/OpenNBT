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
