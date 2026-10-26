@echo off
title CentraOperator Multi-Service Launcher
echo ==============================================================================
echo  Launching CentraOperator Multi-Service Architecture
echo ==============================================================================

echo [1/4] Starting CentraERP on http://localhost:4000...
start "CentraERP (Port 4000)" cmd /k "cd services\erp && node server.js"

timeout /t 2 /nobreak >nul

echo [2/4] Starting Agent Runtime (FastAPI) on http://localhost:8000...
start "CentraOperator Runtime (Port 8000)" cmd /k "cd services\runtime && python main.py"

timeout /t 2 /nobreak >nul

echo [3/4] Starting API Gateway on http://localhost:3000...
start "CentraOperator Gateway (Port 3000)" cmd /k "cd services\gateway && npm start"

timeout /t 2 /nobreak >nul

echo [4/4] Starting React Mission Control Dashboard on http://localhost:5173...
start "CentraOperator Dashboard (Port 5173)" cmd /k "cd services\dashboard && npm run dev"

timeout /t 3 /nobreak >nul

echo Opening Mission Control in default browser...
start http://localhost:5173

echo ==============================================================================
echo  All services running!
echo  - Dashboard: http://localhost:5173
echo  - Gateway:   http://localhost:3000
echo  - Runtime:   http://localhost:8000
echo  - CentraERP: http://localhost:4000
echo ==============================================================================
pause
