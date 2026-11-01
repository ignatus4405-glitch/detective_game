; Inno Setup скрипт для Detective: Blackville
; Установите Inno Setup 6 и запустите: iscc tools/installer.iss

#define MyAppName "Детектив: Блэквил"
#define MyAppVersion GetEnv("VERSION")
#if MyAppVersion == ""
  #define MyAppVersion "0.1.0"
#endif
#define MyAppPublisher "Blackville Studio"
#define MyAppURL "https://github.com/ignatus4405-glitch/detective_game"

[Setup]
AppId={{8B1A2F3C-4D5E-6F78-90AB-CDEF12345678}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={autopf}\BlackvilleDetective
DisableProgramGroupPage=yes
OutputBaseFilename=DetectiveBlackville-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
SetupIconFile=src\detective_game\assets\images\icon.ico

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\DetectiveBlackville.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\latest.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\README.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\DetectiveBlackville.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\DetectiveBlackville.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DetectiveBlackville.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
