# PAEG 技术说明 — 唯一来源目录 ✅

> **本目录为 PAEG 技术说明的唯一来源**（2026-08-29 整理，取代 §3.93 旧结论）。

## 资产清单（完整）

| 类型 | 文件 | 说明 |
|---|---|---|
| 文本 | `PAEG技术说明.md` | md 源（v1.2.27）；渲染输入 |
| 最新 PDF | `PAEG技术说明_v1.2.29.pdf` | 最新交付 PDF |
| 历史 PDF | `archive/PAEG技术说明_v0.69~v1.2.28.pdf` | 历史版本归档 |
| 渲染资产 | `build.ps1` / `extract_figures.py` / `pre_render.py` / `render_pdf.py` / `verify_atlas.py` | 图册构建流水线（SVG 矢量直出） |
| 渲染资产 | `style.css` / `template.html` / `mermaid.min.js` | 样式 / HTML 骨架 / Mermaid 引擎 |
| 说明 | `README.md` | 渲染模板 + 24 条渲染经验 + 更新日志 |

## 唯一来源关系

- **md 编辑源**：根目录 `PAEG技术说明.md`（四份核心文档之一，活跃编辑处）；本目录为文档库收录副本，渲染时由 build.ps1 读取。
- **渲染资产唯一来源**：本目录（不再散落于交付物）。
- **PDF 唯一来源**：本目录（最新 `PAEG技术说明_v1.2.29.pdf` + `archive/`）。

## 渲染命令

```
cd "Alexandria Bibliotheca\技术说明" && .\build.ps1
```

> build.ps1 读根目录 `PAEG技术说明.md` → SVG 矢量直出 → 输出 PDF 到本目录。
