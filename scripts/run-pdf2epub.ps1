[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [Alias("InputDir")]
    [string]$InputPath = ".\samples",

    [Alias("OutputPath")]
    [string]$OutputDir = ".\output",

    [string]$TitlesFile = ".\titles.txt",

    [ValidateSet("auto", "rtl", "ltr")]
    [string]$Binding = "auto",

    [ValidateSet("auto", "pdf-text", "tesseract", "none")]
    [string]$OcrMode = "auto",

    [string]$OcrLang = "jpn+eng",

    [switch]$Recurse,

    [switch]$InspectOnly
)

$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot

function Resolve-ProjectPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue
    )

    if ([System.IO.Path]::IsPathRooted($PathValue)) {
        return $PathValue
    }

    return Join-Path $projectRoot $PathValue
}

$resolvedInputPath = Resolve-ProjectPath -PathValue $InputPath
$resolvedOutputDir = Resolve-ProjectPath -PathValue $OutputDir
$resolvedTitlesFile = Resolve-ProjectPath -PathValue $TitlesFile

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv コマンドが見つかりません。先に uv をインストールしてください。"
}

$env:PYTHONPATH = Join-Path $projectRoot "src"
$env:UV_CACHE_DIR = Join-Path $env:TEMP "pdf2epub-uv-cache"

if (-not (Test-Path -LiteralPath $resolvedInputPath)) {
    throw "入力パスが見つかりません: $resolvedInputPath"
}

if (-not (Test-Path -LiteralPath $resolvedTitlesFile)) {
    throw "タイトル候補ファイルが見つかりません: $resolvedTitlesFile"
}

if (-not $InspectOnly) {
    New-Item -ItemType Directory -Path $resolvedOutputDir -Force | Out-Null
}

function Invoke-Pdf2EpubCli {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & uv run --no-project --with pymupdf python -m pdf2epub.cli @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "pdf2epub の実行に失敗しました。"
    }
}

function Get-TargetPdfFiles {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [switch]$Recursive
    )

    $item = Get-Item -LiteralPath $Path
    if ($item.PSIsContainer) {
        $params = @{
            LiteralPath = $item.FullName
            Filter = "*.pdf"
            File = $true
        }
        if ($Recursive) {
            $params.Recurse = $true
        }
        return Get-ChildItem @params | Sort-Object FullName
    }

    if ($item.Extension -ne ".pdf") {
        throw "入力ファイルは PDF を指定してください: $($item.FullName)"
    }

    return @($item)
}

$pdfFiles = Get-TargetPdfFiles -Path $resolvedInputPath -Recursive:$Recurse
if (-not $pdfFiles -or $pdfFiles.Count -eq 0) {
    throw "PDF ファイルが見つかりませんでした。"
}

foreach ($pdfFile in $pdfFiles) {
    Write-Host "Processing: $($pdfFile.FullName)"

    if ($InspectOnly) {
        Invoke-Pdf2EpubCli -Arguments @(
            "inspect",
            $pdfFile.FullName,
            "--binding", $Binding,
            "--titles-file", $resolvedTitlesFile
        )
        continue
    }

    Invoke-Pdf2EpubCli -Arguments @(
        "convert",
        $pdfFile.FullName,
        "--output-dir", $resolvedOutputDir,
        "--titles-file", $resolvedTitlesFile,
        "--binding", $Binding,
        "--ocr-mode", $OcrMode,
        "--ocr-lang", $OcrLang
    )
}
