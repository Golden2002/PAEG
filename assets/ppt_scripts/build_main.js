// PAEG 路演 PPT v8 从零构建 - 主演示部分（P1-P14）
const pptxgen = require("pptxgenjs");
const path = require("path");

const BASE = "C:/Users/团聚体/AppData/Local/Temp/opencode";
const OUT = path.join(BASE, "PAEG路演PPT_v8_终版.pptx");

// 品牌色
const NAVY = "0F2A52";
const GOLD = "E6A528";
const CREAM = "F5F2EC";
const GRAY = "555F6B";
const WHITE = "FFFFFF";

// 布局常量（英寸）
const MARGIN = 0.5;
const CONTENT_W = 13.33 - MARGIN * 2; // 12.33
const TITLE_Y = 0.35;
const FOOTER_Y = 7.12;

let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.author = "PAEG";
pres.title = "PAEG 路演";

// ===== 母版：加主设计 Logo（右上角） =====
const LOGO_PATH = "D:/桌面/智能体架构与开发（含大模型）/14_教育者Agent项目/09_GUI前端/assets/icons/paeg-logo.svg";
pres.defineSlideMaster({
  title: "CONTENT_SLIDE",
  background: { color: CREAM },
  objects: [
    { rect: { x: 0, y: 0, w: 13.33, h: 0.06, fill: { color: GOLD } } },
    { image: { path: LOGO_PATH, x: 12.35, y: 0.28, w: 0.55, h: 0.55, sizing: { type: "contain", w: 0.55, h: 0.55 } } }
  ]
});

// ===== 工具函数 =====
let pageNum = 0;

function addHeader(slide, part, title, dark = false) {
  // 左上角 PART 标签 + 标题（不用强调线）
  const tc = dark ? WHITE : NAVY;
  const sc = dark ? GOLD : GRAY;
  slide.addText(part, { x: MARGIN, y: TITLE_Y, w: 3.5, h: 0.3, fontSize: 11, color: sc, charSpacing: 2, bold: true });
  slide.addText(title, { x: MARGIN, y: TITLE_Y + 0.28, w: CONTENT_W, h: 0.6, fontSize: 26, color: tc, bold: true, fontFace: "Microsoft YaHei" });
}

function addFooter(slide, dark = false) {
  pageNum++;
  const fc = dark ? "B8C4D6" : GRAY;
  slide.addText("PAEG 教育者 Agent · v8 · 2026.08", { x: MARGIN, y: FOOTER_Y, w: 5, h: 0.25, fontSize: 8, color: GRAY });
  slide.addText(String(pageNum), { x: 12.5, y: FOOTER_Y, w: 0.5, h: 0.25, fontSize: 8, color: GRAY, align: "right" });
}

function addCard(slide, x, y, w, h, fill, line = null) {
  const opts = { x, y, w, h, fill: { color: fill }, rectRadius: 0.06 };
  if (line) opts.line = { color: line, width: 1 };
  return slide.addShape(pres.shapes.ROUNDED_RECTANGLE, opts);
}

