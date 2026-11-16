$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
python -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Could not create Python virtual environment' }
& .\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed' }
$PythonPath = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$ServerPath = Join-Path $PSScriptRoot 'server.py'
$Config = @{ mcpServers = @{ comsol = @{ command = $PythonPath; args = @($ServerPath) } } }
$Config | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'mcp-config.json') -Encoding utf8
Write-Host 'Ready. Merge mcp-config.json into your MCP client configuration.'
