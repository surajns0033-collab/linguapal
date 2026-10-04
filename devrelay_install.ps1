# DevRelay installer for Windows.
#
#   iwr -useb https://devrelay.com/install.ps1 | iex
#
# Installs the gateway binary, wires it into every AI coding host it finds,
# installs the agent skills, and registers a daily update check.
#
# To pass options, download first:
#   iwr -useb https://devrelay.com/install.ps1 -OutFile install.ps1
#   .\install.ps1 -Hosts "opencode,claude-code" -NoAutoUpdate

[CmdletBinding()]
param(
    [switch]$NoAutoUpdate,
    [switch]$NoSkills,
    [switch]$NoTelemetry,
    [switch]$DetailedTelemetry,
    [switch]$NoPathUpdate,
    [string]$Hosts = "all"
)

$ErrorActionPreference = "Stop"

$BaseUrl = "https://devrelay.com"

function Write-Ok    { param($m) Write-Host "  [ok] $m" -ForegroundColor Green }
function Write-Skip  { param($m) Write-Host "  - $m" -ForegroundColor DarkGray }
function Write-Warn2 { param($m) Write-Host "  ! $m" -ForegroundColor Yellow }

$SupportedHostIds = @(
    "claude-code", "claude-desktop", "cursor", "windsurf", "continue",
    "cline", "opencode", "codex", "zed"
)
$SelectedHostIds = @()
if ($Hosts -eq "all" -or $Hosts -eq "none") {
    $HostSelection = $Hosts
} elseif ([string]::IsNullOrWhiteSpace($Hosts)) {
    throw "-Hosts requires a value (for example: -Hosts 'opencode,claude-code')"
} else {
    $HostSelection = "list"
    $SelectedHostIds = @($Hosts.Split(','))
    foreach ($HostId in $SelectedHostIds) {
        if ([string]::IsNullOrWhiteSpace($HostId) -or $SupportedHostIds -notcontains $HostId) {
            throw "Unknown host ID '$HostId'. Supported IDs: $($SupportedHostIds -join ', ')"
        }
    }
}

function Test-HostSelected {
    param([string]$Id)
    return $HostSelection -eq "all" -or ($HostSelection -eq "list" -and $SelectedHostIds -contains $Id)
}

Write-Host ""
Write-Host "=== DevRelay Agentic Gateway Installer (Windows) ===" -ForegroundColor Cyan
Write-Host ""

$ConfigDir  = Join-Path $env:USERPROFILE ".devrelay"
$InstallDir = Join-Path $ConfigDir "bin"
$EnvFile    = Join-Path $ConfigDir "env"
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null

$BinaryPath = Join-Path $InstallDir "dev_mlh_mcp_server.exe"

# ------------------------------------------------------------------ binary ---

$DownloadSuccess = $false
$BinaryUrl = "$BaseUrl/releases/latest/devrelay-windows-x86_64.exe"

try {
    Write-Host "-> Downloading $BinaryUrl" -ForegroundColor Cyan
    Invoke-WebRequest -Uri $BinaryUrl -OutFile "$BinaryPath.tmp" -UseBasicParsing
    # A host that serves index.html for unknown paths would otherwise leave us
    # with an "executable" full of HTML.
    $head = [System.IO.File]::ReadAllBytes("$BinaryPath.tmp")
    if ($head.Length -gt 2 -and $head[0] -eq 0x4D -and $head[1] -eq 0x5A) {
        Move-Item -Path "$BinaryPath.tmp" -Destination $BinaryPath -Force
        $DownloadSuccess = $true
        Write-Ok "Downloaded release binary"
    } else {
        Remove-Item "$BinaryPath.tmp" -Force -ErrorAction SilentlyContinue
        Write-Warn2 "Release URL did not return a Windows executable."
    }
} catch {
    Write-Warn2 "Release download failed: $($_.Exception.Message)"
}

