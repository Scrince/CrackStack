#define MyAppName "CrackStack"
#define MyAppVersion "0.1.0"
#define MyAppExeName "CrackStack.exe"
[Setup]
AppId={{766C320B-36B1-487B-B617-5E8E54733101}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=CrackStack
DefaultDirName={localappdata}\Programs\CrackStack
DefaultGroupName=CrackStack
OutputDir=..\release\windows
OutputBaseFilename=CrackStack-Setup-0.1.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
Uninstallable=yes

[Files]
Source: "..\releases\windows\crackstack-harness-gui.exe"; DestDir: "{app}"; DestName: "CrackStack.exe"; Flags: ignoreversion
Source: "..\releases\windows\crackstack-harness.exe"; DestDir: "{app}"; DestName: "crackstack-cli.exe"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\CrackStack"; Filename: "{app}\CrackStack.exe"

