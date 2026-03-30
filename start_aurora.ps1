# AURORA v4.0 — Full Hologram Launch Script
# Starts: Ollama Brain + Unified Voice/Hologram Engine
# Usage:
#   Normal:     .\start_aurora.ps1
#   Fan mode:   .\start_aurora.ps1 -Fan

param(
    [switch]$Fan,
    [switch]$Test
)

Write-Host ""
Write-Host "  AURORA v4.0 -- Live Holographic Voice Assistant" -ForegroundColor Cyan
Write-Host "  Mode: $(if ($Fan) { 'LED FAN (HDMI Fullscreen)' } elseif ($Test) { 'TEST' } else { 'Laptop Preview' })" -ForegroundColor Yellow
Write-Host ""

# 1. Start Ollama (AI Brain) in background
Write-Host "[1/2] Starting Ollama AI Brain (phi3:mini)..." -ForegroundColor Yellow
Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2

# 2. Launch Unified AURORA Voice + Hologram Engine in a single native process window
Write-Host "[2/2] Launching Unified AURORA System..." -ForegroundColor Magenta

$pyArgs = @("main.py", "--image", "gui/avatar.jpeg", "--video", "gui/avatar.mp4")
if ($Fan) { $pyArgs += "--fullscreen" }
if ($Test) { $pyArgs += "--test" }

Write-Host ""
Write-Host "  AURORA is LIVE. Ready for speech!" -ForegroundColor White
Write-Host "  Close the Hologram window to shut down." -ForegroundColor Gray
Write-Host ""

& "C:\Users\indhu\AppData\Local\Programs\Python\Python312\python.exe" $pyArgs
