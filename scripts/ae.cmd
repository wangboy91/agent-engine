@echo off
rem agent-engine CLI wrapper
rem usage: scripts\ae.cmd serve
cd /d "%~dp0..\engine"
if not exist ".venv" (
  uv sync --extra dev
)
uv run ae %*
