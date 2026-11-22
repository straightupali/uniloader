param([Parameter(Mandatory)][string]$App)
$py   = Join-Path $App 'venv\Scripts\pythonw.exe'
$main = Join-Path $App 'ytdl.py'
$ico  = Join-Path $App 'assets\VideoDownloader.ico'  # new name = Windows can't show a cached old icon

# ---- Desktop + Start menu shortcuts ----
$shell = New-Object -ComObject WScript.Shell
foreach ($dir in [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) {
    Remove-Item (Join-Path $dir 'YouTube Downloader.lnk') -ErrorAction SilentlyContinue  # first version
    $lnk = $shell.CreateShortcut((Join-Path $dir 'Video Downloader.lnk'))
    $lnk.TargetPath = $py
    $lnk.Arguments = '"' + $main + '"'
    $lnk.WorkingDirectory = $App
    $lnk.IconLocation = $ico
    $lnk.Description = 'Video Downloader'
    $lnk.Save()
}

# ---- taskbar: give the shortcuts the app's ID, so the running window uses this same icon ----
$appId = 'VideoDownloader.App'   # must match ytdl.py
try {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace VD {
    [StructLayout(LayoutKind.Sequential, Pack = 4)]
    public struct PropertyKey { public Guid fmtid; public uint pid; }
    [StructLayout(LayoutKind.Explicit, Size = 16)]
    public struct PropVariant { [FieldOffset(0)] public ushort vt; [FieldOffset(8)] public IntPtr p; }
    [ComImport, Guid("886D8EEB-8CF2-4446-8D02-CDBA1DBDCF99"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPropertyStore {
        void GetCount(out uint count);
        void GetAt(uint index, out PropertyKey key);
        void GetValue(ref PropertyKey key, out PropVariant value);
        void SetValue(ref PropertyKey key, ref PropVariant value);
        void Commit();
    }
    public static class Shortcut {
        [DllImport("shell32.dll", CharSet = CharSet.Unicode, PreserveSig = false)]
        static extern void SHGetPropertyStoreFromParsingName(string path, IntPtr bindCtx, int flags,
            ref Guid iid, [MarshalAs(UnmanagedType.Interface)] out IPropertyStore store);
        public static void SetAppId(string lnk, string id) {
            Guid iid = typeof(IPropertyStore).GUID;
            IPropertyStore store;
            SHGetPropertyStoreFromParsingName(lnk, IntPtr.Zero, 2 /* read-write */, ref iid, out store);
            PropertyKey key = new PropertyKey();
            key.fmtid = new Guid("9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3");  // System.AppUserModel.ID
            key.pid = 5;
            PropVariant value = new PropVariant();
            value.vt = 31;  // text
            value.p = Marshal.StringToCoTaskMemUni(id);
            try { store.SetValue(ref key, ref value); store.Commit(); }
            finally { Marshal.FreeCoTaskMem(value.p); Marshal.ReleaseComObject(store); }
        }
    }
}
'@
    foreach ($dir in [Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs')) {
        [VD.Shortcut]::SetAppId((Join-Path $dir 'Video Downloader.lnk'), $appId)
    }
} catch {
    Write-Host "      (couldn't set the taskbar ID: $($_.Exception.Message))"
}

# ---- ytdl:// link handler (used by the Chrome button) ----
$root = 'HKCU:\Software\Classes\ytdl'
New-Item $root -Force | Out-Null
Set-ItemProperty $root -Name '(default)' -Value 'URL:Video Downloader'
New-ItemProperty $root -Name 'URL Protocol' -Value '' -Force | Out-Null
New-Item "$root\DefaultIcon" -Force | Out-Null
Set-ItemProperty "$root\DefaultIcon" -Name '(default)' -Value $ico
New-Item "$root\shell\open\command" -Force | Out-Null
Set-ItemProperty "$root\shell\open\command" -Name '(default)' -Value ('"{0}" "{1}" "%1"' -f $py, $main)

# ---- keep "Start with Windows" pointing at this install ----
$run = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
if (Get-ItemProperty $run -Name 'VideoDownloader' -ErrorAction SilentlyContinue) {
    Set-ItemProperty $run -Name 'VideoDownloader' -Value ('"{0}" "{1}" "--tray"' -f $py, $main)
}

# ---- refresh Windows' icon cache so the new icon shows right away ----
try { Start-Process -FilePath "$env:SystemRoot\System32\ie4uinit.exe" -ArgumentList '-show' -WindowStyle Hidden -Wait } catch { }