// ===== P1 封面（深蓝） =====
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  // 装饰圆环
  s.addShape(pres.shapes.OVAL, { x: 9.8, y: -1.5, w: 6, h: 6, fill: { color: WHITE, transparency: 92 } });
  s.addShape(pres.shapes.OVAL, { x: -2.5, y: 5.2, w: 5, h: 5, fill: { color: GOLD, transparency: 90 } });
  // 顶部标签
  s.addText("EDUCATION AGENT · 2026", { x: MARGIN, y: 0.7, w: 6, h: 0.3, fontSize: 12, color: GOLD, charSpacing: 3, bold: true });
  // 主标题
  s.addText("PAEG", { x: MARGIN, y: 2.1, w: 8, h: 1.2, fontSize: 72, color: WHITE, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("Pedagogical Agent with Evolving Growth", { x: MARGIN + 0.05, y: 3.2, w: 9, h: 0.4, fontSize: 14, color: "D9DFE8", charSpacing: 2 });
  // 金线分隔（封面可用）
  s.addShape(pres.shapes.RECTANGLE, { x: MARGIN + 0.02, y: 3.85, w: 2.2, h: 0.045, fill: { color: GOLD } });
  // 主标语
  s.addText([
    { text: "它不只在回答问题，", options: { breakLine: true, fontSize: 26, color: WHITE, bold: true } },
    { text: "它在理解一个人。", options: { fontSize: 26, color: GOLD, bold: true } }
  ], { x: MARGIN, y: 4.2, w: 9, h: 1.2, fontFace: "Microsoft YaHei" });
  // 底部
  s.addText("新一代教育智能体 · 教学闭环 · 因材施教 × 立德树人 · 自我进化", { x: MARGIN, y: 6.7, w: 10, h: 0.4, fontSize: 11, color: "D9DFE8" });
  pageNum++;
}

// ===== P2 问题 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 01 · THE PROBLEM", "教育缺的不是第二个搜索框");
  // 3 个痛点卡
  const cards = [
    { title: "01 · 对话式 AI 的边界", desc: "大模型知道每个题的解法，但不知道学生是谁。\n一节课讲完，没有留下任何关于这个学生的记忆。" },
    { title: "02 · 真人教师的不可替代", desc: "一位老师带 40 个学生，没有余力记住\n每一个人的卡点、脆弱、和那一点进步。" },
    { title: "03 · 那一条「被看见」的缝隙", desc: "记忆、注意力、关系——\n这是 PAEG 要填补的位置。" }
  ];
  cards.forEach((c, i) => {
    const x = MARGIN + i * 4.27;
    addCard(s, x, 1.9, 3.9, 3.6, WHITE);
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.9, w: 0.07, h: 3.6, fill: { color: GOLD } });
    s.addText(c.title, { x: x + 0.3, y: 2.2, w: 3.3, h: 0.7, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(c.desc, { x: x + 0.3, y: 3.0, w: 3.3, h: 2.2, fontSize: 12, color: GRAY, lineSpacingMultiple: 1.3 });
  });
  // 底部结论
  s.addText("当学生说「我撑不住了」——大多数 AI 继续讲下一题，PAEG 会停下来。", {
    x: MARGIN, y: 6.0, w: CONTENT_W, h: 0.5, fontSize: 14, color: GOLD, bold: true, align: "center"
  });
  addFooter(s);
}

