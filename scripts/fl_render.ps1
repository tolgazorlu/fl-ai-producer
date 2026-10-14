# Render a .flp through FL Studio's GUI (FL 2026 ignores the documented /R command line).
#   powershell -ExecutionPolicy Bypass -File scripts/fl_render.ps1 -Flp C:\...\x.flp -Out C:\...\renders\x.wav
# Assumes a 2560x1440 primary screen (dialog coordinates), FL installed in the default path,
# and "Split mixer tracks" remembered by FL's render dialog. Nothing must cover FL's window.
param([Parameter(Mandatory=$true)][string]$Flp, [Parameter(Mandatory=$true)][string]$Out, [int]$TimeoutSec = 600)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Windows.Forms,System.Drawing
Add-Type @"
using System; using System.Runtime.InteropServices;
public class FLR { [DllImport("user32.dll")] public static extern bool SetCursorPos(int x,int y); [DllImport("user32.dll")] public static extern void mouse_event(uint f,uint x,uint y,uint d,UIntPtr e);
 public static void Click(int x,int y){ SetCursorPos(x,y); System.Threading.Thread.Sleep(120); mouse_event(2,0,0,0,UIntPtr.Zero); System.Threading.Thread.Sleep(60); mouse_event(4,0,0,0,UIntPtr.Zero);} }
"@
$ws = New-Object -ComObject WScript.Shell
$outDir = Split-Path -Parent $Out; New-Item -ItemType Directory -Force $outDir | Out-Null
$stem = [IO.Path]::GetFileNameWithoutExtension($Out)
$fl = "C:\Program Files\Image-Line\FL Studio 2026\FL64.exe"
$name = [IO.Path]::GetFileName($Flp)

# 1. open the project in the running instance (or a new one); answer "No" to a save prompt
Start-Process $fl -ArgumentList "`"$Flp`""
Start-Sleep 5; $null = $ws.AppActivate("FL Studio"); Start-Sleep -Milliseconds 500; $ws.SendKeys("n"); Start-Sleep 2
$t0 = Get-Date
do { Start-Sleep 2; $p = Get-Process FL64 -ErrorAction SilentlyContinue } while ((-not $p -or $p.MainWindowTitle -notlike "*$name*") -and ((Get-Date) - $t0).TotalSeconds -lt 90)
Start-Sleep 10
"loaded: $($p.MainWindowTitle)"

# 2. focus FL (empty toolbar area, never the playlist), Export > WAV, type the path
$null = $ws.AppActivate($p.MainWindowTitle); Start-Sleep -Milliseconds 600
[FLR]::Click(1400, 50); Start-Sleep -Milliseconds 500
$ws.SendKeys("^r"); Start-Sleep -Seconds 3
$ws.SendKeys($Out); Start-Sleep -Milliseconds 400; $ws.SendKeys("{ENTER}"); Start-Sleep -Seconds 3

# 3. Mode -> Full song, then Start
[FLR]::Click(1152, 448); Start-Sleep -Milliseconds 800; [FLR]::Click(1140, 470); Start-Sleep -Milliseconds 800
[FLR]::Click(1455, 987)
$t0 = Get-Date
do {
  Start-Sleep -Seconds 5
  $files = Get-ChildItem $outDir -Filter "$stem*.wav" -ErrorAction SilentlyContinue
  $title = (Get-Process FL64 -ErrorAction SilentlyContinue).MainWindowTitle
  $elapsed = ((Get-Date) - $t0).TotalSeconds
} while ($elapsed -lt $TimeoutSec -and -not ($files.Count -ge 1 -and $title -notlike '*Render*' -and $elapsed -gt 25))
Start-Sleep 5
"rendered $($files.Count) files in $([int]$elapsed)s"
