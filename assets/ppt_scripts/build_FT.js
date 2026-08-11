// PAEG v8 附录 F-T 章节（产出物/数据/能力/技术/测试/时间线）
// 独立生成 F-T 部分（P27-40），之后与主演示+附录A-E合并
const pptxgen = require("pptxgenjs");
const path = require("path");

const BASE = "C:/Users/团聚体/AppData/Local/Temp/opencode";
const OUT = path.join(BASE, "PAEG路演PPT_v8_FT.pptx");

const NAVY = "0F2A52", GOLD = "E6A528", CREAM = "F5F2EC", GRAY = "555F6B", WHITE = "FFFFFF";
const MARGIN = 0.5, CONTENT_W = 13.33 - MARGIN * 2;

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
let pageNum = 0;

function addFooter(slide) {
  pageNum++;
  slide.addText("PAEG 教育者 Agent · v8 · 2026.08", { x: MARGIN, y: 7.12, w: 5, h: 0.25, fontSize: 8, color: GRAY });
  slide.addText(String(pageNum), { x: 12.5, y: 7.12, w: 0.5, h: 0.25, fontSize: 8, color: GRAY, align: "right" });
}
function addAppHeader(slide, tag, title, sub) {
  slide.background = { color: CREAM };
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 1.15, fill: { color: NAVY } });
  slide.addText(tag, { x: MARGIN, y: 0.12, w: 2.5, h: 0.4, fontSize: 13, color: GOLD, bold: true, charSpacing: 2 });
  slide.addText(title, { x: MARGIN, y: 0.4, w: 12, h: 0.6, fontSize: 24, color: WHITE, bold: true, fontFace: "Microsoft YaHei" });
  slide.addText(sub, { x: MARGIN, y: 0.82, w: 12, h: 0.3, fontSize: 10, color: "C9D2E0" });
}
function addCard(slide, x, y, w, h, fill) {
  return slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.05 });
}