// ===== P3 学生说（情绪冲击） =====
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addText("学生说：", { x: MARGIN, y: 1.8, w: 6, h: 0.5, fontSize: 20, color: "D9DFE8" });
  s.addText("「我撑不住了。」", { x: MARGIN, y: 2.4, w: 11, h: 1.0, fontSize: 44, color: WHITE, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("—— PAEG 把这句「我撑不住了」作为唯一入口，而不是继续讲下一题。", {
    x: MARGIN, y: 3.7, w: 11, h: 0.5, fontSize: 16, color: GOLD
  });
  // 三条行为
  const acts = [
    { n: "01", t: "先停下来", d: "危机钩子先行，不进入教学流水线" },
    { n: "02", t: "先回应", d: "完整回应用户说的话，再自然融入关怀" },
    { n: "03", t: "再回归", d: "情绪稳定后，才回到学习" }
  ];
  acts.forEach((a, i) => {
    const x = MARGIN + i * 4.27;
    addCard(s, x, 5.0, 3.9, 1.4, "10224A");
    s.addText(a.n, { x: x + 0.25, y: 5.15, w: 0.8, h: 0.4, fontSize: 22, color: GOLD, bold: true });
    s.addText([
      { text: a.t + "  ", options: { bold: true, color: WHITE, fontSize: 13 } },
      { text: a.d, options: { color: "D9DFE8", fontSize: 10 } }
    ], { x: x + 1.1, y: 5.15, w: 2.6, h: 1.0 });
  });
  pageNum++;
}

// ===== P4 亮点：六种教学场景 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 02 · HIGHLIGHTS", "六种教学场景中，PAEG 都做了什么");
  const scenes = [
    { t: "概念讲解", d: "由浅入深，从现象到本质", i: "01" },
    { t: "习题辅导", d: "分步推导，错因定位", i: "02" },
    { t: "知识图谱", d: "梳理知识脉络与关联", i: "03" },
    { t: "学习方法", d: "元认知与策略指导", i: "04" },
    { t: "情绪陪伴", d: "先回应，再关怀，再学习", i: "05" },
    { t: "产出物", d: "PPT / 讲义 / 视频一键生成", i: "06" }
  ];
  scenes.forEach((sc, i) => {
    const col = i % 3, row = Math.floor(i / 3);
    const x = MARGIN + col * 4.27;
    const y = 1.7 + row * 2.4;
    addCard(s, x, y, 3.9, 2.1, WHITE);
    s.addShape(pres.shapes.OVAL, { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fill: { color: NAVY } });
    s.addText(sc.i, { x: x + 0.25, y: y + 0.32, w: 0.55, h: 0.4, fontSize: 16, color: WHITE, bold: true, align: "center" });
    s.addText(sc.t, { x: x + 1.0, y: y + 0.3, w: 2.7, h: 0.5, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(sc.d, { x: x + 1.0, y: y + 0.9, w: 2.7, h: 0.8, fontSize: 11, color: GRAY });
  });
  addFooter(s);
}

// ===== P5 架构 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 03 · ARCHITECTURE", "10 个子代理 + MCP 双向通道");
  // 中心 Agent 圆
  s.addShape(pres.shapes.OVAL, { x: 5.3, y: 2.6, w: 2.7, h: 2.7, fill: { color: NAVY } });
  s.addText("PAEG\n主 Agent", { x: 5.3, y: 3.3, w: 2.7, h: 1.0, fontSize: 16, color: WHITE, bold: true, align: "center", fontFace: "Microsoft YaHei" });
  // 9 个子代理环
  const agents = ["Diagnostor", "Planner", "Presenter", "Evaluator", "Adapter", "AnswerSolver", "Affection", "SelfUpdate", "Individuality"];
  agents.forEach((a, i) => {
    const ang = (i / agents.length) * Math.PI * 2 - Math.PI / 2;
    const cx = 6.65 + Math.cos(ang) * 3.4;
    const cy = 3.95 + Math.sin(ang) * 2.3;
    addCard(s, cx - 1.15, cy - 0.28, 2.3, 0.56, WHITE, "D5D9E0");
    s.addText(a, { x: cx - 1.15, y: cy - 0.2, w: 2.3, h: 0.4, fontSize: 10, color: NAVY, bold: true, align: "center" });
  });
  // 底部 MCP
  s.addText("LLM 层：DeepSeek  ·  工具层：7 内置工具 + 10 Skills + 3 MCP Server（filesystem/memory/pptx）", {
    x: MARGIN, y: 6.5, w: CONTENT_W, h: 0.4, fontSize: 12, color: GRAY, align: "center"
  });
  addFooter(s);
}

// ===== P6 约束栈 L0-L7 阶梯图（用户最喜欢的 v1 设计） =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 03 · CONSTRAINT STACK", "从 L0 绝对底线到 L7 自由创造");
  // 8 层阶梯（v1 设计：左下到右上倾斜，每层 0.5in，左缩进 0.4in）
  const layers = [
    { id: "L7", name: "自由创造", desc: "鼓励联想、跨学科、生活化类比", xoff: 0 },
    { id: "L6", name: "风格塑造", desc: "鼓励式语言、节奏、比喻偏好", xoff: 0.4 },
    { id: "L5", name: "教学策略", desc: "导入/新授/巩固/复习/应用/提高", xoff: 0.8 },
    { id: "L4", name: "学科规范", desc: "公式、术语、解题步骤正确性", xoff: 1.2 },
    { id: "L3", name: "学习画像", desc: "对接 17 维画像，因材施教", xoff: 1.6 },
    { id: "L2", name: "上下文连贯", desc: "长对话记忆，前情提要", xoff: 2.0 },
    { id: "L1", name: "情绪安全", desc: "识别「撑不住」→ 降速/暂停/追问", xoff: 2.4 },
    { id: "L0", name: "绝对底线", desc: "隐私/自伤干预/价值观偏差", xoff: 2.8 }
  ];
  const startY = 2.0;
  layers.forEach((ly, i) => {
    const y = startY + i * 0.5;
    const x = MARGIN + ly.xoff;
    const w = 7.6 - ly.xoff;
    // 阶梯条
    addCard(s, x, y, w, 0.42, i === 7 ? GOLD : (i % 2 === 0 ? "0F2A52" : "1A3A6B"));
    // 层号
    s.addText(ly.id, { x: x + 0.12, y: y + 0.03, w: 0.55, h: 0.36, fontSize: 13, color: WHITE, bold: true });
    // 名称
    s.addText(ly.name, { x: x + 0.75, y: y + 0.03, w: 1.4, h: 0.36, fontSize: 12, color: i === 7 ? NAVY : WHITE, bold: true, fontFace: "Microsoft YaHei" });
    // 描述
    s.addText(ly.desc, { x: x + 2.3, y: y + 0.05, w: w - 2.5, h: 0.32, fontSize: 10, color: i === 7 ? "0F2A52" : "C9D2E0" });
  });
  // 右侧标注：宽松/严格
  s.addText("宽松", { x: 0.62, y: startY - 0.4, w: 0.8, h: 0.3, fontSize: 10, color: GRAY, align: "center" });
  s.addText("严格", { x: 0.62, y: startY + 7 * 0.5 + 0.1, w: 0.8, h: 0.3, fontSize: 10, color: GRAY, align: "center" });
  // 右侧教学阶段映射表
  s.addText("教学阶段映射", { x: 10.6, y: 1.7, w: 2.3, h: 0.35, fontSize: 12, color: NAVY, bold: true, align: "center" });
  const mapping = [["导入 → L5", "新授 → L5"], ["巩固 → L4", "复习 → L3"], ["应用 → L4", "提高 → L6"], ["总结 → L2", "挑战 → L7"]];
  mapping.forEach((row, i) => {
    row.forEach((cell, j) => {
      addCard(s, 10.6 + j * 1.15, 2.15 + i * 0.42, 1.05, 0.34, WHITE, "D5D9E0");
      s.addText(cell, { x: 10.6 + j * 1.15, y: 2.19 + i * 0.42, w: 1.05, h: 0.26, fontSize: 9, color: NAVY, align: "center" });
    });
  });
  s.addText("8 层不多不少：少于 5 层无法兜底情绪安全，多于 8 层则过约束。", {
    x: MARGIN, y: 6.3, w: CONTENT_W, h: 0.4, fontSize: 12, color: GRAY, italic: true, align: "center"
  });
  addFooter(s);
}

