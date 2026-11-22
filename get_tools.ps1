param([Parameter(Mandatory)][string]$App)
# Downloads FFmpeg (merging, MP3, clips) and Deno (needed by yt-dlp for YouTube)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$ff = Join-Path $App 'ffmpeg'
if (-not (Test-Path (Join-Path $ff 'ffmpeg.exe'))) {
    Write-Host '      downloading FFmpeg (about 100 MB)...'
    $zip = Join-Path $env:TEMP 'vd-ffmpeg.zip'
    $tmp = Join-Path $env:TEMP 'vd-ffmpeg'
    Invoke-WebRequest 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile $zip
    if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
    Expand-Archive $zip $tmp -Force
    New-Item -ItemType Directory -Force $ff | Out-Null
    foreach ($n in 'ffmpeg.exe', 'ffprobe.exe') {
        $f = Get-ChildItem $tmp -Recurse -Filter $n | Select-Object -First 1
        Copy-Item $f.FullName $ff -Force
    }
    Remove-Item $zip, $tmp -Recurse -Force
} else { Write-Host '      FFmpeg already there' }

$dn = Join-Path $App 'deno'
if (-not (Test-Path (Join-Path $dn 'deno.exe'))) {
    Write-Host '      downloading Deno...'
    $zip = Join-Path $env:TEMP 'vd-deno.zip'
    Invoke-WebRequest 'https://github.com/denoland/deno/releases/latest/download/deno-x86_64-pc-windows-msvc.zip' -OutFile $zip
    New-Item -ItemType Directory -Force $dn | Out-Null
    Expand-Archive $zip $dn -Force
    Remove-Item $zip -Force
} else { Write-Host '      Deno already there' }

# aria2 = multi-connection downloads (optional: the app falls back to normal speed without it)
$ar = Join-Path $App 'aria2'
if (-not (Test-Path (Join-Path $ar 'aria2c.exe'))) {
    try {
        Write-Host '      downloading aria2 (fast multi-connection downloads)...'
        $rel = Invoke-RestMethod 'https://api.github.com/repos/aria2/aria2/releases/latest' -Headers @{ 'User-Agent' = 'VideoDownloader' }
        $asset = $rel.assets | Where-Object { $_.name -like '*win-64bit*.zip' } | Select-Object -First 1
        $zip = Join-Path $env:TEMP 'vd-aria2.zip'
        $tmp = Join-Path $env:TEMP 'vd-aria2'
        Invoke-WebRequest $asset.browser_download_url -OutFile $zip
        if (Test-Path $tmp) { Remove-Item $tmp -Recurse -Force }
        Expand-Archive $zip $tmp -Force
        New-Item -ItemType Directory -Force $ar | Out-Null
        $f = Get-ChildItem $tmp -Recurse -Filter 'aria2c.exe' | Select-Object -First 1
        Copy-Item $f.FullName $ar -Force
        Remove-Item $zip, $tmp -Recurse -Force
    } catch {
        Write-Host '      (aria2 download failed - downloads will still work, just without fast mode)'
    }
} else { Write-Host '      aria2 already there' }
