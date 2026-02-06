# OpenClaw Automated Setup Script
Write-Host ">>> Starting OpenClaw Installation..." -ForegroundColor Cyan

# 1. Install CLI
Write-Host "Downloading and installing OpenClaw CLI..."
try {
    iwr -useb https://openclaw.ai/install.ps1 | iex
} catch {
    Write-Error "Installation failed: $_"
    exit 1
}

# 2. Refresh Environment (to get 'openclaw' in path)
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
Write-Host "Environment refreshed." -ForegroundColor Green

# 3. Verify Installation
try {
    openclaw --version
    Write-Host "OpenClaw CLI installed successfully." -ForegroundColor Green
} catch {
    Write-Warning "OpenClaw command not found yet. You may need to restart your terminal."
}

# 4. Prompt for Onboarding
Write-Host "`n>>> Installation Complete." -ForegroundColor Cyan
Write-Host "To initialize the daemon, run:" -ForegroundColor Yellow
Write-Host "    openclaw onboard --install-daemon" -ForegroundColor Yellow