// ===== P7 语言三层 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 03 · LANGUAGE LAYERS", "L1 是什么 · L2 怎么做 · L3 为什么");
  const layers = [
    { t: "L1 · 提示词约束", d: "语法自检 7 项注入 system\n主谓宾 / 动宾搭配 / 介词规范 / 词法句法完整", c: NAVY },
    { t: "L2 · 规则检测", d: "零 LLM 成本\ndetect_ai_taste（AI 味 ≥0.4）+ 省略句检测", c: "1A3A6B" },
    { t: "L3 · LLM 修正", d: "保持风格地补全重写\n「它非常的重要」→「这条定律很重要」", c: GOLD }
  ];
  layers.forEach((ly, i) => {
    const x = MARGIN + i * 4.27;
    addCard(s, x, 1.9, 3.9, 3.4, WHITE);
    s.addShape(pres.shapes.RECTANGLE, { x: x, y: 1.9, w: 3.9, h: 0.6, fill: { color: ly.c } });
    s.addText(ly.t, { x: x + 0.25, y: 2.0, w: 3.4, h: 0.4, fontSize: 14, color: WHITE, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(ly.d, { x: x + 0.25, y: 2.8, w: 3.4, h: 2.2, fontSize: 12, color: GRAY, lineSpacingMultiple: 1.35 });
  });
  s.addText("病句捕获率 15/16（94%），正确句零误报 · 语言规范性是独立于模型性能的能力", {
    x: MARGIN, y: 5.7, w: CONTENT_W, h: 0.4, fontSize: 12, color: GOLD, bold: true, align: "center"
  });
  addFooter(s);
}

// ===== P8 工程化 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 03 · ENGINEERING", "检索 RRF · 单步教学 · 预算窗口 · 安全加固");
  const cards = [
    { t: "检索增强", d: "RRF 融合 + URL 规范化\n+ jieba 切词 + 中英双语变体", n: "3.5s" },
    { t: "提示词模板引擎", d: "固定模板 + 12 动态槽\n按重要性降序注入", n: "12" },
    { t: "8 层约束栈", d: "L0-L7 动态放开\nL0 保底永不跳过", n: "8" },
    { t: "安全加固", d: "SECRET_KEY 双轨\npip-audit 5 高危全修", n: "0" }
  ];
  cards.forEach((c, i) => {
    const col = i % 2, row = Math.floor(i / 2);
    const x = MARGIN + col * 6.27;
    const y = 1.8 + row * 2.5;
    addCard(s, x, y, 6.0, 2.2, WHITE);
    s.addText(c.n, { x: x + 0.25, y: y + 0.2, w: 1.6, h: 0.9, fontSize: 40, color: GOLD, bold: true });
    s.addText(c.t, { x: x + 1.9, y: y + 0.3, w: 3.9, h: 0.5, fontSize: 15, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText(c.d, { x: x + 1.9, y: y + 0.9, w: 3.9, h: 1.1, fontSize: 11, color: GRAY, lineSpacingMultiple: 1.3 });
  });
  addFooter(s);
}

// ===== P9 评估：30 轮 =====
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  addHeader(s, "PART 04 · EVALUATION", "我们用 6 模式 × 30 轮真实对话验证", true);
  const stats = [
    { n: "30/30", d: "对话全部达标" },
    { n: "0", d: "翻车（无答非所问）" },
    { n: "24", d: "维结构化指标" },
    { n: "4", d: "维闭环（诊断-教学-评估-反思）" }
  ];
  stats.forEach((st, i) => {
    const x = MARGIN + i * 3.17;
    addCard(s, x, 2.2, 2.9, 2.4, "10224A");
    s.addText(st.n, { x: x, y: 2.6, w: 2.9, h: 0.9, fontSize: 36, color: GOLD, bold: true, align: "center" });
    s.addText(st.d, { x: x + 0.2, y: 3.7, w: 2.5, h: 0.6, fontSize: 12, color: "C9D2E0", align: "center" });
  });
  s.addText("覆盖教学 / 倾诉 / 找答案 / 查资料 / 学习方法 / 知识库 6 模式，全部真实运行", {
    x: MARGIN, y: 5.2, w: CONTENT_W, h: 0.4, fontSize: 13, color: "D9DFE8", align: "center"
  });
  pageNum++;
}

// ===== P10 教学杀手锏 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 04 · TEACHING DEMO", "孟德尔遗传 15 轮：从导入到独立挑战");
  // 左侧大原文
  addCard(s, MARGIN, 1.7, 7.5, 4.8, WHITE);
  s.addText("R1 · 导入", { x: MARGIN + 0.3, y: 1.9, w: 2, h: 0.4, fontSize: 13, color: GOLD, bold: true });
  s.addText("我们从一个你每天都能观察到的现象说起：你和你爸妈的眼睛颜色不一样。\n你爸爸是棕色眼睛，你妈妈也是棕色眼睛，可你是蓝色眼睛——这种情况在我们身边并不少见。\n问题来了：孩子是从父母那里「各取一半」的，那怎么会取着取着，颜色反而变了？", {
    x: MARGIN + 0.3, y: 2.4, w: 6.9, h: 2.2, fontSize: 15, color: NAVY, lineSpacingMultiple: 1.4, fontFace: "Microsoft YaHei"
  });
  s.addText("「各取一半」不是倒进杯子里搅一搅——遗传更像一人递给你一张卡片。", {
    x: MARGIN + 0.3, y: 5.3, w: 6.9, h: 0.6, fontSize: 13, color: GOLD, italic: true
  });
  // 右侧 UI 截图（原始比例 1725:2282）
  const imgH = 4.8, imgW = imgH * (1725 / 2282);
  s.addImage({ path: "D:/wbo-workspace/v51_teach_hd.png", x: 8.5, y: 1.7, w: imgW, h: imgH, sizing: { type: "contain", w: imgW, h: imgH } });
  s.addText("实际界面 · 1725×2282 原始比例", { x: 8.3, y: 6.6, w: 2.8, h: 0.3, fontSize: 8, color: GRAY, align: "center" });
  addFooter(s);
}

