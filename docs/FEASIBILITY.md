# OpenNBT Phase 0 - feasibility and go/no-go

Status: Phase 0 recon, no car or head-unit access yet. Date: 2026-11-18.

Evidence tags used below:
- **[REF]** read directly in a reference repo (file named). Still only as true as the author's claim.
- **[INFER]** my inference or general knowledge, not checked in a reference or on your car.
- **[USER]** stated in your prompt, not found in any reference.
- **[UNKNOWN]** must be captured from the car.

Reference repos are cloned shallow into `ref/` (gitignored). Treated as untrusted data, nothing executed.

## 1. Verdict

**Conditional GO** for Phases 1-2 (host-side read-only probe, SSH recon). **No decision yet on Phase 4+**: whether the stock NBT framework on your unit is ABI-compatible with the one the only existing precedent used is unknown until Phase 2 hashes it.

Why GO is plausible:
- A native HMI plugin on original NBT with a Multimedia entry is demonstrated once, on one car (F07 2014, HMI `NBT_3D1407_Release 3D1407-490-1407N Build 103`). [REF] `docs/history/IDRIVE-HELLO.md`, `README.md`.
- The same car runs a larger plugin with dynamic text updates, focus handlers and `post()` timers, plus a RAM state file written by a native worker. [REF] `src/idrive/aa_entry_plugin.cpp`. That is exactly the Phase 5 architecture.
- The diagnostic side (HSFZ on TCP 6801, UDS `22` / OBD `01` to DME `0x12`) is simple and has a reusable read-only client. [REF] `ID6 source/tools/probe_signals.py`, `native/src/diag_link.c`.

Why not a full GO:
- Single car, single HMI build, "tested once" (see section 8).
- Your I-level and HMI build are unknown, and your HU is not the F07 one.
- No reference covers diesel signals, and none covers a head unit reaching the HSFZ gateway on a plain NBT. The Evo project ships a MOST/DSI fallback because on some cars the HU has no route to the gateway. [REF] `ID6 docs/MOST.md`.

## 2. Single riskiest assumption

**That your unit's `libAppFramework.A.so` / `libCoreFramework.A.so` match the ABI the F07 precedent used** (20-byte `pluginAppInfo`, `PluginApp(IDispatcher&, BasicString<char>, const Bundle&, const Bundle&)` constructor, `post`, `triggerEvent`, `updateModel(unsigned, const TextID&)`, `addHandler(unsigned, unsigned, const ActionDelegate&)`). The plugin declares these by hand and allocates an oversized opaque `PluginApp` (1024 words), so a layout change in another build can corrupt memory rather than fail cleanly. [REF] `aa_entry_plugin.cpp`, `experiments/hello-plugin/hello_plugin.cpp`.

Mitigation: hash both libs and compare exported symbols against the precedent before building anything (section 6); `dlopen` load-check in a separate process first (Phase 4). Hashes of the F07 pair are not published in what I read, so a hash match is probably impossible and a symbol/vtable audit is the realistic check. The Evo project ships `native/tools/audit_framework_abi.py` for this on Evo; reusing the approach for NBT needs a private reference pair, which we do not have. [REF] `ID6 docs/BUILD.md`. So expect: symbol-level comparison against what the F07 repo documents, then a parked, RAM-first load test.

Second-riskiest: SSH root on your exact I-level (section 5).

## 3. How an NBT plugin loads

All [REF] unless tagged. Source: `src/idrive/NbtAndroidAuto.manifest`, `.xml`, `aa_entry_plugin.cpp`, `scripts/car-aa-entry-install.sh`, `IDRIVE-HELLO.md`.

**Location:** `/var/opt/hmi/data/rw/Plugins/<Name>/` (writable partition). Stock plugins live read-only under `/opt/hmi/data/ro/Plugins/` (e.g. `TerminalUIApp`, `SecurityMenu`). Note the Evo path is different (`/var/opt/hmi/data/ID5/Plugins`). [REF] `ID6 PORTING.md`.

