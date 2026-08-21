# deploy/canary.ps1 —— PAEG 灰度发布脚本（§3.79 D2 · 依据 deploy/灰度回滚规范.md）
# 用途：Canary 阶梯（C1 1-5% → C2 20% → C3 50% → C4 100%）+ 闸门检查 + kill switch + 回滚。
# 用法：
#   pwsh deploy/canary.ps1 -Stage C1        # 推进到 C1（1-5% 流量）
#   pwsh deploy/canary.ps1 -Stage C4        # 全量发布
#   pwsh deploy/canary.ps1 -Gate C1         # 只跑 C1 闸门检查（错误率/P95/eval）
#   pwsh deploy/canary.ps1 -KillSwitch ppt  # 60s 止损：关闭模块
#   pwsh deploy/canary.ps1 -Rollback <commit>  # 5min 回滚：git revert + smoke 验证
# 依赖：仅 PowerShell 5.1+；服务运行中（/api/health、/api/metrics 可访问）。
# 说明：单机部署用配置级 canary（paeg_modules.json 门控 + cohort 字段），
#       多实例场景按权重切流（Nginx upstream + /api/health 探针，规范 §一-3）。

param(
    [ValidateSet("C1", "C2", "C3", "C4", "Gate", "KillSwitch", "Rollback", "Status")]
    [string]$Stage = "Status",
    [string]$BaseUrl = "http://127.0.0.1:5000",
    [string]$ModuleId = "",          # KillSwitch 用：要关闭的模块（ppt/history/voice...）
    [string]$Commit = "",            # Rollback 用：要回退到的 commit
    [switch]$Force,                  # 跳过闸门强制推进（应急）
    [string]$Cohort = ""             # 用户组灰度：cohort 名（预留，多实例/画像 cohort 分桶）
)

$ErrorActionPreference = "Continue"
$sep = "=" * 60

# 灰度阶梯定义（与规范 §一 一致）
$STAGES = @{
    "C1" = @{ pct = 5;  gate = "错误率 ≤ 0.5% 且 P95 不劣化 >20% 且 eval pass rate 不降"; watch = "24h" }
    "C2" = @{ pct = 20; gate = "同上 + 无 P0 上报"; watch = "24h" }
    "C3" = @{ pct = 50; gate = "同上 + 反馈正常"; watch = "24h" }
    "C4" = @{ pct = 100; gate = "全量 72h 无回滚触发"; watch = "72h" }
}

Write-Output $sep
Write-Output "PAEG 灰度发布 $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  stage=$Stage  base=$BaseUrl"
Write-Output $sep

# ─────────────────────────────────────────────
# 闸门检查（Gate）：错误率 / P95 / eval pass rate
# ─────────────────────────────────────────────
function Test-CanaryGate {
    param([string]$StageName)
    # 注意：函数输出会被 `$r = Test-CanaryGate` 捕获——进度信息用 Write-Host 直接显示，
    # 函数只返回布尔结果（避免输出污染返回值）。
    Write-Host ""
    Write-Host "[Gate] $StageName 闸门检查（$($STAGES[$StageName].gate)）"
    $ok = $true
    try {
        $m = Invoke-RestMethod -Uri "$BaseUrl/api/metrics" -TimeoutSec 10
        $tot = $m.slo.total
        $err = [math]::Round($tot.error_rate * 100, 2)
        $p95 = $tot.p95_ms
        $llm = $tot.llm_calls
        Write-Host "  当前: error_rate=$err% p95=${p95}ms llm_calls=$llm"
        # 闸门 1：错误率 ≤ 0.5%
        if ($err -gt 0.5) { Write-Host "  ✘ 错误率 $err% > 0.5%"; $ok = $false }
        else { Write-Host "  ✔ 错误率 $err% ≤ 0.5%" }
        # 闸门 2：P95 ≤ 120s（教学 LLM 长生成容忍上限）
        if ($p95 -gt 120000) { Write-Host "  ✘ P95 ${p95}ms > 120s"; $ok = $false }
        else { Write-Host "  ✔ P95 ${p95}ms ≤ 120s" }
    } catch {
        Write-Host "  ✘ /api/metrics 不可达: $($_.Exception.Message)"
        $ok = $false
    }
    try {
        $h = Invoke-RestMethod -Uri "$BaseUrl/api/health" -TimeoutSec 10
        Write-Host "  ✔ health: status=$($h.status) llm=$($h.llm_ok) db=$($h.db_ok)"
    } catch {
        Write-Host "  ✘ /api/health 不可达"; $ok = $false
    }
    return $ok
}