// ===== P11 倾诉杀手锏 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 04 · AFFECTION DEMO", "学业压力 15 轮：从崩溃到承诺");
  addCard(s, MARGIN, 1.7, 7.5, 4.8, WHITE);
  s.addText("R1 · 开场", { x: MARGIN + 0.3, y: 1.9, w: 2, h: 0.4, fontSize: 13, color: GOLD, bold: true });
  s.addText("两个月，在新学校，交不到朋友，上课走神。这三件事叠在一起，日子确实不好过。\n我想先问一个具体的问题：你说的「交不到朋友」，是指还没有人能说上话，还是有过几次交流却感觉被拒绝？", {
    x: MARGIN + 0.3, y: 2.4, w: 6.9, h: 2.0, fontSize: 15, color: NAVY, lineSpacingMultiple: 1.4, fontFace: "Microsoft YaHei"
  });
  s.addText("→ R15：\n「我会先从小目标做起，下周再来跟你分享进展」", {
    x: MARGIN + 0.3, y: 4.6, w: 6.9, h: 1.2, fontSize: 14, color: GOLD, bold: true, lineSpacingMultiple: 1.3
  });
  const imgH = 4.8, imgW = imgH * (1532 / 2282);
  s.addImage({ path: "D:/wbo-workspace/v51_aff_hd.png", x: 8.5, y: 1.7, w: imgW, h: imgH, sizing: { type: "contain", w: imgW, h: imgH } });
  s.addText("实际界面 · 1532×2282 原始比例", { x: 8.3, y: 6.6, w: 2.8, h: 0.3, fontSize: 8, color: GRAY, align: "center" });
  addFooter(s);
}

