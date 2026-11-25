param(
    [Parameter(Mandatory)][string]$ServerPython,
    [Parameter(Mandatory)][string]$DevicePython,
    [Parameter(Mandatory)][string]$DataFolder,
    [Parameter(Mandatory)][string]$Library,
    [string]$ListenAddress,
    [string]$DeviceId
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$serverExe = (Resolve-Path -LiteralPath $ServerPython).Path
$deviceExe = (Resolve-Path -LiteralPath $DevicePython).Path
$nativeLibrary = (Resolve-Path -LiteralPath $Library).Path
$folder = [IO.Directory]::CreateDirectory($DataFolder).FullName
$marker = Join-Path $folder 'current-kit.json'
if (!$ListenAddress) {
    $nic = Get-NetIPConfiguration | Where-Object {
        $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' -and $_.IPv4Address
    } | Sort-Object { $_.NetIPv4Interface.InterfaceMetric } | Select-Object -First 1
    if (!$nic) { throw 'Connect the laptop and iPhone to the same Wi-Fi.' }
    $ListenAddress = @($nic.IPv4Address)[0].IPAddress
}

function Get-BetaListeners {
    @(Get-NetTCPConnection -LocalAddress $ListenAddress -LocalPort 30133,30443 -State Listen -ErrorAction SilentlyContinue)
}

$listeners = @(Get-BetaListeners)
if (!$listeners.Count) {
    $previous = if (Test-Path -LiteralPath $marker) { Get-Content -Raw -LiteralPath $marker }
    $entry = Join-Path $PSScriptRoot 'rp_laptop.py'
    $argsLine = ('"{0}" --folder "{1}" start --ip "{2}" --library "{3}"' -f $entry, $folder, $ListenAddress, $nativeLibrary)
    $log = Join-Path $folder ('server-' + [guid]::NewGuid().ToString('N'))
    $service = Start-Process -FilePath $serverExe -ArgumentList $argsLine -WindowStyle Hidden -PassThru -RedirectStandardOutput "$log.out" -RedirectStandardError "$log.err"
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        if ($service.HasExited) { throw "Server exited. See $log.err" }
        if ((Test-Path -LiteralPath $marker) -and (Get-Content -Raw -LiteralPath $marker) -ne $previous) {
            $ready = $true
            break
        }
        Start-Sleep -Milliseconds 250
    }
    if (!$ready) { throw "Server startup timed out. See $log.err" }
    $listeners = @(Get-BetaListeners)
}
if ($listeners.Count -ne 2 -or @($listeners.OwningProcess | Select-Object -Unique).Count -ne 1) {
    throw 'The RP and login ports must both be served by the same laptop server.'
}
$kitName = Get-Content -Raw -LiteralPath $marker | ConvertFrom-Json
if ($kitName -notmatch '^kit-[0-9a-f]{16}$') { throw 'Invalid laptop kit marker.' }
$kit = Join-Path $folder $kitName
$profile = Get-Content -Raw -LiteralPath (Join-Path $kit 'officer-iPhone-PRIVATE.json') | ConvertFrom-Json
if ($profile.host -ne $ListenAddress -or $profile.port -ne 30133) { throw 'The current profile belongs to a different server.' }
$installArgs = @((Join-Path $PSScriptRoot 'install_paired_rp_profiles.py'), '--kit', $kit)
if ($DeviceId) { $installArgs += @('--device', $DeviceId) }
& $deviceExe @installArgs
if ($LASTEXITCODE -ne 0) { throw 'Unlock the iPhone and try again. The laptop server is running.' }
$expires = [DateTimeOffset]::FromUnixTimeSeconds($profile.expires).ToLocalTime().ToString('HH:mm')
Write-Output "Server ready at $ListenAddress until $expires. Reopen both GTA apps and select RP rieng."
