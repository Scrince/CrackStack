[CmdletBinding()]
param(
    [string]$ProjectRoot = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -Scope Global -ErrorAction SilentlyContinue) {
    $global:PSNativeCommandUseErrorActionPreference = $false
}

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = Split-Path -Parent $PSScriptRoot
}

$releaseHome = Join-Path $ProjectRoot '.gnupg-release'
$docsDir = Join-Path $ProjectRoot 'docs'
$pubDoc = Join-Path $docsDir 'CrackStack_Release_Signing_2026_pubkey.asc'
$docsSums = Join-Path $docsDir 'SHA256SUMS'

function Convert-ToGpgHomeArgument([string]$Path, [string]$GpgPath) {
    if ($GpgPath -match '\\Git\\usr\\bin\\gpg\.exe$' -and $Path -match '^([A-Za-z]):\\(.*)$') {
        $drive = $Matches[1].ToLowerInvariant()
        $tail = $Matches[2] -replace '\\', '/'
        return "/$drive/$tail"
    }
    return $Path
}

if (-not (Test-Path -LiteralPath $releaseHome)) {
    throw "Missing release GnuPG home: $releaseHome"
}

$gpgCommand = Get-Command gpg -ErrorAction Stop
$gpgPath = $gpgCommand.Source
$gpgHome = Convert-ToGpgHomeArgument $releaseHome $gpgPath
try {
    $sec = & $gpgPath --homedir $gpgHome --list-secret-keys --with-colons 2>$null | Out-String
    $fprLine = ($sec -split "`n" | Where-Object { $_ -match '^fpr:' } | Select-Object -First 1)
    if (-not $fprLine) { throw "No secret key in $releaseHome" }
    $fpr = ($fprLine -split ':')[9]

    New-Item -ItemType Directory -Path $docsDir -Force | Out-Null
    $pub = & $gpgPath --homedir $gpgHome --armor --export $fpr 2>$null | Out-String
    Set-Content -Path $pubDoc -Value $pub.TrimEnd() -Encoding ASCII

    $targets = @()
    $relRoot = Join-Path $ProjectRoot 'releases'
    if (Test-Path $relRoot) {
        Get-ChildItem $relRoot -Recurse -File | Where-Object {
            $_.Extension -in '.exe', '.zip', '.dmg', '.gz', '.AppImage' -or
            $_.Name -match 'crackstack-harness' -and $_.Extension -eq ''
        } | ForEach-Object { $targets += $_.FullName }
    }
    $rootExe = Join-Path $ProjectRoot 'CrackStack-Qwen-Coder.exe'
    if (Test-Path $rootExe) { $targets += $rootExe }

    $targets = $targets | Where-Object { $_ -and (Test-Path $_) -and $_.Extension -ne '.asc' } | Select-Object -Unique
    $lines = @()
    Push-Location $ProjectRoot
    try {
        foreach ($f in $targets) {
            $rel = (Resolve-Path -LiteralPath $f -Relative) -replace '^\.\\', '' -replace '\\', '/'
            if ($rel -match '\.asc$') { continue }
            $h = (Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant()
            $lines += "$h  $rel"
            $asc = "$f.asc"
            if (Test-Path $asc) { Remove-Item -LiteralPath $asc -Force }
            & $gpgPath --homedir $gpgHome --batch --yes --local-user $fpr --detach-sign --armor --output $asc -- $f
            if ($LASTEXITCODE -ne 0) { throw "gpg sign failed for $f" }
            Write-Host "Signed $rel"
        }
        if ($lines.Count -gt 0) {
            (($lines -join "`n") + "`n") | Set-Content -Path $docsSums -Encoding ASCII -NoNewline
            $asc = "$docsSums.asc"
            if (Test-Path $asc) { Remove-Item -LiteralPath $asc -Force }
            & $gpgPath --homedir $gpgHome --batch --yes --local-user $fpr --detach-sign --armor --output $asc -- $docsSums
            Write-Host "Wrote $docsSums"
        }
    } finally {
        Pop-Location
    }
    Write-Host "Done fingerprint=$fpr"
} finally {
    if (Get-Command gpgconf -ErrorAction SilentlyContinue) {
        & gpgconf --kill all 2>$null | Out-Null
    }
}
