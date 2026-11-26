param([string]$Uri)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

function Get-AutosaveReparseTag {
    param([string]$Path)

    if (-not ('NppAutosave.ReparseInfo' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;

namespace NppAutosave {
    public static class ReparseInfo {
        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        private struct FindData {
            public uint Attributes;
            public System.Runtime.InteropServices.ComTypes.FILETIME CreationTime, LastAccessTime, LastWriteTime;
            public uint SizeHigh, SizeLow, ReparseTag, Reserved;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 260)]
            public string Name;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 14)]
            public string AlternateName;
        }

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, ExactSpelling = true, SetLastError = true)]
        private static extern IntPtr FindFirstFileW(string path, out FindData data);
        [DllImport("kernel32.dll")]
        private static extern bool FindClose(IntPtr handle);

        public static uint ReadTag(string path) {
            FindData data;
            IntPtr handle = FindFirstFileW(path, out data);
            if (handle == new IntPtr(-1))
                throw new Win32Exception(Marshal.GetLastWin32Error());
            try {
                return data.ReparseTag;
            } finally {
                FindClose(handle);
            }
        }
    }
}
'@
    }
    return [NppAutosave.ReparseInfo]::ReadTag($Path)
}

function Resolve-AutosaveCopy {
    param([string]$Link, [string]$BaseDirectory)

    $match = [regex]::Match(
        $Link, '\Anpp-autosave:(backup|old)/((?:[0-9a-f]{2}){1,1024})\z',
        [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )
    if (-not $match.Success) {
        throw 'Enlace de Autosave no valido.'
    }
    $hex = $match.Groups[2].Value
    $bytes = New-Object byte[] ($hex.Length / 2)
    for ($i = 0; $i -lt $bytes.Length; $i++) {
        $bytes[$i] = [Convert]::ToByte($hex.Substring($i * 2, 2), 16)
    }
    $utf8 = New-Object System.Text.UTF8Encoding -ArgumentList $false, $true
    $name = $utf8.GetString($bytes)
    if ($name -match '[<>:"/\\|?*\x00-\x1f]' -or $name -match '[. ]\z' -or
        $name.EndsWith('.meta.json', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'El enlace no identifica un nombre de copia permitido.'
    }
    $bucket = '_backup'
    if ($match.Groups[1].Value -ieq 'old') {
        $bucket = '_old'
    }
    $folder = [IO.Path]::GetFullPath([IO.Path]::Combine($BaseDirectory, $bucket))
    $path = [IO.Path]::GetFullPath([IO.Path]::Combine($folder, $name))
    if (-not [string]::Equals(
        [IO.Path]::GetDirectoryName($path), $folder, [StringComparison]::OrdinalIgnoreCase
    )) {
        throw 'La copia esta fuera del directorio permitido.'
    }
    $directory = Get-Item -LiteralPath $folder -Force
    $file = Get-Item -LiteralPath $path -Force
    if ($file.PSIsContainer) {
        throw "La copia es un directorio: $path"
    }
    foreach ($item in @($directory, $file)) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            $tag = Get-AutosaveReparseTag -Path $item.FullName
            # CLOUD and CLOUD_1..F vary only in bits 12..15; older placeholders have their own tags.
            if (($tag -band 0xFFFF0FFFL) -ne 0x9000001AL -and
                $tag -ne 0x80000015L -and $tag -ne 0x80000021L) {
                throw ('Tipo de enlace no permitido: {0} (tag 0x{1:X8}, atributos {2}).' -f
                    $item.FullName, $tag, $item.Attributes)
            }
        }
    }
    return $path
}

function Open-AutosaveCopy {
    param([string]$Link, [string]$SettingsPath)

    $settings = ConvertFrom-Json ([IO.File]::ReadAllText($SettingsPath, [Text.Encoding]::UTF8))
    $path = Resolve-AutosaveCopy -Link $Link -BaseDirectory $settings.base_dir
    $executable = [IO.Path]::GetFullPath($settings.notepad_path)
    if (-not [IO.File]::Exists($executable)) {
        throw 'No se encuentra Notepad++. Ejecuta OpenAutosaveIndex.py para registrar su ruta.'
    }
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $executable
    $start.UseShellExecute = $false
    $start.Arguments = '"' + $path + '"'
    $process = [Diagnostics.Process]::Start($start)
    $process.Dispose()
}

if ($MyInvocation.InvocationName -ne '.') {
    try {
        if ($args.Count -ne 0) {
            throw 'El lanzador solo acepta un enlace de Autosave.'
        }
        Open-AutosaveCopy -Link $Uri -SettingsPath (Join-Path $PSScriptRoot 'settings.json')
    } catch {
        Add-Type -AssemblyName System.Windows.Forms
        [void][System.Windows.Forms.MessageBox]::Show(
            $_.Exception.Message, 'NPP Autosave - Abrir copia'
        )
        exit 1
    }
}
