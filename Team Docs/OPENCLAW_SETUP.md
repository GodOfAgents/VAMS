# OpenClaw Setup Guide

**Version**: 1.0
**Target OS**: Windows (PowerShell)

## Prerequisites
- [x] Node.js 22+ (Verified: v23.10.0 detected)

## Installation

### Method 1: Automated Script (Recommended)
Run the included helper script:
```powershell
.\setup_openclaw.ps1
```

### Method 2: Manual Installation
1. **Install CLI**:
   ```powershell
   iwr -useb https://openclaw.ai/install.ps1 | iex
   ```
2. **Onboard & Install Daemon**:
   ```powershell
   openclaw onboard --install-daemon
   ```
3. **Check Status**:
   ```powershell
   openclaw gateway status
   ```

## Post-Installation
- Access the dashboard: `openclaw dashboard`
- Configure API keys if prompted during onboarding.

## Troubleshooting
- **Command Not Found**: Restart terminal or run `$env:Path += ";C:\Users\aseem\AppData\Roaming\npm"`
- **Script Disabled Error**: If you see `cannot be loaded because running scripts is disabled`, run this:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
  ```
  Then try `openclaw doctor` again.
