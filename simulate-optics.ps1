# Optional local helper for the Python package and its scientific tests.
param([string]$Python, [string]$Output, [switch]$Test)
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
if (-not $Python) {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $Python = $bundled }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
if ($Test) {
    & $Python -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p 'test_*.py' -v
} else {
    $arguments = @((Join-Path $PSScriptRoot 'simulate.py'))
    if ($Output) { $arguments += @('--output', $Output) }
    & $Python @arguments
}
if ($LASTEXITCODE -ne 0) { throw "RK4 calculation/checks failed (exit $LASTEXITCODE). See diagnostic output." }