if (-not $DownloadSuccess) {
    foreach ($candidate in @(".\target\release\dev_mlh_mcp_server.exe", ".\target\debug\dev_mlh_mcp_server.exe")) {
        if (Test-Path $candidate) {
            Copy-Item $candidate $BinaryPath -Force
            $DownloadSuccess = $true
            Write-Ok "Using local build $candidate"
            break
        }
    }
}

if (-not $DownloadSuccess -and (Get-Command cargo -ErrorAction SilentlyContinue) -and (Test-Path ".\Cargo.toml")) {
    Write-Host "-> Building from source (this takes a few minutes)..." -ForegroundColor Cyan
    cargo build --release --bin dev_mlh_mcp_server | Out-Null
    if (Test-Path ".\target\release\dev_mlh_mcp_server.exe") {
        Copy-Item ".\target\release\dev_mlh_mcp_server.exe" $BinaryPath -Force
        $DownloadSuccess = $true
        Write-Ok "Built from source"
    }
}

if (-not $DownloadSuccess) {
    # Installing a stub that only prints a message is worse than failing: the
    # AI host would report a healthy MCP server that answers nothing.
    throw "Could not obtain a gateway binary. Tried $BinaryUrl. Install Rust and re-run from a checkout to build from source."
}

Unblock-File -Path $BinaryPath -ErrorAction SilentlyContinue

# Forward to the binary that OTA replaces, without requiring symlink privileges.
# cmd.exe requires a BOM-free script; ASCII works in PowerShell 5.1 and 7.
$CommandPath = Join-Path $InstallDir "devrelay.cmd"
Set-Content -Path $CommandPath -Value '@"%~dp0dev_mlh_mcp_server.exe" %*' -Encoding Ascii

$InstalledVersion = (& $BinaryPath --version 2>$null)
Write-Host "   $InstalledVersion" -ForegroundColor DarkGray

# ------------------------------------------------------------ credentials ---

function Set-EnvFileVar {
    param([string]$Name, [string]$Value)
    if ([string]::IsNullOrWhiteSpace($Value)) { return }
    $lines = @()
    if (Test-Path $EnvFile) {
        $lines = Get-Content $EnvFile | Where-Object { $_ -notmatch "^\s*(export\s+)?$Name=" }
    }
    $lines += "$Name=$Value"
    Set-Content -Path $EnvFile -Value $lines -Encoding UTF8
}

function Remove-EnvFileVar {
    param([string]$Name)
    if (-not (Test-Path $EnvFile)) { return }
    $lines = @(Get-Content $EnvFile | Where-Object { $_ -notmatch "^\s*(export\s+)?$Name=" })
    Set-Content -Path $EnvFile -Value $lines -Encoding UTF8
}

function Get-EnvFileVar {
    param([string]$Name)
    if (-not (Test-Path $EnvFile)) { return "" }
    $match = Get-Content $EnvFile | Where-Object { $_ -match "^\s*(export\s+)?$Name=" } | Select-Object -Last 1
    if ($match) { return ($match -replace "^\s*(export\s+)?$Name=", "").Trim('"', "'") }
    return ""
}

Write-Host ""
Write-Skip "Finish setup with:  devrelay login   (opens your browser for the Core sign-in)"

# Basic telemetry is on unless opted out; with neither switch a reinstall keeps
# the user's existing choice. The opt-out goes in the env file because every
# release honors it, including ones that predate `devrelay telemetry`.
if ($NoTelemetry) {
    Set-EnvFileVar "DEVRELAY_TELEMETRY_DISABLED" "1"
    Write-Ok "Telemetry disabled"
} elseif ($DetailedTelemetry) {
    $DetailedTelemetryOn = $false
    try {
        & $BinaryPath telemetry detailed *> $null
        $DetailedTelemetryOn = ($LASTEXITCODE -eq 0)
    } catch {
        $DetailedTelemetryOn = $false
    }
    if ($DetailedTelemetryOn) {
        Remove-EnvFileVar "DEVRELAY_TELEMETRY_DISABLED"
        Write-Ok "Detailed telemetry on  (change with: devrelay telemetry on|off)"
    } else {
        Write-Warn2 "This release cannot turn on detailed telemetry; run devrelay telemetry detailed after it updates."
    }
}

