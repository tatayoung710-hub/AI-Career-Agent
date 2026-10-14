$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$pidFile = Join-Path $projectRoot '.local\processes.json'
if (!(Test-Path -LiteralPath $pidFile)) { Write-Output 'No saved project processes.'; exit 0 }
$saved = Get-Content -LiteralPath $pidFile -Raw | ConvertFrom-Json
if ($saved.root -ne $projectRoot) { throw 'Saved process directory does not match this project.' }
foreach ($serviceName in @('api','worker','web')) {
    $servicePid = [int]$saved.$serviceName
    $serviceProcess = Get-CimInstance Win32_Process -Filter "ProcessId=$servicePid" -ErrorAction SilentlyContinue
    if ($serviceProcess -and $serviceProcess.CommandLine -and $serviceProcess.CommandLine.Contains($projectRoot)) {
        Stop-Process -Id $servicePid
        Write-Output "Stopped $serviceName."
    } elseif ($serviceProcess) {
        Write-Output "Skipped $serviceName: process identity no longer belongs to this checkout."
    }
}