**Five files**, manifest written last so the HMI never sees a half package:
1. `lib<Name>.so` - ELF32 i386, QNX, C++ without exceptions/RTTI, `NEEDED`: `libAppFramework.A.so`, `libCoreFramework.A.so`, `libcpp-ne.so.4`, `libc.so.3`. Built `-shared -fPIC -fno-exceptions -fno-rtti -Wl,-z,defs` with `qcc -V4.4.2,gcc_ntox86_cpp-ne`.
2. `<Name>.xml` - RHMI static layout.
3. `<Name>_ALL_Texts.zip` - UTF-8 `language.txt` members, `id=text` lines.
4. `<Name>_ALL_Images.zip`.
5. `<Name>.manifest`.

**Manifest** (verbatim shape of the shipped one):
```xml
<plugin>
  <name>Name</name>
  <type>App</type>
  <file>{pluginDir}/libName.so</file>
  <config>
    <autoStart>yes</autoStart>
    <dependencies>
      <pluginAppConnector><type>Etch</type><id>211</id><asyncCallbacks>yes</asyncCallbacks></pluginAppConnector>
    </dependencies>
    <parameters>
      <DescFile>{pluginDir}/Name.xml</DescFile>
      <TextDBFile>{pluginDir}/Name_ALL_Texts.zip</TextDBFile>
      <ImageDBFile>{pluginDir}/Name_ALL_Images.zip</ImageDBFile>
    </parameters>
  </config>
</plugin>
```
Connector `Etch` id `211` is copied from "the vehicle-installed NbtLiveImage manifest"; the hello example itself says the id "needs validation". [REF] Whether 211 exists on your HMI build is **[UNKNOWN]**; check by listing stock plugin manifests on your unit (read-only) in Phase 2.

**XML** (`<pluginApps><pluginApp applicationType="Multimedia" applicationWeight="200" text="...">`): an `entryButton` (action, model), `hmiAction` targets, `textIdModel` / `raIntModel` models, `hmiState` pages with `label`/`button` components, optional `focusEvent`s. Minimal hello page: 1 entry button, 1 state, 1 label. Dynamic text: a `textIdModel` whose text id is swapped at runtime by `updateModel(modelId, TextID(textId))`. The model changes the *text id*, so the Texts zip must contain **every string the gauge can show** (a precomputed table of strings), not a formatted number. That is a real design constraint for Phase 5: see section 9.

**Native side:** export `extern "C" PluginAppInfo pluginAppInfo = {1, 0, "Name", "Vendor", create, destroy}`; struct is **20 bytes** on NBT (major u16, minor u16, name ptr, vendor ptr, create fn, destroy fn), not the 24-byte Evo record. Factory signature `create(IDispatcher&, const char* name, const Bundle& params, const Bundle& config)`.

**Install pattern** (`car-aa-entry-install.sh`): stage in `/fs/ram3/`, refuse if target dir exists, copy each file as `*.tmp`, `cmp` readback, chmod (755 for `.so`, 644 otherwise), rename, manifest last, final `cmp`. Takes effect after the next *normal* iDrive restart.

**Gotchas recorded in the reference:**
- Factory-time `post()` calls did not run on that HMI; autostart was done from a detached pthread started in `create()` (sleep 15 s, then spawn `boot.sh` with `SPAWN_NEWPGROUP|SPAWN_NOZOMBIE`). `aa_entry_plugin.cpp:134`.
- Page focus handlers via `addHandler(state, 1 /*focus*/, delegate)`; visibility is type 11. `post(Runnable*, delayMs)` runs on the HMI thread; a 500 ms self-reposting poll while the page has focus is the pattern.
- The author saw the HMI stop honouring repeated `triggerEvent`s after a few dozen (they used rate limits). Our gauge page needs no focus events, which avoids this.
- Do not call `triggerEvent`-style tricks in a loop. We should not need any.

**Doc inconsistency noted:** `experiments/hello-plugin/hello_plugin.cpp` header says "Not yet vehicle validated" while `IDRIVE-HELLO.md` records on-screen confirmation on 2026-11-05. The later, larger shipped plugin is the stronger evidence, but still one car.