# ----------------------------------------------------------------- clients ---

Write-Host ""
Write-Host "-> Configuring AI coding hosts..." -ForegroundColor Cyan

function Set-McpConfig {
    param(
        [string]$Id,
        [string]$Label,
        [string]$Path,
        [string]$Trigger,
        [string]$Key = "mcpServers",
        [string]$Format = "standard"
    )

    if (-not (Test-HostSelected $Id)) {
        Write-Skip "$Label`: not selected"
        return $false
    }

    if (-not (Test-Path $Path) -and -not (Test-Path $Trigger)) {
        Write-Skip "$Label`: not detected"
        return $false
    }

    try {
        $config = [ordered]@{}
        if (Test-Path $Path) {
            $raw = (Get-Content -Path $Path -Raw)
            if ($raw -and $raw.Trim()) {
                # Throws on malformed JSON, which sends us to the catch below
                # rather than overwriting the user's config with a fresh object.
                $parsed = ConvertFrom-Json $raw -ErrorAction Stop
                $config = [ordered]@{}
                foreach ($p in $parsed.PSObject.Properties) { $config[$p.Name] = $p.Value }
            }
            Copy-Item $Path "$Path.devrelay.bak" -Force
        }

        $servers = [ordered]@{}
        if ($config[$Key]) {
            foreach ($p in $config[$Key].PSObject.Properties) { $servers[$p.Name] = $p.Value }
        }
        if ($Format -eq "opencode") {
            $servers["devrelay-gateway"] = @{
                type = "local"
                command = @($BinaryPath, "--stdio")
                enabled = $true
            }
        } else {
            $servers["devrelay-gateway"] = @{ command = $BinaryPath; args = @("--stdio") }
        }
        $config[$Key] = $servers

        $dir = Split-Path -Parent $Path
        if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        ConvertTo-Json $config -Depth 20 | Set-Content -Path $Path -Encoding UTF8
        Write-Ok "$Label ($Path)"
        return $true
    } catch {
        Write-Warn2 "$Label`: config is not valid JSON or could not be written; left untouched."
        return $false
    }
}