// ===== P12 产出物 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 04 · ARTIFACTS", "一节课之后，PAEG 自动产出");
  const arts = [
    { t: "PPT 讲义", d: "授课讲义（目标/要求/形式/风格）", icon: "C:/Users/团聚体/AppData/Local/Temp/opencode/icons_ppt.svg" },
    { t: "教学视频", d: "演讲稿驱动 · 音画同步", icon: "C:/Users/团聚体/AppData/Local/Temp/opencode/icons_video.svg" },
    { t: "知识导图", d: "结构化知识地图", icon: "C:/Users/团聚体/AppData/Local/Temp/opencode/icons_map.svg" },
    { t: "学习推荐", d: "基于画像的个性化建议", icon: "C:/Users/团聚体/AppData/Local/Temp/opencode/icons_recommend.svg" }
  ];
  arts.forEach((a, i) => {
    const x = MARGIN + i * 3.17;
    addCard(s, x, 2.0, 2.9, 3.2, WHITE);
    s.addImage({ path: a.icon, x: x + 0.75, y: 2.35, w: 1.4, h: 1.4, sizing: { type: "contain", w: 1.4, h: 1.4 } });
    s.addText(a.t, { x: x + 0.3, y: 3.3, w: 2.3, h: 0.5, fontSize: 15, color: NAVY, bold: true, align: "center", fontFace: "Microsoft YaHei" });
    s.addText(a.d, { x: x + 0.3, y: 3.9, w: 2.3, h: 1.0, fontSize: 11, color: GRAY, align: "center" });
  });
  s.addText("从「对话」到「文件」的完整产出闭环", { x: MARGIN, y: 5.6, w: CONTENT_W, h: 0.4, fontSize: 14, color: GOLD, bold: true, align: "center" });
  addFooter(s);
}

