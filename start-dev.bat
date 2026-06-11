@echo off
echo ============================================
echo  Video AI - Backend Dev Environment
echo ============================================
echo.

REM Start Redis
echo [1/2] Starting Redis...
start "Redis" /MIN D:\php83\redis\redis-server.exe D:\php83\redis\redis.windows.conf
echo   Redis started on port 6379

REM Start PHP built-in server
echo [2/2] Starting PHP Dev Server...
echo   Web server at http://localhost:8080
echo   Press Ctrl+C to stop
echo.
D:\php83\php-5.6.8\php.exe -c D:\php83\php-5.6.8\php.ini -S localhost:8080 -t "D:\BaiduNetdiskDownload\backed\web"
pause
