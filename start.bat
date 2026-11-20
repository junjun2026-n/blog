@echo off
REM ============================================================
REM 文件名称：start.bat
REM 生成日期：2026-11-11
REM 修改日期：2026-11-20
REM 版本信息：v0.261115
REM 作    者：JUN
REM 备    注：本程序由AI辅助完成。
REM           文件功能：执行 start 对应的启动、构建或运维任务。
REM           文件用途：供博客的 BLOG/start.bat 模块使用。
REM           注意事项：运行前检查依赖与配置；涉及数据或服务变更时先备份并验证。
REM ============================================================
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
pause
