# ops/checkup.ps1 —— PAEG 一键运维巡检（§3.79 运维友好性）
# 用途：运维工程师 1 分钟摸清系统状态（进程/端口/健康/指标/效果/复习队列/日志/磁盘）。
# 用法：pwsh ops/checkup.ps1 [-BaseUrl http://127.0.0.1:5000] [-Tail 20]
# 依赖：仅 PowerShell 5.1+（无第三方模块）。
# 说明：只读巡检，不修改任何状态；HTTP 端点不可达时给出明确降级提示。

param(
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [int]$Tail = 20,
    [switch]$NoHttp
)

$ErrorActionPreference = "Continue"
$sep = "=" * 60
Write-Output $sep
Write-Output "PAEG 运维巡检 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  base=$BaseUrl"
Write-Output $sep

# ── 1. 进程与端口 ──
Write-Output "`n[1] 进程与端口"
$port = ([uri]$BaseUrl).Port
$listening = netstat -ano | Select-String "LISTENING" | Select-String ":$port\s"
if ($listening) {
    Write-Output "  ✔ 端口 $port 在监听"
    $pids = ($listening | ForEach-Object { ($_ -split '\s+')[-1] } | Sort-Object -Unique)
    foreach ($pid_ in $pids) {
        $proc = Get-Process -Id $pid_ -ErrorAction SilentlyContinue
        if ($proc) { Write-Output "  ✔ PID $pid_ = $($proc.ProcessName)  CPU=$([math]::Round($proc.CPU,1))s  WS=$([math]::Round($proc.WorkingSet64/1MB))MB" }
    }
} else {
    Write-Output "  ✘ 端口 $port 未监听（服务未启动或端口不同）"
}

# ── 2. HTTP 健康检查 ──
Write-Output "`n[2] HTTP 健康检查"
if (-not $NoHttp) {
    try {
        $h = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 10
        Write-Output "  ✔ health: status=$($h.status) llm=$($h.llm_ok) db=$($h.db_ok) mcp=$($h.mcp_status) skills=$($h.skill_count) version=$($h.version)"
    } catch {
        Write-Output "  ✘ /api/health 不可达: $($_.Exception.Message)"
    }
    try {
        $m = Invoke-RestMethod -Uri "$BaseUrl/api/metrics" -TimeoutSec 10
        $tot = $m.slo.total
        Write-Output "  ✔ metrics: events=$($m.events_count) reqs=$($tot.count) p95=$($tot.p95_ms)ms err=$([math]::Round($tot.error_rate*100,2))% tokens=$($tot.tokens) llm_calls=$($tot.llm_calls)"
    } catch {
        Write-Output "  ✘ /api/metrics 不可达: $($_.Exception.Message)"
    }
    try {
        $e = Invoke-RestMethod -Uri "$BaseUrl/api/metrics/effects?window_days=30" -TimeoutSec 10
        foreach ($k in $e.metrics.PSObject.Properties.Name) {
            $v = $e.metrics.$k.value
            $vS = if ($null -eq $v) { "无数据" } else { $v }
            Write-Output "  ✔ effect[$k] = $vS (target≥$($e.metrics.$k.target), $($e.metrics.$k.status))"
        }
    } catch {
        Write-Output "  ✘ /api/metrics/effects 不可达: $($_.Exception.Message)"
    }
} else {
    Write-Output "  (跳过 HTTP 检查：-NoHttp)"
}

# ── 3. 日志尾部（错误/异常信号） ──
Write-Output "`n[3] 日志尾部（最近 $Tail 行中的异常信号）"
$root = Split-Path -Parent $PSScriptRoot
$logs = Get-ChildItem "$root\05_实现原型" -Filter "server*.log" -File -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 2
if ($logs) {
    foreach ($lg in $logs) {
        Write-Output "  --- $($lg.Name)（$([math]::Round($lg.Length/1KB,1))KB，更新于 $($lg.LastWriteTime.ToString('HH:mm:ss'))）"
        Get-Content $lg.FullName -Tail $Tail -ErrorAction SilentlyContinue |
            Select-String -Pattern "ERROR|Traceback|Exception|失败|忽略" |
            Select-Object -First 8 | ForEach-Object { Write-Output "    $($_.Line.Trim())" }
    }
} else {
    Write-Output "  （无 server*.log；开发模式日志在控制台）"
}

# ── 4. 磁盘与数据卷 ──
Write-Output "`n[4] 磁盘与关键数据"
try {
    $drive = (Get-PSDrive -Name (Split-Path -Qualifier $root).TrimEnd(':')) -ErrorAction SilentlyContinue
    if ($drive) { Write-Output "  ✔ $($drive.Name) 剩余 $([math]::Round($drive.Free/1GB,2)) GB / 共 $([math]::Round(($drive.Used+$drive.Free)/1GB,2)) GB" }
} catch { }
$trans = (Get-ChildItem "$root\05_实现原型\transcripts" -Filter "*.jsonl" -File -ErrorAction SilentlyContinue).Count
$users = (Get-ChildItem "$root\05_实现原型\users_data" -Directory -ErrorAction SilentlyContinue).Count
Write-Output "  ✔ transcripts 会话 $trans 个 · users_data 用户目录 $users 个"

Write-Output "`n$sep"
Write-Output "巡检完成。运维命令速查见维护手册 §18.60；回滚规范见 deploy/灰度回滚规范.md"
Write-Output $sep
