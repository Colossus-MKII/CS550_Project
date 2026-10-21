param(
    [string]$Video = "data/pilot/videos/01_dog.mp4",
    [ValidateSet("all", "yolo", "sam2")][string]$Lesson = "all",
    [int]$Frames = 60,
    [ValidateSet("auto", "cuda", "cpu")][string]$Device = "auto",
    [switch]$PickBox,
    [switch]$NoOpen
)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
try {
    $labPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
    if (!(Test-Path -LiteralPath $labPython)) { throw "Run learning/setup.ps1 first." }
    $labArgs = @("-m", "learning.run", "--video", $Video, "--lesson", $Lesson, "--max-frames", $Frames, "--device", $Device)
    if ($PickBox) { $labArgs += "--pick-box" }
    if (!$NoOpen) { $labArgs += "--open" }
    & $labPython @labArgs
    if ($LASTEXITCODE -ne 0) { throw "Lesson failed. Read the error and the partial run's summary.json." }
} finally { Pop-Location }