function Set-OpenCodeMcpConfig {
    if (-not (Test-HostSelected "opencode")) {
        Write-Skip "OpenCode: not selected"
        return $false
    }

    $configDir = Join-Path $env:USERPROFILE ".config\opencode"
    if ($env:XDG_CONFIG_HOME) {
        $configDir = Join-Path $env:XDG_CONFIG_HOME "opencode"
    }
    $jsonPath = Join-Path $configDir "opencode.json"
    $jsoncPath = Join-Path $configDir "opencode.jsonc"
    $stable = Get-Command opencode -ErrorAction SilentlyContinue
    $beta = Get-Command opencode2 -ErrorAction SilentlyContinue

    if (-not (Test-Path $configDir) -and -not $stable -and -not $beta) {
        Write-Skip "OpenCode: not detected"
        return $false
    }

    # OpenCode merges both files with JSONC taking precedence, while its MCP
    # command currently edits JSON first. Refuse to claim success when we cannot
    # safely know which effective entry the user intends.
    if ((Test-Path $jsonPath) -and (Test-Path $jsoncPath)) {
        Write-Warn2 "OpenCode: both $jsonPath and $jsoncPath exist."
        Write-Warn2 "Consolidate them or update the higher-precedence JSONC file manually."
        return $false
    }

    if ($stable) {
        try {
            & $stable.Source mcp add devrelay-gateway -- $BinaryPath --stdio *> $null
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "OpenCode (opencode mcp add)"
                return $true
            }
        } catch {
            Write-Skip "OpenCode (opencode mcp add): $($_.Exception.Message)"
        }
    }

    if ($beta) {
        try {
            & $beta.Source mcp add devrelay-gateway --global -- $BinaryPath --stdio *> $null
            if ($LASTEXITCODE -eq 0) {
                Write-Ok "OpenCode 2 (opencode2 mcp add --global)"
                return $true
            }
        } catch {
            Write-Skip "OpenCode 2 (opencode2 mcp add --global): $($_.Exception.Message)"
        }
    }

    if (Test-Path $jsoncPath) {
        Write-Warn2 "OpenCode CLI unavailable; cannot safely edit commented file $jsoncPath."
        Write-Warn2 "Add the DevRelay MCP entry manually."
        return $false
    }

    try {
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    } catch {
        Write-Warn2 "OpenCode: could not create $configDir"
        return $false
    }
    return (Set-McpConfig -Id "opencode" -Label "OpenCode" `
        -Path $jsonPath -Trigger $configDir -Key "mcp" -Format "opencode")
}

function Set-CodexMcpConfig {
    # Codex reads MCP servers only from TOML tables in ~/.codex/config.toml.
    # Replace our one table as text so the rest of the file stays intact
    # without needing a TOML parser.
    if (-not (Test-HostSelected "codex")) {
        Write-Skip "Codex: not selected"
        return $false
    }

    $codexDir = Join-Path $env:USERPROFILE ".codex"
    $path = Join-Path $codexDir "config.toml"
    if (-not (Test-Path $codexDir) -and -not (Test-Path $path)) {
        Write-Skip "Codex: not detected"
        return $false
    }

    try {
        $kept = @()
        if (Test-Path $path) {
            $skipping = $false
            foreach ($line in [System.IO.File]::ReadAllLines($path)) {
                if ($line -match '^\s*\[') {
                    $skipping = $line -match '^\s*\[mcp_servers\.devrelay-gateway\]\s*(#.*)?$'
                }
                if (-not $skipping) { $kept += $line }
            }
            Copy-Item $path "$path.devrelay.bak" -Force
        }

        # Trailing blanks are dropped so they never pile up across re-runs.
        $end = $kept.Count
        while ($end -gt 0 -and [string]::IsNullOrWhiteSpace($kept[$end - 1])) { $end-- }
        $lines = @()
        if ($end -gt 0) { $lines = @($kept[0..($end - 1)]) + "" }

        $tomlBinary = $BinaryPath.Replace('\', '\\').Replace('"', '\"')
        $lines += "[mcp_servers.devrelay-gateway]"
        $lines += "command = `"$tomlBinary`""
        $lines += 'args = ["--stdio"]'

        # WriteAllLines writes UTF-8 without a BOM, which TOML parsers expect.
        [System.IO.File]::WriteAllLines($path, [string[]]$lines)
        Write-Ok "Codex ($path)"
        return $true
    } catch {
        Write-Warn2 "Codex: could not write $path; left untouched."
        return $false
    }
}

$configured = 0
# Claude Code keeps user-scoped MCP servers in %USERPROFILE%\.claude.json.
if (Set-McpConfig -Id "claude-code" -Label "Claude Code" `
    -Path (Join-Path $env:USERPROFILE ".claude.json") `
    -Trigger (Join-Path $env:USERPROFILE ".claude")) { $configured++ }
if (Set-McpConfig -Id "claude-desktop" -Label "Claude Desktop" `
    -Path (Join-Path $env:APPDATA "Claude\claude_desktop_config.json") `
    -Trigger (Join-Path $env:APPDATA "Claude")) { $configured++ }
if (Set-McpConfig -Id "cursor" -Label "Cursor" `
    -Path (Join-Path $env:USERPROFILE ".cursor\mcp.json") `
    -Trigger (Join-Path $env:USERPROFILE ".cursor")) { $configured++ }
if (Set-McpConfig -Id "windsurf" -Label "Windsurf" `
    -Path (Join-Path $env:USERPROFILE ".codeium\windsurf\mcp_config.json") `
    -Trigger (Join-Path $env:USERPROFILE ".codeium\windsurf")) { $configured++ }
if (Set-McpConfig -Id "continue" -Label "Continue" `
    -Path (Join-Path $env:USERPROFILE ".continue\config.json") `
    -Trigger (Join-Path $env:USERPROFILE ".continue")) { $configured++ }