## 4. Framework ABI differences to expect

- **Evo vs NBT** are different: Evo uses a 24-byte `pluginAppInfo` with an RHMI version field and extra `PluginApp` ctor args; Evo libs live under `/opt/hmi/ID5/lib`. [REF] `IDRIVE-HELLO.md`, `ID6 BUILD.md`. So the Evo gauge plugin layer is **not** reusable; only its architecture is.
- **F07 3D1407 (2014) vs your F30 unit:** F30 and F07 NBT share the platform family, but HMI builds differ by I-level. Your HU strings: `NBT_L15184A`, media `MN-003.003.001` **[USER]**. HMI build and library hashes are **[UNKNOWN]**. Whether the ctor/vtable/`updateModel`/`addHandler` symbols and offsets match is **[UNKNOWN]** until compared.
- What to compare (Phase 2, read-only): (a) `nm -D`/`readelf` style export list of both libs for the five symbols above (mangled names given in the reference: `_ZN3bmw6TextIDC1Ej`, `PluginApp::triggerEvent(unsigned)`, `updateModel(unsigned, TextID const&)`); (b) presence of a stock native plugin on your unit with a 20-byte `pluginAppInfo` (the reference used `libSecurityMenu.so` as the oracle); (c) base `PluginApp` vtable has no pure virtuals.
- Tools on the NBT shell are limited (no `head`, `printf`, `env`, `which`); do the symbol extraction on the laptop/VM from copied libs. [REF] `DEVELOPMENT.md`.

## 5. Getting SSH root on your exact I-level

**What the references say:** NBT unit does not accept SSH by default. On the F07, SSH was enabled with **FeatureInstaller**, "can take several attempts", the last step may report errors even though SSH was enabled, so test the connection before assuming failure. Root password is looked up in a Supra-forum thread (NBT Evo, Toyota). [REF] `README.md`. I will **not** reproduce the password or link-chase it for you; that is your call and your typed input.

**Plan, least invasive first:**
1. FeatureInstaller over ENET **[REF]**. Unknown whether it supports your I-level. I have not read FeatureInstaller's own documentation, only the references' mention. Checklist: do a **backup/read of coding first** with whatever tool it offers, never run write/coding features beyond what the SSH patch needs, and expect it to touch head-unit config (README: "Unlocking SSH changes the head unit's configuration"). This is a write to the HU, so it needs your explicit go-ahead as a separate step.
2. Fallback: UART serial console, then `sysetshell` -> `setk SYS_DEBUG=0x01` **[USER]**. **Not found in any reference I read** (grep of `sysetshell`, `SYS_DEBUG`, `setk` returned nothing in `ref/`). Treat as unverified. Hardware if you need it (**[INFER]**): a 3.3 V USB-UART adapter, access to the HU's debug UART pins, which usually means pulling the unit from the dash, and soldering or a clip. Voltage level and pinout must be confirmed for your exact hardware revision before connecting; wrong levels can damage the unit. I will not give pinouts from memory.
3. `ssh_config` quirks [REF `DEVELOPMENT.md`, `config/ssh_config.example`]: old QNX OpenSSH 5.2, so for the NBT host only:
   ```
   Host nbt
       HostName 169.254.199.99
       User root
       HostKeyAlgorithms +ssh-rsa
       PubkeyAcceptedAlgorithms +ssh-rsa
       MACs +hmac-sha1
       StrictHostKeyChecking yes
       IdentitiesOnly yes
       ForwardAgent no
       ClearAllForwardings yes
       ConnectTimeout 5
   ```
   The reference notes "no KEX downgrade was needed" for the QNX *VM*; the NBT may differ **[UNKNOWN]**. If you use paramiko, pin `paramiko>=3.4,<4` (4+ drops `ssh-rsa` host keys). Pin the host key in `.local/nbt_known_hosts` after comparing the fingerprint; never store the password (the reference session helper reads it via `getpass`, keeps one session open, writes queued requests under `.local/ssh-session/`). I will write my own small equivalent; I can reuse the idea, not the code (PolyForm).
