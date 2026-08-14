# PAEG 技术文档 PDF 模板（可循环复用）

> v0.70+ 交付物 · 由 visual-engineering 微 agent 设计 · 可复用、可升级

## 用途

把 Markdown 技术文档渲染成**专业美观的 PDF**（A4，含封面/页眉页脚/分页表格/代码块样式）。适用于：技术说明、白皮书、报告、教材等正式文档。

## 文件结构

```
交付物/文档模板/
├── style.css          # 完整样式（封面/正文/表格/代码块/页眉页脚）
├── template.html      # HTML 骨架（封面区 {{COVER}} + 正文 {{CONTENT}}）
├── render_pdf.py      # 一键渲染脚本（md → HTML → Edge headless → PDF）
└── README.md          # 本文件
```

## 快速使用

```bash
python render_pdf.py input.md output.pdf [--title "文档标题"] [--sub "副标题"]
```

或手动：

```python
import markdown, io
# 1. md → HTML
content_html = markdown.markdown(open("input.md", encoding="utf-8").read(),
                                 extensions=["tables", "fenced_code"])
# 2. 套模板
tpl = open("template.html", encoding="utf-8").read()
final = tpl.replace("{{CONTENT}}", content_html)
# 3. Edge headless 打印
# msedge --headless --print-to-pdf=out.pdf file:///tmp.html
```

## 自定义（封面）

模板封面通过 `template.html` 的封面区（`<section class="cover">`）控制：
- 品牌条：`EDUCATION · AGENT · WHITEPAPER` → 改文本
- 副标语：`.cover-tagline` → 换文档定位描述
- 标题：`.cover-title`（主标题 + `.accent` 副题）
- 能力亮点：`.cover-features`（4 个 `.f` 卡片：数字 + 标签）→ 按文档主题换数据
- 元信息：`.cover-meta`（VERSION / DOCUMENT / DATE）

配色用 CSS 变量（`style.css` 顶部 `:root`）：`--c-primary-*`（主色）/ `--c-accent-*`（强调）/ `--c-bg`（底）——换主题只改变量。

## 升级与维护

- **版本记录**：每次修改在本文档"更新日志"登记（日期 + 改动 + 原因）
- **设计原则**：纯 HTML+CSS（Chromium/Edge 打印友好）；颜色克制（2-3 主色）；中文字体回退；A4 打印（@page + 页眉页脚 + 表格 thead 跨页）
- **回归验证**：改样式后渲染一篇测试文档 + Edge 截图检查（封面占满/正文可读/表格分页）


## 渲染生成经验（备份 · 与元能力 §5.6 一致）

**1. A4 打印**：`@page { size: A4; margin: 22mm 18mm 20mm 18mm }` + 封面 `@page :first { margin: 0 }`（封面独立无页眉页脚）。

**2. 封面占满**：`.cover-inner { min-height: 297mm; display: flex; flex-direction: column; justify-content: space-between }`——品牌顶部/标题中/元信息底；右侧视觉锚点（圆环）放**右上角小尺寸避让内容**（曾覆盖标题卡/能力卡）。

**3. 表格双底线修复**：`table { border-bottom: none }` + `tbody tr:last-child td { border-bottom: 0.6pt }`——外框与末行边框叠加会成双线。

**4. Mermaid 渲染（关键）**：
- ```mermaid 块 → `<pre class="mermaid">`（render_pdf.py 正则预处理）
- 模板引入 mermaid.js CDN + Edge `--virtual-time-budget=15000` 等 JS 渲染
- flowchart/sequenceDiagram 均渲染为 SVG（PDF 含矢量图）
- **正则坑**：匹配换行用 `"```mermaid\n(.*?)```"`（非 raw 字符串——raw 的 \n 不匹配换行）

**5. 排版留白**：行高 1.85、段距 15pt、表格 padding 10-11pt——更清晰可读。

**6. 可复用**：占位符 `{{DOC_TITLE}}/{{TAGLINE_LINES}}/{{FEATURES}}/{{META_ITEMS}}` + render_pdf.py 一键脚本（md→HTML→Edge→PDF）。

**7. 语言规范**：文档文字过语言规范（避免"30 秒看懂"类非正式词）。

## 更新日志

| 日期 | 版本 | 改动 |
|---|---|---|
| 2026-08-14 | v0.70 | 初始模板（visual-engineering 设计）：封面三段式（品牌/标题/元信息）+ 能力亮点区 + 页眉页脚 + 表格跨页 + 代码块样式 |
