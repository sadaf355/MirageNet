# Start MirageNet backend and frontend in parallel
Write-Host "Starting MirageNet Backend and Frontend..." -ForegroundColor Cyan

Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\start-backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "$PSScriptRoot\start-frontend.ps1"

Write-Host "Services started!" -ForegroundColor Green
Write-Host "Backend API:  http://127.0.0.1:8000/docs" -ForegroundColor Yellow
Write-Host "Frontend App: http://127.0.0.1:5173" -ForegroundColor Yellow
