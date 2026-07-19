$ErrorActionPreference = "Stop"

$HarnessRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BundledPython = Join-Path $HarnessRoot "runtime/python/windows-x64/python.exe"
$env:CRACKSTACK_ROOT = $HarnessRoot
$env:PYTHONPATH = "$HarnessRoot;$HarnessRoot/runtime/site-packages/windows-x64"
$env:PATH = "$HarnessRoot/runtime/python/windows-x64;$HarnessRoot/runtime/python/windows-x64/Scripts;$env:PATH"

if (Test-Path -LiteralPath $BundledPython) {
    & $BundledPython -m harness.cli @args
    exit $LASTEXITCODE
}

Write-Host "Bundled Windows x64 Python was not found at:"
Write-Host "  $BundledPython"
Write-Host "Falling back to host Python for development only."
py -3 -m harness.cli @args
exit $LASTEXITCODE
