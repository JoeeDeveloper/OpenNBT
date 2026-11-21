# Your preparation checklist (nothing here touches the car unless stated)

Answers so far (2026-11-18): engine unknown, no ISTA/INPA/logger data, Windows 11 laptop + working ENET cable (IP not checked yet), no FeatureInstaller experience, no QNX account, no VirtualBox, no HU photo yet.

## A. Do now, car not needed

1. **Install VirtualBox** (virtualbox.org, Windows host). Needed for Phase 3.
2. **QNX 6.5.0 SDP (x86)**: this needs a legitimate QNX download and licence. Create a QNX myQNX account and see what non-commercial access QNX offers for 6.5. Tell me what you find; I will not use key generators or unlicensed archives (one reference links one, I am ignoring it). Phase 3 is blocked until this exists, but Phases 1 and 2 are not.
3. **Python**: already installed here (3.14.2). Nothing needed.
4. **A diesel data source** (the biggest gap): without BMW identifiers Phase 1 can only try standard OBD PIDs. Cheapest useful options, your choice:
   - a BMW-capable app/adapter you already own (BimmerCode/Carly/BimmerLink-style apps show live DDE values; screenshots of their live-data list help me see what the ECU exposes), or
   - ISTA/INPA via your ENET cable (install from a source you are licensed for; I will not source it).
   Tell me which you can get.

## B. At the car (parked, handbrake on, battery maintainer connected)

1. Plug ENET into the OBD port and the laptop. Ignition on, engine off.
2. In PowerShell run `ipconfig` and send me the Ethernet adapter's IPv4 address and subnet mask (not the MAC). Expect 169.254.x.x after ~30 s.
3. Photograph the HU version/info screen (look under the vehicle/system settings) so I can compare with `NBT_L15184A`.
4. Do NOT run FeatureInstaller yet. Read its documentation for your I-level first; it changes head-unit configuration. I will prepare a pre-check list before that step, and you will approve it.

## C. First live test (only after I ask you and you say yes in chat)

Host-only, read-only, via the new probe. I will give you exact commands. They look like:

```
python tools/hsfz_probe.py discover --local <laptop 169.254.x.x> --yes-parked
python tools/hsfz_probe.py read --gateway <gateway> --local <laptop> --ecu 12 010C 0105 --yes-parked
```
`discover` sends one UDP broadcast whose frame format is unverified. Captures go to `.local/captures/` (gitignored). VIN replies are redacted.