// ===== F 产出物（视频+PPT 4 页）=====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX F1", "产出物 · 教学视频关键帧", "光合作用 128s · 画面与讲解对齐");
  // 视频帧截图（高清提取，1280x720 → 16:9）
  const fw = 5.8, fh = fw * (720 / 1280);
  s.addImage({ path: "C:/Users/团聚体/AppData/Local/Temp/opencode/video_frames_hd/frame_00s.png", x: MARGIN + 0.5, y: 1.6, w: fw, h: fh, sizing: { type: "contain", w: fw, h: fh } });
  s.addImage({ path: "C:/Users/团聚体/AppData/Local/Temp/opencode/video_frames_hd/frame_30s.png", x: MARGIN + 6.8, y: 1.6, w: fw, h: fh, sizing: { type: "contain", w: fw, h: fh } });
  s.addText("帧1 导入：食物从哪来？", { x: MARGIN + 0.5, y: 1.6 + fh + 0.1, w: fw, h: 0.3, fontSize: 10, color: GRAY, align: "center" });
  s.addText("帧2 光反应：分解水放氧", { x: MARGIN + 6.8, y: 1.6 + fh + 0.1, w: fw, h: 0.3, fontSize: 10, color: GRAY, align: "center" });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX F2", "产出物 · 教学视频关键帧", "光合作用 · 暗反应与总结");
  // 高清帧 60s/90s
  const fw = 5.8, fh = fw * (720 / 1280);
  s.addImage({ path: "C:/Users/团聚体/AppData/Local/Temp/opencode/video_frames_hd/frame_60s.png", x: MARGIN + 0.5, y: 1.6, w: fw, h: fh, sizing: { type: "contain", w: fw, h: fh } });
  s.addImage({ path: "C:/Users/团聚体/AppData/Local/Temp/opencode/video_frames_hd/frame_90s.png", x: MARGIN + 6.8, y: 1.6, w: fw, h: fh, sizing: { type: "contain", w: fw, h: fh } });
  s.addText("帧3 暗反应：卡尔文循环", { x: MARGIN + 0.5, y: 1.6 + fh + 0.1, w: fw, h: 0.3, fontSize: 10, color: GRAY, align: "center" });
  s.addText("帧4 总结：光暗反应接力", { x: MARGIN + 6.8, y: 1.6 + fh + 0.1, w: fw, h: 0.3, fontSize: 10, color: GRAY, align: "center" });
  addFooter(s);
}
{
  // 新增 F2b：真实视频插入页
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX F2B", "产出物 · 真实演示视频", "光合作用 35s 片段 · PowerPoint 内可播放");
  // 视频帧静态图（防空白）
  const vfw = 6.5, vfh = vfw * (720 / 1280);
  s.addImage({ path: "C:/Users/团聚体/AppData/Local/Temp/opencode/video_frames_hd/frame_00s.png", x: MARGIN + 1.0, y: 1.8, w: vfw, h: vfh, sizing: { type: "contain", w: vfw, h: vfh } });
  // 视频本体（addMedia）
  s.addMedia({ path: "C:/Users/团聚体/AppData/Local/Temp/opencode/paeg_video_clip.mp4", x: MARGIN + 1.0, y: 1.8, w: vfw, h: vfh, sizing: { type: "contain", w: vfw, h: vfh } });
  s.addText("▶ 点击播放 · 光合作用演示（35s 片段）", { x: MARGIN + 1.0, y: 1.8 + vfh + 0.15, w: vfw, h: 0.4, fontSize: 12, color: GOLD, bold: true, align: "center" });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX F3", "产出物 · PPT 一键生成", "从对话到 .pptx 文件的完整闭环");
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX F3", "产出物 · PPT 一键生成", "从对话到 .pptx 文件的完整闭环");
  addCard(s, MARGIN, 1.5, CONTENT_W, 4.5, WHITE);
  s.addText([
    { text: "输入：", options: { bold: true, color: NAVY, fontSize: 13 } },
    { text: "用户上传文档 + 知识库检索 + 对话历史\n", options: { color: GRAY, fontSize: 12, breakLine: true } },
    { text: "输出：", options: { bold: true, color: NAVY, fontSize: 13 } },
    { text: "授课讲义 .pptx（学习目标/要求/形式/视觉风格）\n", options: { color: GRAY, fontSize: 12, breakLine: true } },
    { text: "价值：", options: { bold: true, color: NAVY, fontSize: 13 } },
    { text: "教学不只「对话」，还能沉淀为可交付文件", options: { color: GRAY, fontSize: 12 } }
  ], { x: MARGIN + 0.5, y: 1.8, w: 11, h: 3.5, lineSpacingMultiple: 1.5 });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX F4", "产出物 · 视频 + PPT 双产出", "从「对话」到「文件」到「视频」");
  addCard(s, MARGIN, 1.5, CONTENT_W, 4.5, WHITE);
  s.addText([
    { text: "教学闭环 → 知识掌握\n", options: { breakLine: true, fontSize: 13, color: NAVY, bold: true } },
    { text: "   → PPT 讲义（复习材料）\n", options: { breakLine: true, fontSize: 12, color: GRAY } },
    { text: "   → 教学视频（可分享/可重看）\n", options: { breakLine: true, fontSize: 12, color: GRAY } },
    { text: "   → 学习推荐（基于画像）", options: { fontSize: 12, color: GRAY } }
  ], { x: MARGIN + 0.5, y: 1.8, w: 11, h: 3.5, lineSpacingMultiple: 1.5 });
  addFooter(s);
}

