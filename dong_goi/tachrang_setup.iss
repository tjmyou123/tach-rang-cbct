; ============================================================
; TachRang — kich ban tao bo cai dat Windows (Inno Setup 6)
; Nguon: thu muc portable dong_goi\TachRang_App (build bang tao_portable.py)
; Bien dich: chay dong_goi\tao_setup.py  (hoac ISCC.exe tachrang_setup.iss)
; Ghi chu: app ghi config/log/ket qua vao chinh thu muc cai
;          -> cai theo nguoi dung (khong can admin), mac dinh vao
;          %LocalAppData%\Programs\TachRang, nguoi dung co the doi sang D:\...
; ============================================================

#define TenApp "TachRang"
#define PhienBan "1.0.0"
#define NhaPhatHanh "Dental Segment"
#define ThuMucNguon "TachRang_App"

[Setup]
AppId={{B7E6D9C4-3C0A-4F2B-9A21-7D5E8F1A6B33}
AppName={#TenApp}
AppVersion={#PhienBan}
AppVerName={#TenApp} {#PhienBan}
AppPublisher={#NhaPhatHanh}
DefaultDirName={autopf}\{#TenApp}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=Output
OutputBaseFilename=TachRang_Setup_{#PhienBan}
SetupIconFile=tachrang.ico
UninstallDisplayIcon={app}\tachrang.ico
WizardStyle=modern
; Hien giay phep Apache 2.0 trong trinh cai dat
LicenseFile={#ThuMucNguon}\LICENSE
Compression=lzma2/fast
SolidCompression=no
LZMAUseSeparateProcess=yes
LZMANumBlockThreads=4
; Tong dung luong > 2.1 GB nen bat buoc chia lat (setup.exe + cac file .bin di kem)
DiskSpanning=yes
DiskSliceSize=2100000000

[Types]
Name: "full"; Description: "Cai day du (khuyen nghi)"
Name: "custom"; Description: "Tuy chon thanh phan"; Flags: iscustom

[Components]
Name: "core"; Description: "Chuong trinh chinh + Python runtime (bat buoc)"; Types: full custom; Flags: fixed
Name: "dentseg"; Description: "Model xuong ham + khoi rang (DentalSegmentator, ~0.25 GB)"; Types: full custom
Name: "totalseg"; Description: "Model rang FDI + xoang + so-ham (TotalSegmentator, ~0.6 GB)"; Types: full custom

[Tasks]
Name: "desktopicon"; Description: "Tao bieu tuong ngoai man hinh Desktop"; GroupDescription: "Bieu tuong:"

[Files]
Source: "{#ThuMucNguon}\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs createallsubdirs ignoreversion; Components: core
Source: "{#ThuMucNguon}\tachrang\*"; DestDir: "{app}\tachrang"; Flags: recursesubdirs createallsubdirs ignoreversion; Components: core
; config.json: khong ghi de khi nang cap, khong xoa khi go cai dat (giu cau hinh nguoi dung)
Source: "{#ThuMucNguon}\config.json"; DestDir: "{app}"; Flags: onlyifdoesntexist uninsneveruninstall; Components: core
Source: "{#ThuMucNguon}\requirements.txt"; DestDir: "{app}"; Components: core
Source: "{#ThuMucNguon}\TachRang.bat"; DestDir: "{app}"; Components: core
Source: "{#ThuMucNguon}\TachRang_console.bat"; DestDir: "{app}"; Components: core
Source: "{#ThuMucNguon}\HUONG-DAN.txt"; DestDir: "{app}"; Components: core
; Giay phep Apache 2.0 + ghi cong ben thu ba (bat buoc kem theo khi phan phoi)
Source: "{#ThuMucNguon}\LICENSE"; DestDir: "{app}"; Components: core
Source: "{#ThuMucNguon}\NOTICE"; DestDir: "{app}"; Components: core
Source: "{#ThuMucNguon}\README.md"; DestDir: "{app}"; Components: core
Source: "tachrang.ico"; DestDir: "{app}"; Components: core
Source: "{#ThuMucNguon}\models\DentalSegmentator\*"; DestDir: "{app}\models\DentalSegmentator"; Flags: recursesubdirs createallsubdirs; Components: dentseg
Source: "{#ThuMucNguon}\models\totalseg_weights\*"; DestDir: "{app}\models\totalseg_weights"; Flags: recursesubdirs createallsubdirs; Components: totalseg

[Dirs]
Name: "{app}\CBCT_input"; Components: core
Name: "{app}\ket_qua"; Components: core
Name: "{app}\logs"; Components: core

[Icons]
Name: "{autoprograms}\TachRang"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m tachrang"; WorkingDir: "{app}"; IconFilename: "{app}\tachrang.ico"; Comment: "Tach rang tu anh CBCT"
Name: "{autoprograms}\TachRang (console - xem loi)"; Filename: "{app}\TachRang_console.bat"; WorkingDir: "{app}"; IconFilename: "{app}\tachrang.ico"
Name: "{autodesktop}\TachRang"; Filename: "{app}\python\pythonw.exe"; Parameters: "-m tachrang"; WorkingDir: "{app}"; IconFilename: "{app}\tachrang.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\python\pythonw.exe"; Parameters: "-m tachrang"; WorkingDir: "{app}"; Description: "Mo TachRang ngay"; Flags: nowait postinstall skipifsilent
