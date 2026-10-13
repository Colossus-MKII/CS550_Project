[CmdletBinding()]
param(
    [switch]$Models,
    [switch]$Videos,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

if (-not $Models -and -not $Videos) {
    $Models = $true
    $Videos = $true
}

function Get-Resource {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $parent = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Force -Path $parent | Out-Null

    if ((Test-Path -LiteralPath $Destination) -and -not $Force) {
        Write-Host "Already present: $Destination"
    }
    else {
        $partial = "$Destination.part"
        if ($Force -and (Test-Path -LiteralPath $partial)) {
            Remove-Item -LiteralPath $partial -Force
        }
        Write-Host "Downloading: $Url"
        & curl.exe -L --fail --retry 3 --retry-delay 2 --continue-at - -o $partial $Url
        if ($LASTEXITCODE -ne 0) {
            throw "Download failed: $Url"
        }
        Move-Item -LiteralPath $partial -Destination $Destination -Force
    }

    $file = Get-Item -LiteralPath $Destination
    $hash = Get-FileHash -Algorithm SHA256 -LiteralPath $Destination
    $relativePath = $file.FullName.Substring($repoRoot.Length).TrimStart('\', '/').Replace('\', '/')
    [PSCustomObject]@{
        File = $relativePath
        Bytes = $file.Length
        SHA256 = $hash.Hash.ToLowerInvariant()
        Source = $Url
    }
}

$results = @()

if ($Models) {
    $checkpointDir = Join-Path $repoRoot 'models/checkpoints'
    $results += Get-Resource `
        -Url 'https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11s-seg.pt' `
        -Destination (Join-Path $checkpointDir 'yolo11s-seg.pt')
    $results += Get-Resource `
        -Url 'https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_tiny.pt' `
        -Destination (Join-Path $checkpointDir 'sam2.1_hiera_tiny.pt')
    $results += Get-Resource `
        -Url 'https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt' `
        -Destination (Join-Path $checkpointDir 'sam2.1_hiera_small.pt')
    $results += Get-Resource `
        -Url 'https://drive.usercontent.google.com/download?id=1BHxsonnvJXylqHlZ1zJHHc-ymKyq-CFf&export=download&confirm=t' `
        -Destination (Join-Path $checkpointDir 'DeAOTB_PRE_YTB_DAV.pth')
}

if ($Videos) {
    $videoDir = Join-Path $repoRoot 'data/pilot/videos'
    $galleryBase = 'https://raw.githubusercontent.com/facebookresearch/sam2/main/demo/data/gallery'
    foreach ($name in @(
        '01_dog.mp4',
        '02_cups.mp4',
        '03_blocks.mp4',
        '04_coffee.mp4',
        '05_default_juggle.mp4'
    )) {
        $results += Get-Resource `
            -Url "$galleryBase/$name" `
            -Destination (Join-Path $videoDir $name)
    }
}

$manifestPath = Join-Path $repoRoot 'resources/downloaded-resources.json'
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $manifestPath) | Out-Null
$results | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifestPath -Encoding utf8

Write-Host "`nPrepared $($results.Count) resources."
Write-Host "Manifest: $manifestPath"
$results | Format-Table File, Bytes, SHA256 -AutoSize
