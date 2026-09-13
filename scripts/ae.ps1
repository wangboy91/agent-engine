# agent-engine 快捷命令（PowerShell）
# 用法：在仓库根目录执行  .\scripts\ae.ps1 <子命令...>
# 例如： .\scripts\ae.ps1 serve
#        .\scripts\ae.ps1 skill list

$ErrorActionPreference = "Stop"
$engine = Join-Path $PSScriptRoot "..\engine"
Set-Location $engine

# 首次：uv sync --extra dev
if (-not (Test-Path ".venv")) {
    uv sync --extra dev
}

uv run ae @args
