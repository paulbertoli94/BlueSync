[Setup]
AppName=BlueSync
AppVersion=1.0.1
DefaultDirName={pf}\BlueSync
DefaultGroupName=BlueSync
OutputDir=installer
OutputBaseFilename=BlueSyncInstaller
Compression=lzma
SolidCompression=yes
SetupIconFile=C:\Users\paulb\PycharmProjects\BlueSync\icon_not_connected.ico
UninstallDisplayIcon={app}\BlueSync.exe

[Files]
Source: "C:\Users\paulb\PycharmProjects\BlueSync\dist\BlueSync.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "C:\Users\paulb\PycharmProjects\BlueSync\icon_connected.png"; DestDir: "{app}"
Source: "C:\Users\paulb\PycharmProjects\BlueSync\icon_not_connected.png"; DestDir: "{app}"
Source: "C:\Users\paulb\PycharmProjects\BlueSync\ToothTray.exe"; DestDir: "{app}"

[Icons]
Name: "{group}\BlueSync"; Filename: "{app}\BlueSync.exe"
Name: "{userstartup}\BlueSync"; Filename: "{app}\BlueSync.exe"; Tasks: autostart

[Tasks]
Name: autostart; Description: "Avvia automaticamente all'accesso"; GroupDescription: "Opzioni di avvio:"
