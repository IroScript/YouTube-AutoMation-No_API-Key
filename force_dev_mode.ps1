# Force-enable Developer Mode in the target Chrome profile by editing
# Preferences.json. All output is mirrored to %TEMP%\fdm.log so the
# caller can read it via filesystem tools (some shells swallow PS stderr).

param(
    [Parameter(Position=0)]
    [string]$ProfileName = "Profile 6"
)

$logPath = Join-Path $env:TEMP "fdm.log"
function Log($msg, $color = "White") {
    Write-Host $msg -ForegroundColor $color
    Add-Content -Path $logPath -Value $msg
}

# Clear log
Set-Content -Path $logPath -Value ""

Log "[$(Get-Date -Format 'HH:mm:ss')] force_dev_mode.ps1 starting for profile: $ProfileName"

$userData = Join-Path $env:LOCALAPPDATA "Google\Chrome\User Data"
$profPath = Join-Path $userData $ProfileName
$prefsPath = Join-Path $profPath "Preferences"
Log "  prefsPath = $prefsPath"

if (-not (Test-Path $prefsPath)) {
    Log "  [ERROR] Preferences.json not found" "Red"
    exit 1
}

try {
    $raw = Get-Content $prefsPath -Raw
    Log ("  File size: {0} bytes" -f $raw.Length)
} catch {
    Log "  [ERROR] Cannot read Preferences.json: $($_.Exception.Message)" "Red"
    exit 1
}

try {
    $prefs = $raw | ConvertFrom-Json
    Log "  Parsed JSON OK" "Green"
} catch {
    Log "  [ERROR] Preferences.json is invalid JSON: $($_.Exception.Message)" "Red"
    exit 1
}

if (-not $prefs.extensions) {
    Log "  extensions block: missing, will create"
    $prefs | Add-Member -NotePropertyName "extensions" -NotePropertyValue ([PSCustomObject]@{}) -Force
} else {
    Log "  extensions block: present"
}

if (-not $prefs.extensions.ui) {
    Log "  extensions.ui block: missing, will create"
    $prefs.extensions | Add-Member -NotePropertyName "ui" -NotePropertyValue ([PSCustomObject]@{}) -Force
} else {
    Log "  extensions.ui block: present"
}

# Read current state without triggering strict-property error on PS5.1.
$uiHasDevMode = $prefs.extensions.ui.PSObject.Properties.Match('developer_mode').Count -gt 0
$current = if ($uiHasDevMode) { $prefs.extensions.ui.developer_mode } else { $null }
if ($null -eq $current) { $currentStr = "(null)" } else { $currentStr = $current.ToString() }
Log ("  current developer_mode = {0}" -f $currentStr)

if ($current -eq $true) {
    Log "  Already true, nothing to do." "Green"
    exit 0
}

if ($uiHasDevMode) {
    # Property exists but isn't true — set it directly.
    $prefs.extensions.ui.developer_mode = $true
} else {
    # Property doesn't exist — add it.
    $prefs.extensions.ui | Add-Member -NotePropertyName "developer_mode" -NotePropertyValue $true -Force
}
Log "  Set developer_mode = true"

$backup = "$prefsPath.flowboard.bak"
Copy-Item $prefsPath $backup -Force
Log "  Backup written: $backup"

$newRaw = $prefs | ConvertTo-Json -Depth 100
Log ("  Re-serialized: {0} bytes" -f $newRaw.Length)

Set-Content -Path $prefsPath -Value $newRaw -Encoding UTF8 -NoNewline
Log "  Preferences.json updated"

try {
    $null = Get-Content $prefsPath -Raw | ConvertFrom-Json
    Log "  Validate: JSON parse OK" "Green"
    Remove-Item $backup -Force
    Log "  Backup removed"
} catch {
    Log "  [ERROR] Re-serialized JSON invalid: $($_.Exception.Message)" "Red"
    Log "  Restoring backup..."
    Copy-Item $backup $prefsPath -Force
    exit 1
}

Log "[done]" "Green"
exit 0