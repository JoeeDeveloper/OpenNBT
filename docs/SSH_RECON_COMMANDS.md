# Phase 2 SSH recon: exact commands (read-only)

Run only after: SSH is reachable on your car, you have the root credential (typed by you, never given to me or
stored in this repo), and the gates in `docs/PHASE2_PLAN.md` are accepted. This file is the fixed list referenced
by that plan's step 3. Do not improvise additional commands on the head unit; if you want to run something not
listed here, stop and ask first.

**Never paste the host IP, VIN, or root password into a GitHub issue, commit, or chat you share publicly.** Paste
command *output* here in chat if you want it read; redact anything that looks like a VIN (17 chars) first.

## Connect

Original-NBT SSH may need legacy algorithms (seen on the NBT Evo in the reference repos; try without first):

```
ssh root@<head-unit-IP>
# if that fails to negotiate:
ssh root@<head-unit-IP> -o HostKeyAlgorithms=+ssh-rsa -m hmac-sha1
```

Accept/verify the host key fingerprint once; don't blindly accept on every future connection (pin it, e.g. by
saving `known_hosts` after you've checked it once).

## 1. Identify the system (read-only)

```
uname -a
cat /etc/*version* 2>/dev/null
mount
```

`mount` tells us which filesystems are read-only vs read-write — do not remount anything.

## 2. Locate the HMI framework libraries (read-only)

```
find / -xdev -name 'libAppFramework.A.so' -o -name 'libCoreFramework.A.so' 2>/dev/null
```

Once you have the path(s) from that:

```
ls -l <path>/libAppFramework.A.so <path>/libCoreFramework.A.so
sha256sum <path>/libAppFramework.A.so <path>/libCoreFramework.A.so 2>/dev/null || sum <path>/*.so
```

(QNX may not have `sha256sum`; `sum` or `md5sum` as a fallback is fine — just say which you used.)

## 3. HMI version and plugin directories (read-only)

```
cat /opt/hmi/version.txt 2>/dev/null
ls -la /opt/hmi/data/ro/Plugins/ 2>/dev/null
ls -la /var/opt/hmi/data/rw/Plugins/ 2>/dev/null
```

## 4. Copy the two libraries off the car (read-only on the car; this is a download, not a change)

From your laptop, **not** from the SSH session:

```
scp root@<head-unit-IP>:<path>/libAppFramework.A.so .local/hmi-libs/
scp root@<head-unit-IP>:<path>/libCoreFramework.A.so .local/hmi-libs/
```

`.local/` is gitignored. These are BMW's binaries: never commit, publish, or share them outside this analysis.

## 5. Close the session

```
exit
```

Do not leave the SSH session open longer than needed. Do not run anything that writes, mounts read-write, installs
packages, or starts/stops services. If anything on-car behaves oddly after this (reboots, display glitches), stop
and tell me before doing anything else — do not attempt to fix it over SSH.

## After this: offline audit (no car needed)

```
python tools/audit_framework_abi.py .local/hmi-libs/libAppFramework.A.so .local/hmi-libs/libCoreFramework.A.so
```

Paste its output (symbol names and hashes only — no VIN, no IP) back here.