// ===== P13 质量 =====
{
  const s = pres.addSlide({ masterName: "CONTENT_SLIDE" });
  s.background = { color: CREAM };
  addHeader(s, "PART 05 · QUALITY", "30 / 30 轮全部达标");
  s.addText("30", { x: 2.2, y: 2.0, w: 4, h: 1.6, fontSize: 88, color: NAVY, bold: true, align: "center" });
  s.addText("/ 30 轮通过 · 0 缺陷", { x: 5.5, y: 2.6, w: 4, h: 0.8, fontSize: 24, color: GOLD, bold: true });
  s.addText("「通过」不是口号，是每一轮对话后那句结构化评估的结果。", {
    x: MARGIN, y: 4.3, w: CONTENT_W, h: 0.5, fontSize: 14, color: GRAY, align: "center"
  });
  // 修复清单
  const fixes = ["登录后索引文件丢失 → 已修复", "AES 加解密乱码 → 已修复", "核心测试崩溃 → 已修复", "pip-audit 5 高危 → 已修复"];
  fixes.forEach((f, i) => {
    const x = MARGIN + (i % 2) * 6.27, y = 5.0 + Math.floor(i / 2) * 0.7;
    addCard(s, x, y, 6.0, 0.55, WHITE, "D5D9E0");
    s.addText(f, { x: x + 0.2, y: y + 0.1, w: 5.6, h: 0.35, fontSize: 11, color: NAVY });
  });
  addFooter(s);
}

// ===== P14 愿景（深蓝收尾） =====
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.shapes.OVAL, { x: 9.8, y: 4.5, w: 5, h: 5, fill: { color: GOLD, transparency: 92 } });
  s.addText("从一个「撑得住的学生」开始，", { x: MARGIN, y: 2.2, w: 12, h: 0.8, fontSize: 32, color: WHITE, bold: true, align: "center", fontFace: "Microsoft YaHei" });
  s.addText("走向「每一所学校都有一位长期陪伴者」。", { x: MARGIN, y: 3.1, w: 12, h: 0.8, fontSize: 32, color: GOLD, bold: true, align: "center", fontFace: "Microsoft YaHei" });
  s.addShape(pres.shapes.RECTANGLE, { x: 5.6, y: 4.2, w: 2.1, h: 0.045, fill: { color: GOLD } });
  s.addText("PAEG · 让教育重新被看见", { x: MARGIN, y: 4.6, w: 12, h: 0.5, fontSize: 14, color: "D9DFE8", align: "center" });
  s.addText("www.paeg.example", { x: MARGIN, y: 6.6, w: 12, h: 0.3, fontSize: 11, color: "B8C4D6", align: "center" });
  pageNum++;
}

// ===== 保存主演示 =====
pres.writeFile({ fileName: OUT }).then(() => {
  console.log("主演示 P1-P14 已生成:", OUT);
}).catch(e => {
  console.error("生成失败:", e);
});
