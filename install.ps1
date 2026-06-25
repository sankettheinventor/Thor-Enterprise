<#  THOR Enterprise - one-line Windows installer (PURE CODE, no AI).

    Premium first-run: run ONE line, click "Allow" on the Windows prompts, and THOR sets up the whole
    system itself - Docker, WSL+Ubuntu, the engine, the AI room images - then opens the cockpit.

    Run (PowerShell):
        irm https://raw.githubusercontent.com/<you>/thor-enterprise/main/install.ps1 | iex
      or, from a clone:
        powershell -ExecutionPolicy Bypass -File install.ps1

    Flags:
        -Check     detect only, install nothing (safe dry-run)
        -Yes       assume "yes" to every prompt (unattended)
        -ThorRepo  git URL to clone THOR from (default below)
        -Distro    WSL distro to use (default Ubuntu)

    The only thing this cannot do for you is sign you into Claude - that is your identity (done once,
    later, with the "Connect Claude" button in the cockpit). Everything else is automatic.
#>
[CmdletBinding()]
param(
  [switch]$Check,
  [switch]$Yes,
  [string]$ThorRepo = "https://github.com/sankettheinventor/thor-enterprise.git",
  [string]$Distro   = "Ubuntu"
)

$ErrorActionPreference = "Stop"
function Step($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Good($m) { Write-Host "  [OK]  $m" -ForegroundColor Green }
function Miss($m) { Write-Host "  [--]  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "  [XX]  $m" -ForegroundColor Red }
function Note($m) { Write-Host "  $m" -ForegroundColor DarkGray }

function Ask($m) {
  if ($Yes) { return $true }
  $a = Read-Host "  $m  [Y/n]"
  return ($a -eq "" -or $a -match '^(y|yes)$')
}
function Has($cmd) { return [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }
function IsAdmin {
  $id = [Security.Principal.WindowsIdentity]::GetCurrent()
  return ([Security.Principal.WindowsPrincipal]$id).IsInRole([Security.Principal.WindowsBuiltinRole]::Administrator)
}
# run a literal bash command in the distro (single-quoted at the call site => no PowerShell expansion,
# so $, &&, || pass straight through to bash). Returns the exit code.
function Wsl($bash) {
  wsl.exe -d $Distro -- bash -lc $bash
  return $LASTEXITCODE
}

Write-Host ""
Write-Host "  THOR Enterprise - installer" -ForegroundColor White
Write-Host "  governance cage for AI coding agents" -ForegroundColor DarkGray
if ($Check) { Note "(check mode: detecting only, installing nothing)" }

# ---------------------------------------------------------------- 1) winget
Step "Windows package manager (winget)"
if (Has winget) { Good "winget present ($(winget --version))" }
else { Fail "winget not found. Install 'App Installer' from the Microsoft Store, then re-run."; if (-not $Check) { exit 1 } }

# ---------------------------------------------------------------- 2) WSL2 + distro
Step "WSL2 + $Distro"
# Ground truth = can we actually RUN a command in the distro. (Avoid parsing `wsl -l -q`, whose UTF-16
# output is null-byte-laden and breaks string matching - a classic false negative.)
$distroOk = $false
if (Has wsl) { try { if ((Wsl 'true') -eq 0) { $distroOk = $true } } catch {} }
$wslOk = $distroOk
if ($distroOk) { Good "WSL2 + $Distro ready" }
else {
  Miss "WSL2/$Distro not set up"
  if (-not $Check) {
    if (Ask "Install WSL2 + $Distro now? (Windows will ask for admin permission)") {
      Note "A UAC prompt will appear for 'wsl --install'."
      Start-Process -FilePath "wsl.exe" -ArgumentList "--install","-d",$Distro -Verb RunAs -Wait
      Note "NOTE: a fresh WSL install usually needs a REBOOT. If so, reboot then re-run this installer."
    } else { Fail "WSL is required - aborting."; exit 1 }
  }
}

# ---------------------------------------------------------------- 3) Docker (usable from WSL)
Step "Docker (the engine everything runs inside)"
# What THOR needs is a docker the WSL side can use - that's Docker Desktop's WSL integration OR docker-ce
# installed directly in the distro. Check the real thing: does `docker info` work inside WSL?
$dockerInstalled = $false
if ($distroOk -and (Wsl 'docker info >/dev/null 2>&1') -eq 0) { $dockerInstalled = $true }
elseif ((Has docker) -or (Test-Path "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe")) { $dockerInstalled = $true }
if ($dockerInstalled) { Good "Docker is usable from WSL" }
else {
  Miss "Docker Desktop not installed"
  if (-not $Check) {
    if (Ask "Install Docker Desktop now via winget? (Windows will ask for admin permission)") {
      winget install --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
      Good "Docker Desktop installed"
      Note "Starting Docker Desktop - accept its terms on first launch and enable WSL integration if asked."
      $dd = "$Env:ProgramFiles\Docker\Docker\Docker Desktop.exe"
      if (Test-Path $dd) { Start-Process $dd }
      Step "Waiting for the Docker engine to come up (first launch can take a minute)"
      for ($i = 0; $i -lt 60; $i++) {
        try { docker info *> $null; if ($LASTEXITCODE -eq 0) { break } } catch {}
        Start-Sleep -Seconds 5; Write-Host "." -NoNewline
      }
      Write-Host ""
    } else { Fail "Docker is required - aborting."; exit 1 }
  }
}

# ---------------------------------------------------------------- 4) THOR into WSL
Step "THOR engine (in WSL)"
$present = $false
if ($wslOk -or $distroOk) { if ((Wsl 'test -d ~/thor-enterprise/.git') -eq 0) { $present = $true } }
if ($present) { Good "THOR present at ~/thor-enterprise (in $Distro)" }
else {
  Miss "THOR not in WSL"
  if (-not $Check) {
    if (Ask "Clone THOR into ~/thor-enterprise now?") {
      Wsl 'command -v git >/dev/null || (sudo apt-get update && sudo apt-get install -y git)' | Out-Null
      wsl.exe -d $Distro -- bash -lc "git clone $ThorRepo ~/thor-enterprise"
      if ((Wsl 'test -d ~/thor-enterprise/.git') -eq 0) { $present = $true; Good "Cloned THOR" }
    }
  }
}

# ---------------------------------------------------------------- 5) THOR self-bootstrap (images + venv)
if ($present -and -not $Check) {
  Step "THOR self-setup (builds the AI room image + engine - first run takes a few minutes)"
  # ensure python3 + node(nvm), then run the pure-code doctor which auto-builds images + the venv
  Wsl 'command -v python3 >/dev/null || (sudo apt-get update && sudo apt-get install -y python3 python3-venv)' | Out-Null
  Wsl 'export NVM_DIR=$HOME/.nvm; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; command -v node >/dev/null || (curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash && . "$NVM_DIR/nvm.sh" && nvm install --lts)' | Out-Null
  Wsl 'export NVM_DIR=$HOME/.nvm; [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"; nvm use --lts >/dev/null 2>&1; cd ~/thor-enterprise && node bin/thor.js doctor'
}

# ---------------------------------------------------------------- done
Step "Next"
if ($Check) {
  Note "Check complete. Re-run WITHOUT -Check to install anything marked [--]."
} else {
  Write-Host "  Setup done (or guided above). To govern a project:" -ForegroundColor White
  Note "wsl -d $Distro -- bash -lc 'cd ~/thor-enterprise && node bin/thor.js run ~/thor-projects/<your-repo>'"
  Write-Host "  Then open:  http://localhost:7080/   and click 'Connect Claude' to sign in once." -ForegroundColor White
}
Write-Host ""
