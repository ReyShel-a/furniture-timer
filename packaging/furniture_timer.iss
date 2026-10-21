; Per-user Windows installer. No administrator rights: the app keeps its data in %APPDATA%.

#define AppVersion "0.4.1"

[Setup]
AppId={{A7C3E1B4-9F26-4D58-8C0A-6B5E2F91D047}
AppName=Furniture Timer
AppVersion={#AppVersion}
AppPublisher=Furniture Timer
DefaultDirName={localappdata}\FurnitureTimer
DefaultGroupName=Furniture Timer
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=FurnitureTimer-Setup-{#AppVersion}
SetupIconFile=..\assets\furniture_timer.ico
UninstallDisplayIcon={app}\FurnitureTimer.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=auto

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FurnitureTimer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Furniture Timer"; Filename: "{app}\FurnitureTimer.exe"
Name: "{autodesktop}\Furniture Timer"; Filename: "{app}\FurnitureTimer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\FurnitureTimer.exe"; Description: "{cm:LaunchProgram,Furniture Timer}"; Flags: nowait postinstall skipifsilent