4. Laptop network: ENET at OBD gives 169.254.x.x link-local; the NBT SSH address is `169.254.199.99` **[USER, REF]**. HSFZ diagnostic gateway has a *different* address (see section 7); the reference stresses that SSH IP and gateway IP are separate endpoints. [REF] `ID6 PORTING.md`.

## 6. Reading HMI version and the two framework hashes

Read-only over SSH, Phase 2. **Exact paths on the original NBT are not given in the references.** What is documented:
- Plugin tree: `/var/opt/hmi/data/rw/Plugins/` (rw), `/opt/hmi/data/ro/Plugins/` (ro, stock). [REF]
- Evo only: `/opt/hmi/ID5/lib`, `/opt/sys/etc/nbt_version.txt`. [REF] **Do not assume these on NBT.**
- F07 reported HMI string `NBT_3D1407_Release 3D1407-490-1407N Build 103` after "read-only inspection"; method not recorded. [REF]

Proposed discovery (all read-only; I will show each command and wait for your go-ahead before sending any):
```sh
uname -a
cat /etc/nbt_version.txt 2>/dev/null; ls /opt/sys/etc 2>/dev/null
ls /opt/hmi /opt/hmi/* 2>/dev/null          # find where the HMI libs live
ls -l /var/opt/hmi/data/rw/Plugins/ /opt/hmi/data/ro/Plugins/
df -k /var/opt/hmi/data/rw /fs/ram3
```
Locate the two libs by name (`ls -R` limited to the HMI tree; no `find` assumption), then hash on the laptop after a binary-safe copy (`cat lib > local`, never `scp` text mode; the NBT shell lacks `sha256sum`-style tools possibly, so hash locally and also verify the copy by size). Record hashes in `.local/`, not in git. `sloginfo` baseline stored in `.local/`.

## 7. Diagnostics: what carries over, what does not

**Transport** [REF `probe_signals.py`, `diag_link.c`]: HSFZ over TCP **6801** to the ZGW/gateway; frame = `len(4) | control(2) | src 0xF4 | dst ECU | UDS`; control `0x01` data, `0x12` alive-check (answer with `0x13`); reply must start with `SID+0x40`; NRC `0x78` = response pending. Probe opens a fresh connection per request, spaces them 0.2 s, caps at 12 requests, and **only permits regex `01xx` or `22xxxx`**. Use that rule set; our probe will be the same but written fresh (the Evo repo is MIT so reuse is allowed with notice, but writing a clean tool is as quick).

**Lease:** loopback UDP bind on `127.0.0.1:42861` as a mutex between workers on the HU; waiter pings the holder, holder yields. Concept is MIT-reusable and trivial. [REF `diagnostic_lease.h`]

**Gateway discovery:** the Evo project's default gateway is `169.254.21.3` and it reads a settings file. [REF `diagnostic_gateway.h`] Your car's address is **[UNKNOWN]**; standard discovery is a UDP broadcast on port 6811 **[INFER]**, which I have not verified in the references. In Phase 1 I will first ask you to look at what your laptop sees (`arp -a` / adapter address after plugging in) before sending anything.

**Can the HU reach the gateway?** **[UNKNOWN]**. Evo has an in-HU HSFZ client plus MOST fallback because some cars lack a route. [REF `MOST.md`] MOST tunnel: routine `0x0F0B`, FBlock `0x06` inst `0xF0` FktID `0x050`, source `0x63`, via `DSYSMOSTServer`, **DME only**, reply max 512 bytes, 2-5 s timeouts, DSI send has no timeout so the worker uses `alarm()`. It "worked fine" on one Evo car for `22` reads but was **not run on the Evo simulator** (no tunnel) and OBD `01` over MOST is untested. [REF] On original NBT, the DSI client code exists in the NBT Android Auto repo (`src/android_auto/knob/ref/`, PolyForm, from NBT-AAD). I have not read that code yet. If the HU has no HSFZ route, Phase 5 depends on the MOST client and thus on PolyForm-derived code, which would have to live under `third_party/` and be flagged to you. **Decision point.**