// ===== G 数据全景 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX G", "30 场对话数据全景", "真实运行数据 · 24 维结构化指标");
  const stats = [
    { n: "30/30", d: "对话全部达标" },
    { n: "24 维", d: "结构化指标" },
    { n: "0 翻车", d: "无答非所问" },
    { n: "4 维", d: "闭环" }
  ];
  stats.forEach((st, i) => {
    const x = MARGIN + i * 3.17;
    addCard(s, x, 1.8, 2.9, 3.5, WHITE);
    s.addText(st.n, { x: x, y: 2.3, w: 2.9, h: 1.2, fontSize: 36, color: NAVY, bold: true, align: "center" });
    s.addText(st.d, { x: x + 0.2, y: 3.7, w: 2.5, h: 0.8, fontSize: 13, color: GRAY, align: "center" });
  });
  addFooter(s);
}

// ===== H 能力矩阵 2 页 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX H1", "全功能能力矩阵 · 教学与 Agent 架构", "PAEG 全部功能一览（上半）");
  const caps = [
    ["教学闭环", "诊断→计划→呈现→评估→调整→反思"],
    ["9 subagent", "Diagnostor/Planner/Presenter/Evaluator/Adapter/AnswerSolver/Affection/Update/Individuality"],
    ["意图路由", "模式短路 + LLM 判断 + 规则兜底"],
    ["学段联动", "SUBJECT_MIN_GRADE 初中12/高中22/本科28/考研2"],
    ["个体化", "17 维正交画像 + 增量建模 + 五层注入"],
    ["立德树人", "危机先行 + 先回应再关怀"],
    ["语言规范", "L0+L1+L2+L3 四层，AI 味 0.4"]
  ];
  caps.forEach((c, i) => {
    const y = 1.4 + i * 0.68;
    addCard(s, MARGIN, y, 2.6, 0.55, NAVY);
    s.addText(c[0], { x: MARGIN, y: y + 0.08, w: 2.6, h: 0.4, fontSize: 12, color: WHITE, bold: true, align: "center", fontFace: "Microsoft YaHei" });
    s.addText(c[1], { x: MARGIN + 2.8, y: y + 0.1, w: 9.5, h: 0.4, fontSize: 11, color: GRAY });
  });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX H2", "全功能能力矩阵 · 工具与产出", "PAEG 全部功能一览（下半）");
  const caps = [
    ["8层约束", "L0-L7 + mask 000-111 动态放开"],
    ["检索增强", "RRF + URL 规范化 + jieba + 双语变体"],
    ["自我进化", "四路自进化 + 7 分类 + 质量门禁"],
    ["MCP 双向", "3 server · 34 工具 · opencode 插件"],
    ["PPT 生成", "授课讲义模式 · 经验库驱动"],
    ["视频生成", "演讲稿驱动 · 三字段对齐"],
    ["语音", "edge-tts TTS + Web Speech STT"],
    ["文件4能力", "找答案/讲解/输出原文/重组结构"]
  ];
  caps.forEach((c, i) => {
    const y = 1.4 + i * 0.6;
    addCard(s, MARGIN, y, 2.6, 0.5, NAVY);
    s.addText(c[0], { x: MARGIN, y: y + 0.06, w: 2.6, h: 0.38, fontSize: 12, color: WHITE, bold: true, align: "center", fontFace: "Microsoft YaHei" });
    s.addText(c[1], { x: MARGIN + 2.8, y: y + 0.08, w: 9.5, h: 0.38, fontSize: 11, color: GRAY });
  });
  addFooter(s);
}

