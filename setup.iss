; Inno Setup script - compiled by build_setup.bat
#define AppName "Video Downloader"
#define AppVersion "2.3.2"
#define AppExe "VideoDownloader.exe"

[Setup]
AppId={{8F6A3C1E-2B7D-4E59-9C1A-5D3E7B2F4A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UsedUserAreasWarning=no
OutputDir=Output
OutputBaseFilename=VideoDownloader-Setup
SetupIconFile=assets\VideoDownloader.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start with Windows (in the tray)"; GroupDescription: "Options:"; Flags: unchecked

[Files]
Source: "dist\VideoDownloader\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "VideoDownloader.App"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; AppUserModelID: "VideoDownloader.App"; Tasks: desktopicon

[Registry]
; ytdl:// link handler for the Chrome button
Root: HKCU; Subkey: "Software\Classes\ytdl"; ValueType: string; ValueName: ""; ValueData: "URL:{#AppName}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\ytdl"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\ytdl\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"",0"
Root: HKCU; Subkey: "Software\Classes\ytdl\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""
; start with Windows
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VideoDownloader"; ValueData: """{app}\{#AppExe}"" ""--tray"""; Tasks: autostart
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "VideoDownloader"; Flags: uninsdeletevalue dontcreatekey

[Run]
Filename: "{app}\{#AppExe}"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