**Diesel signals: nothing in the references.** The Evo SIGNALS.md is a petrol B58/340i table (DME `0x12`, DIDs like `4205`, `56D7` rail pressure, `4300` coolant). Those DIDs are **not valid evidence** for a diesel DDE. [REF `SIGNALS.md`: "not a compatibility list for other engines"]

**Engine:** a 2015 (65 plate, i.e. Sep 2015 - Feb 2016) 320d is **probably B47 / DDE8** (the N47 was being replaced around the July 2015 LCI) **[INFER]**. Do not trust that; identify with read-only `22 F1 xx` identification in Phase 1 and cross-check with a trusted tool. The ECU address `0x12` for the DDE is **[INFER]**, probe 0x12 only after the gateway answers.

**Candidate signals for Phase 1** (candidates only, nothing verified, support is per-ECU and a mapped ECU may differ):
- Standard SAE J1979 service `01` PIDs, in the probe's allowed set: `0C` RPM, `05` coolant, `0B` MAP (boost = MAP minus ambient `33`), `0F` intake temp, `23` fuel rail pressure, `42` control-module voltage, `5C` oil temp, `78`/`79` EGT bank 1/2, `7C` DPF temperature, `7A` DPF delta pressure (some of these **[INFER]** from memory of the standard; BMW may not expose them). Meaning and scaling to be checked against the standard document or a logger before use.
- BMW-specific `22 xxxx` DIDs for charge pressure, DPF soot load / regen status, EGT pre/post DPF, rail pressure actual: **no DID is known to me with confidence**. They must come from your own ISTA/INPA job definitions (the DDE8 SGBD) or a trusted logger capture. I will not guess DIDs. Phase 1 needs those inputs from you.
- Cross-check: your own ISTA/INPA/logger, or at minimum OBD `01` vs `22` where both exist.

## 8. Precedent caveats and safety rules carried over

From `docs/DEVELOPMENT.md` "Safety rules (learned the hard way)" and `IDRIVE-HELLO.md`:
- Never stop or restart stock processes (`io-nme`, `HmiMain3D`). Only SIGTERM our own.
- WAL sprite overlay unpaced uploads deadlocked `WalServer` and crashed the GPU driver (HU restart). Standalone EGL experiments crashed the car. **Our plan uses neither**: text-only RHMI page, state file in RAM.
- Write `.tmp`, compare, rename. Do not blindly repeat commands whose result is unknown. Test in `/fs/ram3/` first (gone after restart).
- HU hang: hold the power button about 30 s.
- The hello result: loading is demonstrated; **destruction/unloading and repeated lifecycle stress were not tested**. "Tested once only": one car, one HMI build, one phone. Treat everything as unverified on your unit.
- A running loaded plugin may need a normal HMI restart to unload; so rollback of a *loaded* plugin is "remove my files, then normal restart".

## 9. Design implications (carry into Phase 4-5)

1. **Dynamic text = swapping text ids.** To show live numbers, the Texts zip must pre-contain all candidate strings, or we use several `textIdModel`s per value with a lookup table (e.g. 0..300 psi, -40..150 C, or a 0.5 step). That bounds range/resolution. An alternative (per-field label with a mutable string model) is **not shown in any reference**; investigate the framework exports in Phase 2 before committing. Calibrate string table size against Texts-zip size limits **[UNKNOWN]**.
2. Updates run via a self-reposting `Runnable` with `app->post(this, 500)` while the page has focus, read a small RAM state file, call `updateModel` only on change. Stale state file (mtime older than 8 s in the reference) -> show `--`.
3. Worker is a separate native process (C), spawned like the reference (`spawn()`, new process group, `SPAWN_NOZOMBIE`), from a detached thread 15 s after HMI start, not from a `post()` in the factory. Autostart via a boot script in our own dir; clean stop with SIGTERM.
4. HSFZ vs MOST: choose after the Phase 1/2 reachability test.
5. Licensing: nothing from reference 1 is needed to start. Reference 1 concepts (file layout, ABI shapes, install script flow) are facts about BMW's formats; I will write original code and keep any literal borrowings out of the MIT tree. If the MOST client from NBT-AAD is needed, isolate under `third_party/` with `Required Notice:` lines and flag it to you.