// ===== I 8层约束详细 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX I", "8 层约束：从 L0 安全基线到 L7 创造性生成", "动态提示词约束 · v0.50 全映射");
  const layers = [
    ["L0", "语言底线", "语言规范/格式/反AI腔/安全伦理", "永不跳过"],
    ["L1", "危机安全", "危机检测、安全护栏", "生效"],
    ["L2", "直接答案", "取消「直接给答案」（用户要答案时）", "生效"],
    ["L3", "情绪温度", "情绪/共情/约纳斯克制", "生效"],
    ["L4", "深度默认", "教学深度/学科教学法", "生效"],
    ["L5", "过程讲解", "分步讲解/教学步骤", "生效"],
    ["L6", "扩展深度", "母语迁移/概念对子", "生效"],
    ["L7", "迁移创造", "迁移运用/创造力", "生效"]
  ];
  layers.forEach((ly, i) => {
    const y = 1.35 + i * 0.6;
    addCard(s, MARGIN, y, 1.1, 0.5, NAVY);
    s.addText(ly[0], { x: MARGIN, y: y + 0.05, w: 1.1, h: 0.4, fontSize: 14, color: WHITE, bold: true, align: "center" });
    s.addText(ly[1], { x: MARGIN + 1.3, y: y + 0.06, w: 1.8, h: 0.38, fontSize: 12, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(ly[2], { x: MARGIN + 3.3, y: y + 0.08, w: 7.5, h: 0.38, fontSize: 11, color: GRAY });
    s.addText(ly[3], { x: MARGIN + 11.0, y: y + 0.08, w: 1.5, h: 0.38, fontSize: 11, color: GOLD });
  });
  s.addText("mask 000=4层全约束 → 111=7层全放开（L0 恒在）· 约束段 1089→1836 字", { x: MARGIN, y: 6.4, w: CONTENT_W, h: 0.4, fontSize: 12, color: GOLD, bold: true, align: "center" });
  addFooter(s);
}

// ===== J 语言规范三层 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX J", "语言三层：L1 约束 · L2 检测 · L3 修正", "程序化保证的规范中文 · AI 味阈值 0.4");
  const blocks = [
    ["L1 提示词约束", "语法自检 7 项注入 system：主谓宾/动宾搭配/介词规范/词法完整/句法完整"],
    ["L2 规则检测", "detect_ai_taste（AI 味 ≥0.4）+ _check_ellipsis（省略句）——零 LLM 成本"],
    ["L3 LLM 修正", "refiner.refine 保持风格补全——「它非常的重要。」→「这条定律很重要…」"]
  ];
  blocks.forEach((b, i) => {
    const y = 1.5 + i * 1.2;
    addCard(s, MARGIN, y, 2.8, 0.9, NAVY);
    s.addText(b[0], { x: MARGIN, y: y + 0.25, w: 2.8, h: 0.4, fontSize: 13, color: WHITE, bold: true, align: "center", fontFace: "Microsoft YaHei" });
    s.addText(b[1], { x: MARGIN + 3.1, y: y + 0.15, w: 9.2, h: 0.6, fontSize: 11, color: GRAY, lineSpacingMultiple: 1.3 });
  });
  s.addText("病句捕获率 15/16（94%）· 正确句零误报 · 8 模块全覆盖", { x: MARGIN, y: 5.6, w: CONTENT_W, h: 0.4, fontSize: 13, color: GOLD, bold: true, align: "center" });
  addFooter(s);
}

