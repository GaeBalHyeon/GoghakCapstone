$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$resultPath = Join-Path $root "data\network_fix_result.txt"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $resultPath) | Out-Null

try {
$wifi = Get-NetAdapter | Where-Object { $_.InterfaceDescription -like "*Wireless*" -and $_.Status -eq "Up" } | Select-Object -First 1
$ethernet = Get-NetAdapter | Where-Object { $_.InterfaceDescription -notlike "*Wireless*" -and $_.Status -eq "Up" -and $_.HardwareInterface } | Select-Object -First 1

if (-not $wifi) { throw "Connected Wi-Fi adapter was not found." }
if (-not $ethernet) { throw "Connected Ethernet adapter was not found." }

Set-NetIPInterface -InterfaceIndex $wifi.ifIndex -AddressFamily IPv4 -AutomaticMetric Disabled -InterfaceMetric 10
Set-NetIPInterface -InterfaceIndex $ethernet.ifIndex -AddressFamily IPv4 -AutomaticMetric Disabled -InterfaceMetric 80

try {
    Set-NetConnectionProfile -InterfaceIndex $ethernet.ifIndex -NetworkCategory Private
} catch {
    # Route selection is the required change. Profile adjustment can be unavailable on unidentified networks.
}

$defaultRoutes = Get-NetRoute -AddressFamily IPv4 -DestinationPrefix "0.0.0.0/0" |
    Sort-Object { $_.RouteMetric + $_.InterfaceMetric } |
    ForEach-Object { "{0}: gateway={1}, total_metric={2}" -f $_.InterfaceAlias, $_.NextHop, ($_.RouteMetric + $_.InterfaceMetric) }

@(
    "[OK] Wi-Fi metric: 10 (Internet preferred)",
    "[OK] Ethernet metric: 80 (Jetson local LAN retained)",
    "[ROUTES]",
    $defaultRoutes
) | Set-Content -Path $resultPath -Encoding UTF8
} catch {
    @(
        "[ERROR] $($_.Exception.Message)",
        "[DETAIL] $($_.ScriptStackTrace)"
    ) | Set-Content -Path $resultPath -Encoding UTF8
    exit 1
}
