# Windows installer

Installs the GUI and CLI in the current user profile. Download local GGUF models separately.

Installer: `release/windows/CrackStack-Setup-0.1.0.exe`

SHA-256: `60a6496ee3c1752d3af2b737751d1fdb5d9bb1d7b61f327da7396e4429afc151`

Detached OpenPGP signature: `release/windows/CrackStack-Setup-0.1.0.exe.asc`

This is a detached OpenPGP release signature, not a Windows Authenticode signature.

Public key: `docs/CrackStack_Release_Signing_2026_pubkey.asc`
Fingerprint: `FB1B27B88818C13ADFF50BAE7D20C384A0A90F16`

Compare the fingerprint above before importing the key. From the project root:

```powershell
gpg --show-keys docs/CrackStack_Release_Signing_2026_pubkey.asc
gpg --import docs/CrackStack_Release_Signing_2026_pubkey.asc
gpg --verify release/windows/CrackStack-Setup-0.1.0.exe.asc release/windows/CrackStack-Setup-0.1.0.exe
gpg --verify release/windows/SHA256SUMS.asc release/windows/SHA256SUMS
```