// ===== K 检索增强 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX K", "检索增强：RRF 融合 · jieba 切词 · 双语变体", "回答前强制检索 · 答案有据可依");
  const steps = [
    ["1", "查询变体", "中英双语 × 多轮改写（5 主题 × 3 轮 → 16 条）"],
    ["2", "多路检索", "BM25 + jieba + 网络 web_search_multi"],
    ["3", "RRF 融合", "k=60 倒数排名融合，无归一化问题"],
    ["4", "URL 规范化", "去 tracking/尾斜杠/www，去 30-60% 假重复"],
    ["5", "相关性打分", "核心词 + 标题 + 长度 + 域名权重"]
  ];
  steps.forEach((st, i) => {
    const y = 1.5 + i * 0.85;
    addCard(s, MARGIN, y, 0.6, 0.65, NAVY);
    s.addText(st[0], { x: MARGIN, y: y + 0.1, w: 0.6, h: 0.45, fontSize: 18, color: WHITE, bold: true, align: "center" });
    s.addText(st[1], { x: MARGIN + 0.9, y: y + 0.1, w: 1.8, h: 0.45, fontSize: 13, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(st[2], { x: MARGIN + 3.0, y: y + 0.13, w: 9.3, h: 0.4, fontSize: 11, color: GRAY });
  });
  s.addText("实测：「超导体的量子隧穿效应」→ 9 条相关结果 3.5s", { x: MARGIN, y: 6.1, w: CONTENT_W, h: 0.4, fontSize: 12, color: GOLD, bold: true, align: "center" });
  addFooter(s);
}

// ===== L 个体化画像 17 维 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX L", "个体化画像：17 维正交 · 增量建模 · 五层注入", "因材施教 · 对每个学生个别对待");
  const dims = ["身份学段","认知通道(VARK)","知识掌握状态","学习目标","价值观世界观","情感状态","学习动机","自我信念","会话意图","投入度","学习节奏","时段偏好","错误反应模式","协作偏好","多媒体偏好","可用性需求","母语"];
  dims.forEach((dim, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = MARGIN + col * 4.27, y = 1.4 + row * 0.55;
    addCard(s, x, y, 4.0, 0.42, WHITE);
    s.addText((i + 1) + ". " + dim, { x: x + 0.15, y: y + 0.05, w: 3.7, h: 0.32, fontSize: 10.5, color: NAVY });
  });
  s.addText("增量建模：说「代数弱」→ 画像自动记录 · 持久化 users_data/profile.json · 可扩第 18/19 维", { x: MARGIN, y: 5.2, w: CONTENT_W, h: 0.4, fontSize: 12, color: GRAY, align: "center" });
  addFooter(s);
}

