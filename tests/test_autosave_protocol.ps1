$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '../scripts/OpenAutosaveIndex/OpenAutosaveFile.ps1')

function New-TestLink {
    param([string]$Name, [string]$Bucket = 'backup')
    $hex = -join ([Text.Encoding]::UTF8.GetBytes($Name) | ForEach-Object { $_.ToString('x2') })
    return 'npp-autosave:' + $Bucket + '/' + $hex
}

function Assert-Rejected {
    param([string]$Link)
    $rejected = $false
    try {
        Resolve-AutosaveCopy -Link $Link -BaseDirectory $root | Out-Null
    } catch {
        $rejected = $true
    }
    if (-not $rejected) {
        throw "Unexpectedly accepted: $Link"
    }
}

$root = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString())
try {
    [void][IO.Directory]::CreateDirectory((Join-Path $root '_backup'))
    [void][IO.Directory]::CreateDirectory((Join-Path $root '_old'))
    $name = 'report_' + [char]0x00f1 + ' & [1].txt'
    foreach ($bucket in @('backup', 'old')) {
        $path = Join-Path (Join-Path $root ('_' + $bucket)) $name
        [IO.File]::WriteAllText($path, 'test')
        $resolved = Resolve-AutosaveCopy -Link (New-TestLink $name $bucket) -BaseDirectory $root
        if ($resolved -cne $path) {
            throw "Wrong file resolved: $resolved"
        }
    }
    foreach ($name in @(
        '../outside.txt', '..\outside.txt', 'C:\outside.txt', 'file.txt:stream',
        'file.txt.meta.json', 'file.', 'file ', 'file" -multiInst.txt',
        "file`n.txt", 'missing.txt'
    )) {
        Assert-Rejected (New-TestLink $name)
    }
    foreach ($link in @(
        'https://example.com', 'npp-autosave:backup/ff', 'npp-autosave:backup/1',
        'npp-autosave:backup/00', 'npp-autosave:elsewhere/6162',
        'npp-autosave:backup/6162" -Command anything'
    )) {
        Assert-Rejected $link
    }
    [void][IO.Directory]::CreateDirectory((Join-Path $root '_backup/directory.txt'))
    Assert-Rejected (New-TestLink 'directory.txt')

    $reader = ${function:Get-AutosaveReparseTag}
    $cloudName = 'cloud.txt'
    $cloudFolder = Join-Path $root '_backup'
    $cloudPath = Join-Path $cloudFolder $cloudName
    function Get-Item {
        param([string]$LiteralPath, [switch]$Force)
        if ($LiteralPath -eq $cloudPath -or $LiteralPath -eq $cloudFolder) {
            return [pscustomobject]@{
                FullName = $LiteralPath
                Attributes = [IO.FileAttributes]::Archive -bor [IO.FileAttributes]::ReparsePoint
                PSIsContainer = ($LiteralPath -eq $cloudFolder)
            }
        }
        return Microsoft.PowerShell.Management\Get-Item -LiteralPath $LiteralPath -Force:$Force
    }
    function Get-AutosaveReparseTag {
        param([string]$Path)
        return $simulatedTag
    }
    try {
        foreach ($simulatedTag in @(0x9000001AL, 0x9000F01AL, 0x80000015L, 0x80000021L)) {
            $resolved = Resolve-AutosaveCopy -Link (New-TestLink $cloudName) -BaseDirectory $root
            if ($resolved -cne $cloudPath) {
                throw 'Cloud placeholders should remain accessible.'
            }
        }
        foreach ($simulatedTag in @(0xA000000CL, 0xA0000003L, 0x80000000L)) {
            Assert-Rejected (New-TestLink $cloudName)
        }
    } finally {
        Remove-Item Function:\Get-Item
        Set-Item Function:\Get-AutosaveReparseTag -Value $reader
    }
    if ([Environment]::OSVersion.Platform -eq [PlatformID]::Unix) {
        $outside = Join-Path $root 'outside.txt'
        [IO.File]::WriteAllText($outside, 'outside')
        [void](New-Item -ItemType SymbolicLink -Path (Join-Path $root '_backup/link.txt') -Target $outside)
        # Windows tag reading is unavailable on Unix; simulate the native symlink tag.
        function Get-AutosaveReparseTag {
            param([string]$Path)
            return 0xA000000CL
        }
        try {
            Assert-Rejected (New-TestLink 'link.txt')
        } finally {
            Set-Item Function:\Get-AutosaveReparseTag -Value $reader
        }
    }
    Write-Output 'Protocol path validation tests passed.'
} finally {
    if ([IO.Directory]::Exists($root)) {
        [IO.Directory]::Delete($root, $true)
    }
}