if (Set-OpenCodeMcpConfig)                                                                                                                           { $configured++ }
if (Set-CodexMcpConfig)                                                                                                                              { $configured++ }
if (Set-McpConfig -Id "cline" -Label "VS Code (Cline)" `
    -Path (Join-Path $env:APPDATA "Code\User\globalStorage\saoudrizwan.claude-dev\settings\cline_mcp_settings.json") `
    -Trigger (Join-Path $env:APPDATA "Code\User\globalStorage\saoudrizwan.claude-dev")) { $configured++ }
if (Set-McpConfig -Id "zed" -Label "Zed" `
    -Path (Join-Path $env:APPDATA "Zed\settings.json") `
    -Trigger (Join-Path $env:APPDATA "Zed") -Key "context_servers") { $configured++ }

if ($configured -eq 0) {
    if ($HostSelection -eq "none") {
        Write-Skip "AI host configuration skipped (-Hosts none)."
    } else {
        Write-Warn2 "No selected AI hosts were configured. Register $BinaryPath --stdio manually."
    }
}

# ------------------------------------------------------------------ skills ---

if (-not $NoSkills) {
    Write-Host ""
    Write-Host "-> Installing agent skills..." -ForegroundColor Cyan
    try {
        $env:DEVRELAY_BASE_URL = $BaseUrl
        & $BinaryPath --sync-skills
    } catch {
        Write-Warn2 "Could not reach $BaseUrl/v1/skills.json. Retry with: $BinaryPath --sync-skills"
    }
}

# ------------------------------------------------------ background updates ---

if (-not $NoAutoUpdate) {
    Write-Host ""
    Write-Host "-> Scheduling background updates..." -ForegroundColor Cyan

    $UpdateScript = Join-Path $InstallDir "devrelay-update.ps1"
    @"
# Periodic DevRelay refresh. Installed by install.ps1; safe to delete.
`$env:DEVRELAY_BASE_URL = "$BaseUrl"
`$log = "$ConfigDir\update.log"
"--- `$(Get-Date) ---" | Out-File -Append `$log
& "$BinaryPath" --self-update *>> `$log
& "$BinaryPath" --sync-skills *>> `$log
"@ | Set-Content -Path $UpdateScript -Encoding UTF8

    try {
        $action  = New-ScheduledTaskAction -Execute "powershell.exe" `
                       -Argument "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$UpdateScript`""
        $trigger = New-ScheduledTaskTrigger -Daily -At 4am
        $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
                       -AllowStartIfOnBatteries -AllowHardTerminate
        Register-ScheduledTask -TaskName "DevRelayUpdate" -Action $action -Trigger $trigger `
            -Settings $settings -Description "Daily DevRelay gateway and skill refresh" -Force | Out-Null
        Write-Ok "Scheduled daily update check (Task Scheduler: DevRelayUpdate)"
    } catch {
        Write-Warn2 "Could not register the scheduled task: $($_.Exception.Message)"
        Write-Warn2 "Run $UpdateScript manually to update."
    }
} else {
    Write-Skip "Background updates skipped (-NoAutoUpdate)."
}

# -------------------------------------------------------------------- PATH ---

if (-not $NoPathUpdate) {
    $UserPath = [Environment]::GetEnvironmentVariable("PATH", "User")
    if ($UserPath -notlike "*$InstallDir*") {
        [Environment]::SetEnvironmentVariable("PATH", "$UserPath;$InstallDir", "User")
        Write-Ok "Added $InstallDir to your PATH"
    }
} else {
    Write-Skip "PATH update skipped (-NoPathUpdate)."
}

# ----------------------------------------------------------------- summary ---

Write-Host ""
Write-Host "DevRelay is installed." -ForegroundColor Green
Write-Host "Command: devrelay ($CommandPath)" -ForegroundColor DarkGray
Write-Host ""
& $BinaryPath --doctor
Write-Host ""
Write-Host "Restart your AI host so it picks up the new MCP server." -ForegroundColor DarkGray
Write-Host ""
