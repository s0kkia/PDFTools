#define MyAppName "PDFTools test-1"
#define MyAppVersion "1.0.0"
#define MyAppExeName "PDFTools.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-47A8-9B0C-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\PDFTools test-1
DefaultGroupName={#MyAppName}
OutputDir=..\dist-installer
OutputBaseFilename=PDFTools_test-1_Setup
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"

[Files]
Source: "..\dist\PDFTools.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README_test-1.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Запустить PDFTools test-1"; Flags: postinstall nowait skipifsilent
