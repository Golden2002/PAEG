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


**8. 图跨页与高清**：Mermaid 图用 Playwright 元素截图 PNG 嵌入（device_scale_factor=2 高清）；img 设 `max-height:170mm` + `page-break-inside:avoid` 防跨页截断；图与文字 `margin:8mm auto`。

**9. Playwright 用系统 Edge**：`channel='msedge'`（无需下载 chromium）——`pip install playwright` 即可，浏览器用系统自带 Edge。

**10. Mermaid 高对比度主题（图9/15 深色文字修复 · v0.70）**：
- 原 `theme:'neutral'` 渲染 sequenceDiagram 时出现**深色文字 + 深色背景不可见**（如 SSE 节点）
- 修复：`theme:'base'` + 显式 themeVariables（`background:#ffffff / primaryColor:#f0f4ff / primaryTextColor:#1a1a2e / actorBkg/actorBorder/actorTextColor/noteBkgColor...`）+ CSS 强制覆盖（`.mermaid text,tspan { fill:#1a1a2e !important }` 等）
- **教训**：不要只调 theme 名，sequenceDiagram 的 actor/note/activation 配色必须显式声明——高对比度原则（浅底深字）对所有 Mermaid 图类型统一生效

**11. 封面背景截断教训（Chromium print 大高度渐变只画 ~50-62%）**：
- `.cover` 高度 297mm/1122px + 渐变背景在 `page.pdf` 中**只渲染上半**（Chromium print 对大高度元素背景的已知 bug）
- 尝试过：px 固定高度 / mm / prefer_css_page_size / dsf=1 独立页 / base64 SVG 背景 / PyMuPDF 流前缀 / insert_image(overlay=False)——**均无法根治**（fitz 渲染 Chromium PDF 还有兼容白屏问题）
- **结论**：接受既有状态（v0.69 同款，渐变到签名行），不强行全页背景；**关键修复优先于完美背景**（图 9/15 文字可见性是用户核心诉求）

**12. 图片排版留白控制（v0.70 用户要求）**：
- 单页大图时上方易有大片空白 → 用 `margin:8mm auto` + `max-height:170mm` + 行高/段距微调（行高 1.85 / 段距 15pt）让图尽量贴上下文
- 宁可一页一张图，也不留 >半页空白——图前段距压缩、图后紧跟说明文字

**13. 表格框线去重（双底线修复）**：
- `table { border-bottom: none }` + `tbody tr:last-child td { border-bottom: 0.6pt }`——外框底边与末行边框叠加会成**双线**；thead 用 `border-bottom` 单独声明，tbody 各行 `border-bottom` 保证横线连续不断
- 每次改样式后渲染测试文档 + Edge 截图检查（封面/正文/表格三处）

**14. Mermaid 图容器化（v0.71 排版优化 · 核心）**：
- **dsf=1 截图**：`device_scale_factor=2` 使 PNG 高 2 倍产生超长窄图+大片空白；改 dsf=1 后 PNG 尺寸减半，文件 2.5MB→2.2MB
- **figure 容器**：`.mermaid-fig` 统一控制（`max-width:174mm` 页宽自适应 + `max-height:215mm` 留页眉页脚缓冲 + `object-fit:contain`）+ 浅色底/圆角/细边框/微阴影提升视觉完成度
- **`.tall` 类**：高窄图（viewBox h>1.6w）加 `.tall` 允许跨页（`page-break-inside:auto`）——根治"一页一张图+大片空白"
- **防节尾空白**：`h2/h3 + figure { page-break-before: avoid }` 防标题孤立页底；`figure + p { margin-top:-2mm }` 图后段落拉近
- **教训**：不要把"图后短段落"自动转 figcaption——文档里的"图 N · 标题"段落是既有标题，误判会导致重复标题+隐藏原文（第 8 页 Mermaid 显示源码的根因）。保留既有标题，不做自动 caption

**15. 图片排版留白策略（v0.71 用户要求）**：单页大图上方易大片空白 → ①图容器 max-width/height 双约束 ②高窄图允许跨页 ③图后段落拉近 ④h2/h3 与图 page-break-before:avoid ⑤宁可一页一张图也不留 >半页空白

