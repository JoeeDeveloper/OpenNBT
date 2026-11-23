# Phase 2 plan: SSH recon and framework check (PLAN ONLY, nothing here has been run)

Status: draft for the owner to approve or reject. Nothing in this repo performs any step below.
Evidence tags as in FEASIBILITY.md: [REF] read in a reference repo, [INFER] inference, [UNKNOWN] must be captured.

## 0. Result of the module-list comparison (host-only, done)
The three reference repos contain **no NBT module list to compare against**. The only SWFL ids they mention are
`0x2720` / `0x271A` for the NBTevo head unit (HU_NBT2) in the ID6 project [REF], which is a different head unit.
None of our captured ids (e.g. 0x1275, 0x1E6B, 0x1FAB, 0x21D2) appear anywhere in `ref/`. The F07 precedent does not
publish its module versions. So the capture cannot be matched to the precedent from what we have; only the libraries
on the unit itself can settle the ABI question (FEASIBILITY.md section 2).

## 1. Why this phase is different
Phases 0-1 were read-only. Phase 2 needs a root shell on the head unit, and the stock NBT does not accept SSH logins.
[REF] `nbt-android-auto/README.md`: SSH must be "unlocked (patched) once"; the developer used FeatureInstaller, which can
need several attempts and may report errors even when the unlock worked. **That unlock changes the head unit's
configuration and is the only modifying step in this phase.** It is the owner's decision, run by the owner with a tool
the owner sources. This project does not provide, fetch, or script it.

## 2. Gates (all must be true before the unlock)
1. You decide to proceed, knowing the unlock is not something this project can undo. Risk is real but I cannot put a
   number on it: community reports say the unlock can fail or error partway [REF], and I have no measured failure rate.
2. Car on a battery maintainer, parked, handbrake on, not driven afterwards until the unit has been checked.
3. A recovery route exists: you know who could reflash or recode the head unit if it misbehaves (dealer or specialist),
   and you accept the cost. [UNKNOWN] whether a warranty or service-plan position changes this.
4. A backup of the head unit's coding. **Gap:** our tools cannot take one. It needs BMW tools (ISTA/E-Sys style) that
   you do not currently have, so either obtain them legitimately first or accept proceeding without a backup.
5. Phase 1 data saved off OneDrive (it holds unredacted serials).

## 3. Steps once approved
1. (Owner) Run the SSH unlock with FeatureInstaller, reading its documentation for the I-level first. Stop on any
   unexpected behaviour. Check the infotainment still boots normally, then test SSH reachability only.
2. (Owner) Obtain the root credential yourself and type it at the prompt. I will not look it up, store it, or put it in
   any file. Pin the head unit's host key before connecting ([REF] `tools/nbt_ssh_session.py` pins it).
3. Read-only recon over SSH, as a fixed list of commands reviewed before running: `uname -a`, `ls -l` and `sha256sum`
   of `libAppFramework.A.so` and `libCoreFramework.A.so`, the HMI version file, `mount` (to see read-only vs
   read-write), directory listing of `/var/opt/hmi/data/rw/Plugins/` and `/opt/hmi/data/ro/Plugins/`. No writes, no
   remount, no `chmod`, no package installs.
4. Copy the two framework libraries into `.local/` (gitignored) for offline symbol/vtable audit against what the F07
   repo documents. Never commit them (BMW binaries).
5. Close the session. Decide on Phase 3/4 from the audit, not before.

## 4. Stop conditions
- Unlock errors repeat, the unit reboots oddly, or the screen/audio behaves differently: stop and do not retry blindly.
- Framework symbols or layout differ from the F07 precedent: the plugin plan (Phase 4+) is a NO-GO as written.
- Anything asks for a write on the head unit: stop and re-plan; that is a separate approval.

## 5. What I will and will not do
Will: write the read-only command list, the offline audit script, and analyse results you paste.
Will not: source or run the unlock, handle the root credential, write to the head unit, or push anything onto it
without a separate explicit approval for that exact step.
