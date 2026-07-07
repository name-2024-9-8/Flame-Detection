@echo off
chcp 65001 >nul
echo ============================================
echo  视频AI智能识别及预警管理信息系统
echo  火焰识别 - 统一启动脚本
echo ============================================
echo.
echo 启动方式:
echo   1 - Web管理平台 (Flask, port 5000)
echo   2 - YOLO11检测命令
echo   3 - PHP后端服务 (王永林API, port 8080)
echo.
set /p choice="请选择 [1/2/3]: "

if "%choice%"=="1" (
    echo.
    echo [启动] Flask Web 管理平台...
    echo   访问地址: http://127.0.0.1:5000
    echo   管理后台: http://127.0.0.1:5000/dashboard
    echo.
    python run.py web
)
if "%choice%"=="2" (
    echo.
    echo [启动] YOLO11检测命令
    echo   提示: 运行 python run.py detection --help 查看所有命令
    echo.
    cd /d "%~dp0detection"
    python main.py %*
    cd /d "%~dp0"
    pause
)
if "%choice%"=="3" (
    echo.
    echo [启动] PHP 后端服务...
    echo   Web server at http://localhost:8080
    echo.
    D:\php83\php-5.6.8\php.exe -c D:\php83\php-5.6.8\php.ini -S localhost:8080 -t "D:\BaiduNetdiskDownload\backed\web"
    pause
)