**16. Chromium print 图片压扁（v0.71 关键坑）**：
- 症状：动态 JS 插入的 `<img>`（`height:auto` + 父容器 `max-height`）在 `page.pdf` 中被压成 6pt 细线（宽正常、高塌陷），screen 正常
- 根因：**CSS `max-height` 对动态插入 img 在 Chromium print 中触发高度塌陷**（screen 正常但 print 塌陷）
- 修复：**去掉 img 的 `max-height`**（保留 max-width + 显式 HTML width/height 属性）——比例自动保持，print 不再塌陷
- 教训：print 渲染与 screen 不同，动态元素高度必须显式（width/height 属性）或去掉 max-height；用 fitz 的 `get_image_info().bbox` 检查 `<20pt` 高度图排查

**17. Mermaid 深色背景与配色统一（v0.71 用户洞察）**：
- **深色背景来源**：`style.css` 的 `pre{background:#1f2937}`（代码块深色）被 `<pre class="mermaid">` 继承 → 截图含深色边框残留
- **修复**：`pre.mermaid{background:#fff!important;border:none!important;padding:0!important}` + 截图前 JS 强制 pre/svg 白底 + 去 border/outline/margin
- **紫底白框冲突（用户核心洞察）**：把节点改淡紫后，文字标签背景仍白 → 紫底白框突兀。**改配色必须同步文字背景**——节点文字标签背景与节点同色（淡紫 #eef0ff）
- **配色方案**：采纳 visual 方案 A 蓝灰专业（primaryColor #f0f4f9 + textColor #0f1f3a + border #2b3a55 + decision 琥珀 #fef3c7 + cluster #eaf1f8）——比淡紫更专业、打印 CMYK 稳定；stroke ≥1.2px 适配高清
- **检测坑**：PNG 采样 (2,2) 落 pre 边框深色误报"深色图"——**采样应取 (10,10) 或图主体**，深色像素占比 <5% 为正常

**18. 高清截图（v0.71 用户要求"最高至尊"）**：
- `device_scale_factor=4`：PNG 像素×4（如 632→2528px），PDF 嵌入 DPI ~700，打印级清晰
- 代价：PNG 文件 4x（27 页 PDF 4.4MB），渲染时间 +2-3s/张
- 封面是纯 HTML/CSS 矢量渲染（无 PNG），page.pdf 输出天然最清晰——无需额外处理
- 分类逻辑用 PIL 读 PNG 宽高比，与 dsf 无关（比例不变），无需改

**19. 图分类策略（Oracle+visual 双咨询，v0.71 最终）**：
- 按 PNG 真实宽高比（PIL 读）：`ar≥3` wide（占满版心+min-height 防孤）/ `ar≤0.6` tall（限宽居中）/ `ar>1.6` tall / 其余 normal；sequenceDiagram 一律 normal（天然横向）
- hero（独占页放大）仅给关键架构总览图（如 fig0/8）
- 高窄图可源码层改分栏式（flowchart TD→LR + subgraph 分组）占满版心——仅适合并行/阶段型流程，决策树/状态机保持纵向

**20. 双主题方案（v0.71.1 用户精确指令 · 白框不可见的正确解法）**：
- **核心认知**：用户要的不是"去掉白框"，而是"**白框融入节点不可见**"——第一版 neutral 主题（白色节点 + 深色文字）下，Mermaid 文字标签白底与白色节点融为一体，白框自然消失
- **方案**：图按类型双主题——①保持现状（base 蓝灰）图9/15/16/17 ②其余 15 图第一版方案（`%%{init: {'theme': 'neutral'}}%%` 每图内嵌覆盖全局 base）
- **实现**：Mermaid 图内嵌 `%%{init: {'theme': 'neutral'}}%%` 指令（图级覆盖全局 initialize）——比改全局 initialize 灵活，可逐图指定
- **去白框 CSS 的真相**：`.mermaid foreignObject div{background:transparent}` 等强制透明，在 neutral 白节点上=文字直接印白色节点（白框消失）；在 base 蓝灰节点上=文字印蓝灰（无白框）——**两种主题下都成立**，是让白框不可见的通用手段
- **教训**：用户说"去白框"可能指"让框不可见"（融入背景）而非"删掉框元素"——先理解意图（白框 vs 蓝灰/白节点背景对比突兀），再选方案（同色系融合 或 透明）

