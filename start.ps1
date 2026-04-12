Write-Host ""
Write-Host "  ⚡ Skald Bench" -ForegroundColor Cyan
Write-Host "  Запуск сервера..." -ForegroundColor Gray
Write-Host ""
pip install -r requirements.txt -q
Write-Host "  Открывай: http://127.0.0.1:7860" -ForegroundColor Green
Write-Host ""
python server.py
