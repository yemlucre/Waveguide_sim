param([string]$Python, [string]$Config, [string]$Output, [switch]$Test, [switch]$OpenReport, [ValidateSet('coupler','lamp','bpm','python')][string]$Scenario = 'coupler')
$ErrorActionPreference = 'Stop'
$env:PYTHONIOENCODING = 'utf-8'
if (-not $Python) {
    $bundled = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path -LiteralPath $bundled) { $Python = $bundled }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
& $Python -c 'import numpy; from PIL import Image'
if ($LASTEXITCODE -ne 0) { throw 'Python needs NumPy and Pillow. Install src/Agamemnon.Optics/requirements.txt into your Python environment, or pass -Python.' }
if ($Test) {
    & $Python -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -p 'test_optics*.py' -v
} else {
    if (-not $Output) { $Output = Join-Path $PSScriptRoot ('artifacts\optics\' + (Get-Date -Format 'yyyyMMdd-HHmmss-ffff')) }
    $entryPoint = if ($Scenario -in @('bpm','python')) { 'src\Agamemnon.Optics\run_bpm.py' } elseif ($Scenario -eq 'lamp') { 'src\Agamemnon.Optics\run_lamp.py' } else { 'src\Agamemnon.Optics\run.py' }
    $arguments = @((Join-Path $PSScriptRoot $entryPoint))
    if ($Scenario -eq 'python') {
        $sceneFile = if ($Config) { $Config } else { Join-Path $PSScriptRoot 'src\Agamemnon.Optics\scene_example.py' }
        $arguments += @('--scene', $sceneFile)
    } elseif ($Config) { $arguments += @('--config', $Config) }
    if ($Output) { $arguments += @('--output', $Output) }
    & $Python @arguments
}
if ($LASTEXITCODE -ne 0) { throw "Optical calculation/checks did not pass (exit $LASTEXITCODE). See structured result and diagnostic output." }

if ($OpenReport -and -not $Test) { Invoke-Item -LiteralPath (Join-Path $Output 'index.html') }


