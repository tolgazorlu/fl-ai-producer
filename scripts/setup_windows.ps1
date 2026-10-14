# fl-ai-producer - Windows setup (idempotent). Run from the repo root in PowerShell.
# Steps: uv Pythons -> venvs -> loopMIDI (+ports) -> FL controller script -> MCP_Apply pyscript.
# Windows "Smart App Control" blocks unsigned .exe launchers in venvs, so the MCP server
# is always started as `python -m fl_studio_mcp.server` (see .mcp.json), never via the .exe.

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[1/6] Python via uv"
uv python install 3.11 3.12

Write-Host "[2/6] MCP server venv (.venv-flmcp)"
if (-not (Test-Path ".venv-flmcp")) { uv venv --python 3.11 .venv-flmcp }
$env:VIRTUAL_ENV = "$Root\.venv-flmcp"
uv pip install -e "vendor/flstudio-mcp[audio]"
Remove-Item Env:VIRTUAL_ENV

Write-Host "[3/6] Analysis venv (.venv)"
uv sync --extra ml --extra flp

Write-Host "[4/6] loopMIDI"
$loop = "C:\Program Files (x86)\Tobias Erichsen\loopMIDI\loopMIDI.exe"
if (-not (Test-Path $loop)) { winget install --id TobiasErichsen.loopMIDI --accept-source-agreements --accept-package-agreements -h }
if (-not (Get-Process loopMIDI -ErrorAction SilentlyContinue)) { Start-Process $loop; Start-Sleep 3 }
& "$Root\.venv-flmcp\Scripts\python.exe" "$Root\scripts\loopmidi_ports.py"

Write-Host "[5/6] FL Studio controller script"
$fls = "$env:USERPROFILE\Documents\Image-Line\FL Studio\Settings"
New-Item -ItemType Directory -Force "$fls\Hardware\FLStudioMCP" | Out-Null
Copy-Item "vendor-patches\device_FLStudioMCP.py" "$fls\Hardware\FLStudioMCP\" -Force   # upstream script + pattern_select command

Write-Host "[6/6] Seed MCP_Apply piano-roll script"
Push-Location "vendor\flstudio-mcp"
& "$Root\.venv-flmcp\Scripts\python.exe" -c "import os, fl_studio_mcp.pyscript_gen as g; os.makedirs(g.PIANO_ROLL_SCRIPTS_DIR, exist_ok=True); print('seeded ' + g.write_apply_script([], mode='append'))"
Pop-Location

Write-Host ""
Write-Host "Manual steps left (one time, inside FL Studio):"
Write-Host "  Options > MIDI Settings:"
Write-Host "    Input  'FLStudioMCP RX' -> Enable, Controller type = FLStudioMCP, Port = 42"
Write-Host "    Output 'FLStudioMCP TX' -> Enable, Port = 42"
Write-Host "  View > Script output should print: [FLStudioMCP] Ready"
Write-Host "Each session: Piano roll > Scripting menu > run MCP_Apply once."
Write-Host "Then start the bridge:  .\.venv-flmcp\Scripts\python.exe -m fl_studio_mcp.daemon"
