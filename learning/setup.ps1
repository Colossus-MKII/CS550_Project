param([string]$Python = "python", [switch]$CpuOnly)
$ErrorActionPreference = "Stop"
$repoRoot = Split-Path $PSScriptRoot -Parent
Push-Location $repoRoot
$previousSamBuild = $env:SAM2_BUILD_CUDA
try {
    if (!(Test-Path -LiteralPath ".venv/Scripts/python.exe")) {
        & $Python -c "import sys; assert (3,10) <= sys.version_info[:2] <= (3,12), 'Use Python 3.10-3.12 for these pinned lessons'"
        if ($LASTEXITCODE -ne 0) { throw "A compatible Python executable is required." }
        & $Python -m venv .venv
        if ($LASTEXITCODE -ne 0) { throw "Virtual environment creation failed." }
    }
    $labPython = Join-Path $repoRoot ".venv/Scripts/python.exe"
    $torchIndex = if ($CpuOnly) { "https://download.pytorch.org/whl/cpu" } else { "https://download.pytorch.org/whl/cu128" }
    & $labPython -m pip install torch==2.7.1 torchvision==0.22.1 --index-url $torchIndex
    if ($LASTEXITCODE -ne 0) { throw "PyTorch installation failed." }
    & $labPython -m pip install -r learning/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "Lesson dependency installation failed." }
    # No custom CUDA compiler needed. Hole/sprinkle cleanup is deliberately disabled.
    $env:SAM2_BUILD_CUDA = "0"
    & $labPython -m pip install --no-build-isolation --no-deps "https://github.com/facebookresearch/sam2/archive/2b90b9f5ceec907a1c18123530e92e794ad901a4.zip"
    if ($LASTEXITCODE -ne 0) { throw "SAM 2 installation failed; see learning/README.md." }
    & $labPython -m pip check
    if ($LASTEXITCODE -ne 0) { throw "Dependency check failed." }
    & $labPython -m learning.run --check
    if ($LASTEXITCODE -ne 0) { throw "Environment check failed." }
} finally {
    $env:SAM2_BUILD_CUDA = $previousSamBuild
    Pop-Location
}