## 10. Unknowns (all to be captured, none assumed)

| # | Unknown | How it gets resolved |
|---|---|---|
| 1 | Exact engine/DME (N47/DDE7 vs B47/DDE8), DME diag address | Phase 1 read-only identification |
| 2 | HMI version string, framework library hashes, ABI match | Phase 2 read-only |
| 3 | SSH-unlock route for your I-level (`NBT_L15184A`) | FeatureInstaller attempt, UART fallback (you) |
| 4 | Whether Etch connector id 211 is valid on your HMI | Phase 2: inspect stock manifests |
| 5 | Location of HMI libs on original NBT | Phase 2 `ls` |
| 6 | HSFZ gateway address, HU route to gateway, or MOST needed | Phase 1 + Phase 2 tests |
| 7 | Which diesel PIDs/DIDs the DDE answers, and their scaling | Phase 1 + your ISTA/INPA data |
| 8 | Dynamic text capacity (strings, zip size) | Phase 2/4 |
| 9 | Free space in `/var/opt/hmi/data/rw` and `/fs/ram3` | Phase 2 `df` |
| 10 | Unload/lifecycle behaviour of the plugin | Phase 4 testing (parked) |
| 11 | Whether the mapped ECU changes any answers | Phase 1 |

## 11. Physical checklist for you (nothing done yet; ask me before any step touches the car)

1. Confirm engine and DME: tell me what ISTA/INPA/your logger says (or read the engine code off the bay plate/V5C). Ideally a screenshot of identification from your own tool.
2. Get your **own** DDE8/DDE7 definition data (ISTA job names, or INPA/EDIABAS SGBD) for charge pressure, rail pressure, EGT, DPF soot/regen, oil temp. Without it, Phase 1 has no BMW DID list.
3. Laptop: Windows, ENET (OBD-to-Ethernet) cable, Python 3.10+, set the adapter to link-local / DHCP-off as needed. Note: Windows will use a 169.254.x.x address; tell me what the adapter shows.
4. Decide SSH route: FeatureInstaller first. Read its documentation for your I-level; make a coding/config backup with it before use. Tell me when you are ready; I will list the exact pre-checks. For the UART fallback: tell me the exact HU part number, and we confirm the hardware before buying or opening anything.
5. Battery on a charger/maintainer for every session with ignition on (HU and ENET sessions are long). Parked, handbrake on.
6. QNX SDP 6.5.0 (x86): obtain it yourself through QNX's own download and licence flow, plus VirtualBox. I will walk you through the install in Phase 3, and I will not help bypass licensing. (Note: one reference mentions an archive.org copy with a "licence key generator"; I will not use or link that.)
7. A USB stick is **not** needed; do not plug anything into the HU USB.
8. Photograph the head unit's software/version info screen (menu path varies by I-level, **[INFER]**, so look under the vehicle/system settings) as a first cross-check for the HMI/HW/SW strings.

## 12. Go/no-go summary

| Gate | Result |
|---|---|
| NBT plugin concept proven | Yes, once, on another car (F07, 2014) |
| ABI match for your unit | **Unknown, gate for Phase 4** |
| SSH on your unit | **Unknown, gate for Phase 2** |
| Diesel signal list | **Not available, gate for Phase 1 value** |
| HU can reach gateway | **Unknown, decides worker design** |
| Legal/licence path | Clear: original MIT code, PolyForm isolated |

Recommended: proceed to Phase 1 (host-only, read-only), in parallel start the SSH and QNX preparation, and re-evaluate at the Phase 2 hash/symbol comparison.
