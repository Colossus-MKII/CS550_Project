param([Parameter(ValueFromRemainingArguments = $true)][string[]]$ExperimentArgs)
$ErrorActionPreference = 'Stop'
$experimentRoot = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $experimentRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = Join-Path (Split-Path -Parent $experimentRoot) '.venv\Scripts\python.exe'
}
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Create a local Python environment and install this experiment package first.'
}
Push-Location -LiteralPath $experimentRoot
try {
    & $pythonExe -m tracking_lab.run @ExperimentArgs
    if ($LASTEXITCODE -ne 0) { throw "Experiment exited with code $LASTEXITCODE" }
} finally {
    Pop-Location
}
