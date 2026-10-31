param([switch]$PathOnly)
$ErrorActionPreference = 'Stop'
$reportsRoot = Join-Path $PSScriptRoot 'artifacts\optics'
$reports = @(Get-ChildItem -LiteralPath $reportsRoot -Directory | ForEach-Object {
    $report = Join-Path $_.FullName 'index.html'
    if (Test-Path -LiteralPath $report) { Get-Item -LiteralPath $report }
})
$latest = $reports | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $latest) { throw 'No report found. Run simulate-optics.ps1 first.' }
if ($PathOnly) { $latest.FullName } else { Invoke-Item -LiteralPath $latest.FullName }