**21. SVG 矢量直出终极方案（v1.1 ⭐ 放弃 PNG 截图，图直接矢量进 PDF）**：
- **核心决策**：不截图 PNG，让 mermaid.js 在浏览器渲染 SVG → page.pdf 直接输出矢量（2782 矢量路径、0 位图）——无限清晰，无截图/深色/白框/压扁/高清问题
- **白框根治（librarian 源码级）**：白框 = Mermaid `textPlacement:'fo'`（foreignObject 路径）内嵌 HTML div 默认白底，PDF 打印时显现。**根治：`sequence: { textPlacement: 'tspan' }`**——sequence 文字走原生 SVG text，完全绕开 foreignObject（mermaid svgDraw.js byFo→byTspan）
- **跨页截断**：`.mermaid svg { max-height: 240mm !important }` 限高，超高 SVG 等比缩放防跨页
- **宽度解放**：`svg { width: 100% !important }` 图占满版心全宽（用户要求），高度受限
- **大图分页**：渲染后 JS 检测 SVG viewBox 高度 > 页高 55% → 在【图标题段落前】插 `page-break-before:always` 分隔符——标题+图独占一页，不分离。**关键：用 viewBox 高度（非 getBoundingClientRect，避免 margin 误判）；阈值适中（65% 误伤小图，55% 合适）**
- **图标题同页**：分页符必须插在标题段落（pre 前含"图 N"的 p）之前，而非 pre 前——否则标题孤立上一页
- **教训**：①PNG 截图路线所有问题（深色/白框/压扁/高清/截断）在 SVG 直出下全部消失 ②白框优先查 Mermaid 渲染机制（textPlacement/foreignObject）而非 CSS 修补 ③分页判断用真实元素尺寸（viewBox）而非含 margin 的 rect

**22. 图标题-图同页（v1.1.2 用户反馈迭代）**：
- 症状：大图标题在上一页、图在下一页，中间大片空白
- 修复：JS 在【标题段落前】插 `page-break-before:always`（标题+图一起独占下一页）
- 迭代：阈值 65% 误伤小图（第11页图4被推走）→ 调 55% + 用 viewBox 真实高度 → 修复
- 教训：分页判断要区分"真大图"（viewBox 高）与"宽扁小图"（宽但矮）；阈值需实测调优

## 更新日志

| 日期 | 版本 | 改动 |
|---|---|---|
| 2026-08-14 | v0.70 | 初始模板（visual-engineering 设计）：封面三段式（品牌/标题/元信息）+ 能力亮点区 + 页眉页脚 + 表格跨页 + 代码块样式 |
| 2026-08-14 | v0.70.1 | Mermaid 高对比度主题（theme:base + themeVariables 显式配色 + CSS 强制覆盖）修复图9/15 深色文字不可见；封面亮点卡提亮（rgba 0.10→0.17 + 纯白标签 + 亮青数字）；dsf=1 独立 PDF 页面；经验记录 #10-13（高对比度主题/封面截断教训/图片排版/表格框线） |
| 2026-08-14 | v0.71 | Mermaid 图容器化排版优化（Oracle+visual 双咨询）：dsf=1 截图（PNG 减半）+ figure 容器（max-width/height 双约束 + 浅色底圆角细边框）+ .tall 高窄图跨页 + 节尾防空白（h2/h3 与图 page-break-before:avoid + 图后段落拉近）+ 修复 figcaption 误判既有标题；经验 #14-15 |
| 2026-08-14 | v0.71.1 | 排版深水区修复（多轮 Oracle+visual+用户洞察）：①print 图片压扁（去 max-height）②深色背景（pre.mermaid 白底）③紫底白框冲突（文字标签与节点同色）④配色方案 A 蓝灰专业 ⑤dsf=4 至尊高清 ⑥图分类三类+hero ⑦pre 去边框；经验 #16-19 |
| 2026-08-14 | v0.71.2 | 图双主题方案（用户精确指令）：保持现状（base 蓝灰）图9/15/16/17 + 其余 15 图第一版（neutral 白节点深字，白框融入不可见）；Mermaid 图级 `%%{init:{theme:'neutral'}}%%` 覆盖；经验 #20 |
| 2026-08-15 | v1.1 | SVG 矢量直出终极方案：放弃 PNG 截图，mermaid.js 浏览器渲染 SVG 直接 page.pdf（矢量无限清晰）；白框根治（sequence textPlacement:'tspan' 绕开 foreignObject div 白底）；跨页截断修复（svg max-height 240mm）；大图分页（标题前插 page-break-before）；宽度解放（svg width:100%）；经验 #21-22 |