// ===== M 自我进化 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX M", "自我进化：四路自进化 + 质量门禁", "越用越懂怎么教 · 数据飞轮");
  const items = [
    ["知识蒸馏", "成功教学入库 evolved_*.json"],
    ["提示词补丁", "evolve_prompt → subject_patches.md"],
    ["工具经验", "工具使用效果回流"],
    ["新学科需求", "问「量子力学」→ 自动注册入库"],
    ["SelfUpdateAgent", "7 分类 + 周期调度器落地执行"],
    ["质量门禁", "Constitutional AI 风格过滤"]
  ];
  items.forEach((it, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = MARGIN + col * 6.27, y = 1.5 + row * 1.4;
    addCard(s, x, y, 6.0, 1.1, WHITE);
    s.addText(it[0], { x: x + 0.25, y: y + 0.15, w: 2.0, h: 0.5, fontSize: 14, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(it[1], { x: x + 2.3, y: y + 0.2, w: 3.5, h: 0.8, fontSize: 11, color: GRAY, lineSpacingMultiple: 1.3 });
  });
  addFooter(s);
}

// ===== N 语音 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX N", "语音模块：TTS 朗读 + STT 语音输入", "edge-tts 免 key · Web Speech API · 模块门控");
  addCard(s, MARGIN, 1.5, 6.0, 3.8, WHITE);
  s.addText("TTS（朗读回答）", { x: MARGIN + 0.3, y: 1.7, w: 5, h: 0.5, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("edge-tts 中文女声\n后端 /api/voice/tts 生成 MP3\n点击朗读", { x: MARGIN + 0.3, y: 2.3, w: 5.4, h: 2.5, fontSize: 12, color: GRAY, lineSpacingMultiple: 1.5 });
  addCard(s, MARGIN + 6.3, 1.5, 6.0, 3.8, WHITE);
  s.addText("STT（语音提问）", { x: MARGIN + 6.6, y: 1.7, w: 5, h: 0.5, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("浏览器 Web Speech API\nChrome/Edge/Safari\n语音输入", { x: MARGIN + 6.6, y: 2.3, w: 5.4, h: 2.5, fontSize: 12, color: GRAY, lineSpacingMultiple: 1.5 });
  s.addText("真实边界：STT 需 HTTPS/localhost；微信内置浏览器不支持——已标注", { x: MARGIN, y: 5.6, w: CONTENT_W, h: 0.4, fontSize: 11, color: GOLD, align: "center" });
  addFooter(s);
}

// ===== O 知识导图/文件4能力 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX O", "知识导图 + 文件 4 能力", "从「问」到「产出」 · 用户资料深度利用");
  addCard(s, MARGIN, 1.5, 6.0, 3.8, WHITE);
  s.addText("知识导图", { x: MARGIN + 0.3, y: 1.7, w: 5, h: 0.5, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("说「画知识导图/列提纲/思维导图」\n→ 知识定位/知识树/关联/学习路径", { x: MARGIN + 0.3, y: 2.3, w: 5.4, h: 2.5, fontSize: 12, color: GRAY, lineSpacingMultiple: 1.5 });
  addCard(s, MARGIN + 6.3, 1.5, 6.0, 3.8, WHITE);
  s.addText("文件 4 能力", { x: MARGIN + 6.6, y: 1.7, w: 5, h: 0.5, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("① 找答案 ② 基于文件讲解\n③ 输出原文 ④ 重组结构", { x: MARGIN + 6.6, y: 2.3, w: 5.4, h: 2.5, fontSize: 12, color: GRAY, lineSpacingMultiple: 1.5 });
  addFooter(s);
}

// ===== P 测试体系 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX P", "测试体系：从单元到 E2E 的五层保障", "每次改动前后必跑 · 5 命令全绿才发版");
  const tests = [
    ["单元测试", "pytest + tmp_path 隔离 · 可并行"],
    ["管线契约", "7 用例验证教学管线完整"],
    ["API 契约", "6 用例覆盖核心端点"],
    ["学段学科矩阵", "5 用例：学段×学科联动"],
    ["全模式 E2E", "chat/teach/mock · 36 端点多轮"],
    ["多轮注入实验", "5 维度：退化/决策/语言/约束/tool"],
    ["audit_check", "24/24 静态检视"],
    ["smoke_test", "27 秒验证关键 API"]
  ];
  tests.forEach((t, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = MARGIN + col * 6.27, y = 1.4 + row * 0.85;
    addCard(s, x, y, 6.0, 0.7, WHITE);
    s.addText(t[0], { x: x + 0.2, y: y + 0.15, w: 2.0, h: 0.4, fontSize: 12, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(t[1], { x: x + 2.2, y: y + 0.17, w: 3.6, h: 0.38, fontSize: 10.5, color: GRAY });
  });
  addFooter(s);
}

// ===== Q 测试数据全景 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX Q", "测试数据全景：30 场对话 · 0 翻车", "真实运行数据 · 24 维结构化指标");
  const stats = [
    ["30/30", "对话全部达标"], ["24 维", "结构化指标"], ["0 翻车", "无答非所问"],
    ["5863字", "教学 15 轮"], ["9723字", "倾诉 15 轮"], ["100%", "找答案 10 题通过"]
  ];
  stats.forEach((st, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = MARGIN + col * 4.27, y = 1.6 + row * 2.4;
    addCard(s, x, y, 4.0, 2.1, WHITE);
    s.addText(st[0], { x: x, y: y + 0.3, w: 4.0, h: 0.9, fontSize: 32, color: NAVY, bold: true, align: "center" });
    s.addText(st[1], { x: x + 0.3, y: y + 1.4, w: 3.4, h: 0.5, fontSize: 12, color: GRAY, align: "center" });
  });
  s.addText("数据来源：v51_test_results.json（真实运行日志）", { x: MARGIN, y: 6.6, w: CONTENT_W, h: 0.3, fontSize: 9, color: GOLD, align: "center" });
  addFooter(s);
}

// ===== R 查资料真实效果 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX R", "查资料 3 场景：检索增强真实效果", "哲学/物理/英语 · RRF 融合 + 知识库 + 网络");
  const scenes = [
    ["哲学入门书籍推荐", "n=2 条 · 知识库优先 → 网络补充 → RRF 融合"],
    ["物理竞赛学习方法", "n=6 条 · URL 规范化去重 → 融合出 6 条高相关"],
    ["英语单词记忆技巧", "n=6 条 · jieba 切词提升命中 → sources 卡片"]
  ];
  scenes.forEach((sc, i) => {
    const y = 1.5 + i * 0.9;
    addCard(s, MARGIN, y, 3.2, 0.7, NAVY);
    s.addText(sc[0], { x: MARGIN, y: y + 0.15, w: 3.2, h: 0.4, fontSize: 13, color: WHITE, bold: true, align: "center", fontFace: "Microsoft YaHei" });
    s.addText(sc[1], { x: MARGIN + 3.5, y: y + 0.18, w: 9.0, h: 0.4, fontSize: 11, color: GRAY });
  });
  // 配视频帧
  const fw = 4.5, fh = fw * (720 / 1280);
  s.addImage({ path: "D:/wbo-workspace/video_frames/v_p1.png", x: MARGIN + 1.5, y: 4.6, w: fw, h: fh, sizing: { type: "contain", w: fw, h: fh } });
  addFooter(s);
}

// ===== S 视频生成实测 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX S", "视频生成实测：演讲稿驱动管线", "光合作用 128s · 先写稿再配音 · 音画同步");
  addCard(s, MARGIN, 1.5, CONTENT_W, 2.5, WHITE);
  s.addText([
    { text: "管线：", options: { bold: true, color: NAVY, fontSize: 13 } },
    { text: "写演讲稿(narration) → TTS 合成(audio_duration) → 字幕(subtitle_cues) → 合并输出\n", options: { color: GRAY, fontSize: 12, breakLine: true } },
    { text: "v0.53 修复：", options: { bold: true, color: NAVY, fontSize: 13 } },
    { text: "演讲稿驱动修复音画不同步 · 关键帧静态图防空白", options: { color: GRAY, fontSize: 12 } }
  ], { x: MARGIN + 0.5, y: 1.8, w: 11, h: 2.0, lineSpacingMultiple: 1.5 });
  const fw = 4.5, fh = fw * (720 / 1280);
  s.addImage({ path: "D:/wbo-workspace/video_frames/v_p3.png", x: MARGIN + 1.5, y: 4.3, w: fw, h: fh, sizing: { type: "contain", w: fw, h: fh } });
  addFooter(s);
}

// ===== T 版本时间线 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX T", "版本演进时间线：v0.25 → v0.53", "从单文件到完整 Agent 架构 · 48 个版本");
  const milestones = [
    ["v0.25", "学段-学科联动 + PPT MCP + SelfUpdateAgent"],
    ["v0.35", "LLM 优先意图路由（14 意图）"],
    ["v0.36", "语音模块 + 母语迁移"],
    ["v0.41", "模块化拆分 + 测试隔离根治"],
    ["v0.42", "提示词模板引擎（12 动态槽）"],
    ["v0.45", "检索增强（RRF + URL + jieba）"],
    ["v0.50", "8 层约束（L0-L7）+ 全模式测试"],
    ["v0.53", "视频演讲稿驱动 + PPT 讲义 + 插件生态"]
  ];
  milestones.forEach((m, i) => {
    const y = 1.4 + i * 0.62;
    addCard(s, MARGIN, y, 1.6, 0.5, GOLD);
    s.addText(m[0], { x: MARGIN, y: y + 0.06, w: 1.6, h: 0.38, fontSize: 12, color: NAVY, bold: true, align: "center" });
    s.addText(m[1], { x: MARGIN + 1.9, y: y + 0.08, w: 10.4, h: 0.38, fontSize: 11, color: GRAY });
  });
  addFooter(s);
}

}

pres.writeFile({ fileName: OUT }).then(() => {
  console.log("F-T 章节已生成:", OUT, "| 页数:", pageNum);
}).catch(e => console.error("失败:", e));
