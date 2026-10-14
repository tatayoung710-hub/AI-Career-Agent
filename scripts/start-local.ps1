param([int]$ApiPort = 8000, [int]$WebPort = 5173)
$ErrorActionPreference = 'Stop'
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$localPython = Join-Path $projectRoot '.venv\Scripts\python.exe'
$viteScript = Join-Path $projectRoot 'frontend\node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $localPython) -or !(Test-Path -LiteralPath $viteScript)) {
    throw 'Install backend and frontend dependencies using README.md before starting.'
}
$localNode = (Get-Command node -ErrorAction Stop).Source
$env:VITE_PROXY_TARGET = "http://127.0.0.1:$ApiPort"
$env:CORS_ORIGINS = (@("http://localhost:$WebPort", "http://127.0.0.1:$WebPort") | ConvertTo-Json -Compress)
$runDirectory = Join-Path $projectRoot '.local'
New-Item -ItemType Directory -Path $runDirectory -Force | Out-Null
foreach ($servicePort in @($ApiPort, $WebPort)) {
    if (Get-NetTCPConnection -LocalPort $servicePort -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $servicePort is already in use. Choose another port or stop the existing project process."
    }
}
& $localPython (Join-Path $PSScriptRoot 'configure.py')
Push-Location (Join-Path $projectRoot 'backend')
try {
    & $localPython -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw 'Database migration failed.' }
} finally { Pop-Location }
$apiProcess = Start-Process -FilePath $localPython -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDirectory 'api.log') -RedirectStandardError (Join-Path $runDirectory 'api-error.log')
$workerProcess = Start-Process -FilePath $localPython -ArgumentList @('-m','app.worker') -WorkingDirectory (Join-Path $projectRoot 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDirectory 'worker.log') -RedirectStandardError (Join-Path $runDirectory 'worker-error.log')
$webProcess = Start-Process -FilePath $localNode -ArgumentList @(('"' + $viteScript + '"'),'--host','127.0.0.1','--port',"$WebPort",'--strictPort') -WorkingDirectory (Join-Path $projectRoot 'frontend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runDirectory 'web.log') -RedirectStandardError (Join-Path $runDirectory 'web-error.log')
@{ api = $apiProcess.Id; worker = $workerProcess.Id; web = $webProcess.Id; root = $projectRoot } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runDirectory 'processes.json') -Encoding utf8
Write-Output "Started local services. Open http://127.0.0.1:$WebPort and check .local logs if a service cannot start."
