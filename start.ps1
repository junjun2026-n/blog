# ============================================================
# 文件名称：start.ps1
# 生成日期：2026-11-11
# 修改日期：2026-11-20
# 版本信息：v0.261115
# 作    者：JUN
# 备    注：本程序由AI辅助完成。
#           文件功能：执行 start 对应的启动、构建或运维任务。
#           文件用途：供博客的 BLOG/start.ps1 模块使用。
#           注意事项：运行前检查依赖与配置；涉及数据或服务变更时先备份并验证。
# ============================================================
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!(Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
    & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt
}
& '.\.venv\Scripts\python.exe' app.py
