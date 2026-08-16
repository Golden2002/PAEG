# build.ps1 — 图册构建流水线（Oracle 重新设计方案 · 统一入口）
# 四阶段：extract（严格解析+幽灵块检测）→ pre_render（逐图SVG）→ render（原方法PDF）→ verify（质量门）
# 用法：powershell -ExecutionPolicy Bypass -File build.ps1
# 退出码：0=成功，1=失败（任一阶段失败即中止）

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # 项目根（交付物/文档模板 的上级的上级）
$md = Join-Path $root "PAEG技术说明.md"
$pdf = Join-Path $root "交付物\技术说明\PAEG技术说明_v1.1.8.pdf"
$figs = Join-Path $root "figures"
$tmpl = $PSScriptRoot

$env:PYTHONIOENCODING = "utf-8"
Write-Host "=== 图册构建流水线 ===" -ForegroundColor Cyan

# 1. extract：严格解析 + 幽灵块检测（失败即中止——幽灵块是泄漏根因）
Write-Host "[1/4] extract_figures.py（幽灵块检测 + manifest）" -ForegroundColor Yellow
python (Join-Path $tmpl "extract_figures.py") $md $figs
if ($LASTEXITCODE -ne 0) { Write-Host "❌ 阶段1失败（幽灵块或解析错误）" -ForegroundColor Red; exit 1 }

# 2. pre_render：逐图预渲染 SVG（28 张，约 1min）
Write-Host "[2/4] pre_render.py（逐图 SVG 预渲染）" -ForegroundColor Yellow
python (Join-Path $tmpl "pre_render.py") $figs
if ($LASTEXITCODE -ne 0) { Write-Host "❌ 阶段2失败（有图渲染失败）" -ForegroundColor Red; exit 1 }

# 3. render：原方法生成 PDF（v1.1.5 纯版 + 幽灵块已修复 → 44页零泄漏）
Write-Host "[3/4] render_pdf.py（原方法 SVG 直出 → PDF）" -ForegroundColor Yellow
python (Join-Path $tmpl "render_pdf.py") --title "PAEG 技术说明文档" --sub "v1.1.8 · 2026-08-16" $md $pdf
if ($LASTEXITCODE -ne 0) { Write-Host "❌ 阶段3失败" -ForegroundColor Red; exit 1 }

# 4. verify：质量门（28图SVG完整 + PDF零泄漏）
Write-Host "[4/4] verify_atlas.py（质量门）" -ForegroundColor Yellow
python (Join-Path $tmpl "verify_atlas.py") $pdf $figs
if ($LASTEXITCODE -ne 0) { Write-Host "❌ 阶段4失败（质量门未过）" -ForegroundColor Red; exit 1 }

Write-Host "`n✅ 图册构建完成：44 页 PDF 零泄漏 + 28 图 SVG 完整" -ForegroundColor Green
exit 0
