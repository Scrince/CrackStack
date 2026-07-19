param(
    [int]$GpuLayers = 24
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Python = Join-Path $Root "runtime/python/windows-x64/python.exe"
$Config = Join-Path $Root "config.toml"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Bundled Python was not found at $Python"
}

Write-Host "Installing Vulkan-enabled llama-cpp-python wheel..."
& $Python -m pip install --upgrade --force-reinstall --no-cache-dir llama-cpp-python `
    --only-binary=:all: `
    --index-url https://pypi.org/simple `
    --extra-index-url "https://abetlen.github.io/llama-cpp-python/whl/vulkan"

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "Verifying llama.cpp GPU offload support..."
$verify = @'
from llama_cpp import llama_cpp as lib
print(bool(lib.llama_supports_gpu_offload()))
'@
$supportsGpu = & $Python -c $verify
if ($supportsGpu -ne "True") {
    throw "Installed llama-cpp-python still reports no GPU offload support."
}

if (Test-Path -LiteralPath $Config) {
    $text = Get-Content -Raw -LiteralPath $Config
    if ($text -match '(?m)^gpu_layers\s*=') {
        $text = $text -replace '(?m)^gpu_layers\s*=.*$', "gpu_layers = $GpuLayers"
    } else {
        $text = $text -replace '(?m)^\[model\]\s*$', "[model]`ngpu_layers = $GpuLayers"
    }
    [System.IO.File]::WriteAllText($Config, $text, [System.Text.UTF8Encoding]::new($false))
    Write-Host "Updated config.toml gpu_layers = $GpuLayers"
}

Write-Host "Vulkan GPU version installed. Run .\run.ps1 doctor to confirm."
