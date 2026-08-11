# ============================================================
# PAEG 公网服务启动脚本（方案 A：临时隧道）
# 启动后：
#   - 本地 PAEG server (127.0.0.1:5000)
#   - Cloudflare 临时隧道（公网访问）
# 使用方法：双击本脚本，或 PowerShell 运行
# ============================================================
$ErrorActionPreference = "Continue"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  PAEG 教育者智能体 - 公网服务启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. 检查并清理旧进程
$conn = Get-NetTCPConnection -LocalPort 5000 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($conn) {
    Write-Host "  释放被占用的 5000 端口 (PID $($conn.OwningProcess))..." -ForegroundColor Yellow
    taskkill /PID $conn.OwningProcess /F 2>$null | Out-Null
    Start-Sleep -Seconds 2
}

# 2. 启动 PAEG server（后台）
Write-Host "  启动 PAEG server..." -ForegroundColor Green
$env:PYTHONIOENCODING = "utf-8"
$server = Start-Process -FilePath "python" -ArgumentList @(
    "`"D:\桌面\智能体架构与开发（含大模型）\14_教育者Agent项目\05_实现原型\server.py`""
) -WindowStyle Hidden -PassThru
Write-Host "  server PID: $($server.Id)" -ForegroundColor Green
Start-Sleep -Seconds 3

# 3. 验证本地服务
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:5000/api/health" -TimeoutSec 10
    Write-Host "  本地服务 OK: $($h.status)，知识库 $($h.kb_stats.total) 节点" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️ 本地服务启动失败，请检查 server.py" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# 4. 启动 Cloudflare 隧道（前台运行，窗口保持打开）
Write-Host "`n  启动 Cloudflare 公网隧道..." -ForegroundColor Green
Write-Host "  请等待 5-15 秒，出现 https://xxx.trycloudflare.com 即为公网地址" -ForegroundColor Yellow
Write-Host "  复制该地址，任何设备浏览器打开即可访问 PAEG" -ForegroundColor Yellow
Write-Host "  提示：本窗口需保持打开，关闭 = 公网访问断开`n" -ForegroundColor Yellow

& "D:\devtools\cloudflared.exe" tunnel --url http://127.0.0.1:5000 --no-autoupdate

# 隧道关闭后清理 server
Write-Host "`n隧道已关闭，停止 PAEG server..." -ForegroundColor Yellow
Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
