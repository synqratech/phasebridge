# Security Policy

PhaseBridge provides **strict, lossless** conversion guarantees. We take security and integrity seriously.

## Supported Versions

We support the latest **minor** release of the SDK and PIF v1.x.

| Version        | Status    |
|----------------|-----------|
| PIF v1.x       | Supported |
| SDK 0.1.x      | Supported |
| Older releases | Best-effort, please upgrade |

## Reporting a Vulnerability

If you find a potential security or integrity issue, please report it **privately**:

- **Email:** anvifedotov.biz@gmail.com  
- **Subject:** `[SECURITY] <short description>`  
- Include: affected version(s), steps to reproduce, sample inputs, environment.

We’ll acknowledge within **5 business days** and provide updates until resolution.

> Please **do not** open public issues for suspected vulnerabilities.

## Vulnerability Types We Prioritize

- **Integrity violations** — decode differs from original while `meta.hash_raw` passes.  
- **Validation gaps** — malformed or out-of-range PIF accepted.  
- **CLI injection** — unsafe handling of input paths or arguments.  
- **Denial-of-service** — unbounded memory or CPU usage on crafted inputs.  

## Coordinated Disclosure

- A patched release will be published.  
- `SECURITY.md` and `CHANGELOG.md` will be updated.  
- A public advisory (e.g. GitHub Security Advisory) may be issued.  

---

ℹ️ More detailed notes on hardening and cryptographic considerations are in  
[`docs/security_notes.md`](docs/security_notes.md).
