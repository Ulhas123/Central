# CentraOperator PowerShell Launcher
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " Launching CentraOperator Multi-Service Architecture" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan

$root = $PSScriptRoot

Write-Host "[1/4] Starting CentraERP on http://localhost:4000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/services/erp'; node server.js"

Start-Sleep -Seconds 2

Write-Host "[2/4] Starting Agent Runtime (FastAPI) on http://localhost:8000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/services/runtime'; python main.py"

Start-Sleep -Seconds 2

Write-Host "[3/4] Starting API Gateway on http://localhost:3000..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/services/gateway'; npm start"

Start-Sleep -Seconds 2

Write-Host "[4/4] Starting React Mission Control Dashboard on http://localhost:5173..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$root/services/dashboard'; npm run dev"

Start-Sleep -Seconds 3

Write-Host "Opening Mission Control Dashboard in default browser..." -ForegroundColor Green
Start-Process "http://localhost:5173"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " All services running! Check individual terminal windows for live logs." -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Cyan