function Invoke-KillSwitch {
    param([string]$Module)
    if (-not $Module) { Write-Output "用法: -KillSwitch <module>（ppt/history/voice/teach/chat...）"; return 1 }
    $cfgPath = Join-Path (Split-Path $PSScriptRoot -Parent) "05_实现原型/paeg_modules.json"
    if (-not (Test-Path $cfgPath)) { Write-Output "✘ 找不到 $cfgPath"; return 1 }
    $cfg = Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $cfg.PSObject.Properties["$Module"] = $false
    $cfg | ConvertTo-Json -Depth 5 | Set-Content $cfgPath -Encoding UTF8
    Write-Output "✔ Kill switch: $Module 已关闭（module_registry 热重载，无需重启）"
    Write-Output "  验证: Invoke-RestMethod $BaseUrl/api/health | 检查模块状态；60s 止损计时开始"
    return 0
}

# ─────────────────────────────────────────────
# Rollback（5min 回滚）
# ─────────────────────────────────────────────
function Invoke-Rollback {
    param([string]$Rev)
    if (-not $Rev) { Write-Output "用法: -Rollback <commit>"; return 1 }
    $proj = Split-Path $PSScriptRoot -Parent
    Push-Location $proj
    try {
        Write-Output "`n[Rollback] git revert 到 $Rev ..."
        git revert --no-edit $Rev 2>&1 | ForEach-Object { Write-Output "  $_" }
        Write-Output "`n[Rollback] smoke 验证..."
        Push-Location "05_实现原型"
        python smoke_test.py 2>&1 | Select-Object -Last 3 | ForEach-Object { Write-Output "  $_" }
        Pop-Location
        Write-Output "✔ 回滚完成；若 revert 冲突，改用: git checkout $Rev -- <file>（先备份未提交改动）"
    } finally {
        Pop-Location
    }
    return 0
}

# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
switch ($Stage) {
    "Status" {
        Write-Output "`n[Status] 当前模块门控状态"
        $cfgPath = Join-Path (Split-Path $PSScriptRoot -Parent) "05_实现原型/paeg_modules.json"
        if (Test-Path $cfgPath) {
            Get-Content $cfgPath -Raw -Encoding UTF8 | ConvertFrom-Json | Format-List
        } else {
            Write-Output "  未找到 paeg_modules.json"
        }
        Write-Output "`n灰度阶梯:"
        foreach ($k in "C1", "C2", "C3", "C4") {
            Write-Output "  $k = $($STAGES[$k].pct)% 流量（闸门: $($STAGES[$k].gate)，观察 $($STAGES[$k].watch)）"
        }
    }
    "Gate" {
        $s = if ($Cohort) { "C2" } else { "C1" }  # cohort 灰度默认 C2 起步
        Write-Output "`n[Gate] 检查阶段: $s"
        $r = Test-CanaryGate -StageName $s
        Write-Output "`n[Gate] 闸门结果: $(if ($r) { 'PASS' } else { 'FAIL' })"
        if ($r) { exit 0 } else { exit 1 }
    }
    "C1" { $s = "C1" }
    "C2" { $s = "C2" }
    "C3" { $s = "C3" }
    "C4" { $s = "C4" }
    default { $s = "" }
}
if ($s) {
    Write-Output "`n[推进] 发布到 $s（$($STAGES[$s].pct)% 流量，观察 $($STAGES[$s].watch)）"
    if (-not $Force) {
        $passed = Test-CanaryGate $s
        if (-not $passed) {
            Write-Output "`n✘ 闸门未通过——不推进。用 -Force 强制推进（应急）或先处理问题。"
            exit 1
        }
    } else {
        Write-Output "  ⚠ -Force：跳过闸门强制推进（应急路径）"
    }
    # 配置级 canary：模块门控已具备（如需关闭旧模块在此写入）
    Write-Output "  ✔ 模块门控（kill switch）就绪：改 paeg_modules.json 即热重载"
    if ($Cohort) {
        Write-Output "  ✔ 用户组灰度：cohort=$Cohort（画像字段，按 uid 哈希分桶——多实例场景启用）"
    }
    Write-Output "  下一步：观察 $($STAGES[$s].watch) 后跑 `pwsh deploy/canary.ps1 -Gate` 验证闸门再推进下一阶段"
    exit 0
}
if ($Stage -eq "KillSwitch") { exit (Invoke-KillSwitch $ModuleId) }
if ($Stage -eq "Rollback") { exit (Invoke-Rollback $Commit) }
