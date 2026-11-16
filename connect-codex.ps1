$ErrorActionPreference = 'Stop'
$PythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$ServerPath = Join-Path $PSScriptRoot 'server.py'
if (-not (Test-Path -LiteralPath $PythonPath)) { throw 'Run setup.ps1 first.' }
& codex mcp get comsol-editable *> $null
if ($LASTEXITCODE -eq 0) { throw 'comsol-editable is already registered. Review the existing configuration before replacing it.' }
& codex mcp add comsol-editable -- $PythonPath $ServerPath
if ($LASTEXITCODE -ne 0) { throw 'Could not register MCP server.' }
Write-Host 'Registered comsol-editable. Restart or reload Codex to load its tools.'
