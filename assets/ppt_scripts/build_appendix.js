// PAEG 路演 PPT v8 附录部分（P15-P54：A/B/C/D/E 章节）
// 在已生成的 v8 基础上追加 —— 用 pptxgenjs 一次性生成全部（主演示 + 附录）
const pptxgen = require("pptxgenjs");
const path = require("path");
const fs = require("fs");

const BASE = "C:/Users/团聚体/AppData/Local/Temp/opencode";
const OUT = path.join(BASE, "PAEG路演PPT_v8_full.pptx");

const NAVY = "0F2A52";
const GOLD = "E6A528";
const CREAM = "F5F2EC";
const GRAY = "555F6B";
const WHITE = "FFFFFF";
const MARGIN = 0.5;
const CONTENT_W = 13.33 - MARGIN * 2;

// ===== 数据加载 =====
const teachData = JSON.parse(fs.readFileSync(path.join(BASE, "appendix_dialogue.json"), "utf-8"));
const answerData = JSON.parse(fs.readFileSync(path.join(BASE, "answer_10q.json"), "utf-8"));
const teach = teachData.teach_15;
const aff = teachData.affection_15;

// ===== 工具 =====
let pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.author = "PAEG";
pres.title = "PAEG 路演";

let pageNum = 0;

function cleanMd(t) {
  if (!t) return t;
  return t
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/^#{1,6}\s*/gm, "")
    .replace(/`([^`]*)`/g, "$1")
    .replace(/\$\$(.+?)\$\$/g, "$1")
    .replace(/\$(.+?)\$/g, "$1")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/^\s*[-*]\s+/gm, "\u2022 ");
}

function addFooter(slide) {
  pageNum++;
  slide.addText("PAEG 教育者 Agent · v8 · 2026.08", { x: MARGIN, y: 7.12, w: 5, h: 0.25, fontSize: 8, color: GRAY });
  slide.addText(String(pageNum), { x: 12.5, y: 7.12, w: 0.5, h: 0.25, fontSize: 8, color: GRAY, align: "right" });
}

function addAppHeader(slide, tag, title, sub) {
  slide.background = { color: CREAM };
  // 深蓝头条（不用强调线）
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: 13.33, h: 1.15, fill: { color: NAVY } });
  slide.addText(tag, { x: MARGIN, y: 0.12, w: 2.5, h: 0.4, fontSize: 13, color: GOLD, bold: true, charSpacing: 2 });
  slide.addText(title, { x: MARGIN, y: 0.4, w: 12, h: 0.6, fontSize: 24, color: WHITE, bold: true, fontFace: "Microsoft YaHei" });
  slide.addText(sub, { x: MARGIN, y: 0.82, w: 12, h: 0.3, fontSize: 10, color: "C9D2E0" });
}

function addCard(slide, x, y, w, h, fill) {
  return slide.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, fill: { color: fill }, rectRadius: 0.05 });
}

// 计算文本所需高度（估算）
function textHeight(text, widthIn, fontSize) {
  const charsPerLine = Math.max(4, Math.floor(widthIn / (fontSize * 0.014)));
  let lines = 0;
  text.split("\n").forEach(para => {
    lines += Math.max(1, Math.ceil(para.length / charsPerLine));
  });
  return lines * fontSize * 0.018;
}

// ===== P15 附录封面 =====
{
  const s = pres.addSlide();
  s.background = { color: NAVY };
  s.addShape(pres.shapes.OVAL, { x: 10, y: -2, w: 6, h: 6, fill: { color: WHITE, transparency: 95 } });
  s.addText("APPENDIX", { x: MARGIN, y: 1.2, w: 6, h: 0.5, fontSize: 16, color: GOLD, bold: true, charSpacing: 4 });
  s.addText("PAEG 全功能实测记录", { x: MARGIN, y: 1.8, w: 11, h: 0.9, fontSize: 36, color: WHITE, bold: true, fontFace: "Microsoft YaHei" });
  s.addText("Full-Feature Empirical Record", { x: MARGIN + 0.05, y: 2.7, w: 8, h: 0.4, fontSize: 13, color: "C9D2E0" });
  s.addShape(pres.shapes.RECTANGLE, { x: MARGIN + 0.02, y: 3.3, w: 2.0, h: 0.045, fill: { color: GOLD } });
  s.addText([
    { text: "30 场对话 · 10 题答案 · 3 类查资料 · 扩展测试\n", options: { fontSize: 14, color: "FFFFFF", breakLine: true } },
    { text: "教学视频 · PPT 产出 · 全功能能力矩阵", options: { fontSize: 14, color: "C9D2E0" } }
  ], { x: MARGIN, y: 3.7, w: 10, h: 0.8 });
  // 目录索引
  s.addText("附录章节索引", { x: MARGIN, y: 4.8, w: 4, h: 0.4, fontSize: 14, color: GOLD, bold: true });
  const index = [
    "A 教学 15 轮完整原文  ·  B 倾诉 15 轮完整原文",
    "C 找答案 10 题完整答案  ·  D 查资料 3 场景",
    "E 扩展测试  ·  F 产出物（视频/PPT）",
    "G 数据全景  ·  H 能力矩阵  ·  I 8层约束",
    "J 语言规范  ·  K 检索增强  ·  L 个体化画像",
    "M 自我进化  ·  N 语音  ·  O 导图/文件4能力",
    "P 测试体系  ·  Q 测试数据  ·  R/S 实测  ·  T 版本时间线"
  ];
  index.forEach((line, i) => {
    s.addText(line, { x: MARGIN, y: 5.3 + i * 0.28, w: 12, h: 0.25, fontSize: 10, color: "FFFFFFAA".replace("AA", ""), transparency: 30 });
  });
  pageNum++;
}

// ===== P16-20 附录 A：教学 15 轮完整原文（5 页，每页 3 轮） =====
const A_GROUPS = [
  { label: "A1", rounds: [0, 1, 2], title: "导入/新授" },
  { label: "A2", rounds: [3, 4, 5], title: "巩固/复习" },
  { label: "A3", rounds: [6, 7, 8], title: "提高/应用" },
  { label: "A4", rounds: [9, 10, 11], title: "应用/总结" },
  { label: "A5", rounds: [12, 13, 14], title: "复习/挑战" }
];
A_GROUPS.forEach((grp, gi) => {
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX " + grp.label, "教学 15 轮完整原文 · 孟德尔遗传", grp.title + " — 每轮完整原文 + UI 截图");
  // 3 轮，每轮 1.7in 高
  grp.rounds.forEach((ri, i) => {
    const r = teach[ri];
    const y = 1.35 + i * 1.75;
    addCard(s, MARGIN, y, 9.7, 1.6, WHITE);
    s.addText(r.round.split(" ")[0], { x: MARGIN + 0.2, y: y + 0.08, w: 1.0, h: 0.3, fontSize: 13, color: GOLD, bold: true });
    const cleanContent = cleanMd(r.content);
    s.addText(cleanContent, { x: MARGIN + 1.3, y: y + 0.1, w: 8.2, h: 1.4, fontSize: 10.5, color: GRAY, lineSpacingMultiple: 1.15 });
    s.addText(r.chars + "字", { x: MARGIN + 8.8, y: y + 1.35, w: 0.8, h: 0.2, fontSize: 8, color: GOLD, align: "right" });
  });
  // 右侧竖屏截图（1725:2282 原始比例）
  const imgH = 4.9, imgW = imgH * (1725 / 2282);
  s.addImage({ path: "D:/wbo-workspace/v51_teach_hd.png", x: 10.4, y: 1.35, w: imgW, h: imgH, sizing: { type: "contain", w: imgW, h: imgH } });
  s.addText("实际界面 · 1725×2282", { x: 10.2, y: 6.35, w: 1.6, h: 0.25, fontSize: 7, color: GRAY, align: "center" });
  addFooter(s);
});

// ===== P21-28 附录 B：倾诉 15 轮完整原文（8 页，每页 2 轮） =====
const B_GROUPS = [
  { label: "B1", rounds: [0, 1] }, { label: "B2", rounds: [2, 3] },
  { label: "B3", rounds: [4, 5] }, { label: "B4", rounds: [6, 7] },
  { label: "B5", rounds: [8, 9] }, { label: "B6", rounds: [10, 11] },
  { label: "B7", rounds: [12, 13] }, { label: "B8", rounds: [14] }
];
B_GROUPS.forEach((grp, gi) => {
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX " + grp.label, "倾诉 15 轮完整原文 · 学业压力", "完整原文 + UI 截图（转学适应 · 从崩溃到承诺）");
  grp.rounds.forEach((ri, i) => {
    const r = aff[ri];
    const y = 1.35 + i * 2.6;
    addCard(s, MARGIN, y, 9.7, 2.4, WHITE);
    s.addText(r.round.split(" ")[0], { x: MARGIN + 0.2, y: y + 0.08, w: 1.0, h: 0.3, fontSize: 13, color: GOLD, bold: true });
    const cleanContent = cleanMd(r.content);
    s.addText(cleanContent, { x: MARGIN + 1.3, y: y + 0.1, w: 8.2, h: 2.2, fontSize: 10.5, color: GRAY, lineSpacingMultiple: 1.15 });
    s.addText(r.chars + "字", { x: MARGIN + 8.8, y: y + 2.15, w: 0.8, h: 0.2, fontSize: 8, color: GOLD, align: "right" });
  });
  const imgH = 4.9, imgW = imgH * (1532 / 2282);
  s.addImage({ path: "D:/wbo-workspace/v51_aff_hd.png", x: 10.4, y: 1.35, w: imgW, h: imgH, sizing: { type: "contain", w: imgW, h: imgH } });
  s.addText("实际界面 · 1532×2282", { x: 10.2, y: 6.35, w: 1.6, h: 0.25, fontSize: 7, color: GRAY, align: "center" });
  addFooter(s);
});

// ===== P29-33 附录 C：找答案 10 题（5 页，每页 2 题） =====
for (let ci = 0; ci < 5; ci++) {
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX C" + (ci + 1), "找答案完整答案 · 每页 2 题", "论述/计算/证明 · 完整答案原文");
  const items = answerData.slice(ci * 2, ci * 2 + 2);
  let top = 1.4;
  items.forEach(item => {
    // 题目条
    addCard(s, MARGIN, top, CONTENT_W, 0.5, WHITE);
    s.addText("[" + item.type + "/" + item.subject + "] " + item.question, { x: MARGIN + 0.2, y: top + 0.06, w: CONTENT_W - 0.4, h: 0.4, fontSize: 13, color: NAVY, bold: true, fontFace: "Microsoft YaHei" });
    s.addText("答案 " + item.chars + " 字 · 耗时 " + item.time + "s", { x: MARGIN, y: top + 0.02, w: CONTENT_W - 0.2, h: 0.2, fontSize: 8, color: GOLD, align: "right" });
    top += 0.55;
    // 答案全文
    const cleanAns = cleanMd(item.answer);
    const h = Math.min(2.2, textHeight(cleanAns, CONTENT_W - 0.6, 10) + 0.2);
    s.addText(cleanAns, { x: MARGIN + 0.3, y: top, w: CONTENT_W - 0.6, h: h, fontSize: 10, color: GRAY, lineSpacingMultiple: 1.15 });
    top += h + 0.25;
  });
  addFooter(s);
}

// ===== P34-36 附录 D：查资料 3 场景 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX D1", "查资料 · 哲学入门书籍推荐", "RRF 融合 + 知识库 + 网络 sources");
  addCard(s, MARGIN, 1.5, CONTENT_W, 1.0, WHITE);
  s.addText("查询：「哲学入门书籍推荐」 → n=2 条结果", { x: MARGIN + 0.3, y: 1.65, w: 11, h: 0.4, fontSize: 13, color: NAVY, bold: true });
  s.addText("检索链路：知识库哲学书单 → 网络补充 → RRF 融合 → 推荐 2 本入门书", { x: MARGIN + 0.3, y: 2.1, w: 11, h: 0.3, fontSize: 11, color: GRAY });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX D2", "查资料 · 物理竞赛学习方法", "RRF 融合 + URL 规范化 + 6 条 sources");
  addCard(s, MARGIN, 1.5, CONTENT_W, 1.0, WHITE);
  s.addText("查询：「物理竞赛学习方法」 → n=6 条结果", { x: MARGIN + 0.3, y: 1.65, w: 11, h: 0.4, fontSize: 13, color: NAVY, bold: true });
  s.addText("检索链路：知识库 + 网络（竞赛经验帖）→ URL 规范化去重 → 融合出 6 条高相关", { x: MARGIN + 0.3, y: 2.1, w: 11, h: 0.3, fontSize: 11, color: GRAY });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX D3", "查资料 · 英语单词记忆技巧", "jieba 切词 + 词根词缀 sources 卡片");
  addCard(s, MARGIN, 1.5, CONTENT_W, 1.0, WHITE);
  s.addText("查询：「英语单词记忆技巧」 → n=6 条结果", { x: MARGIN + 0.3, y: 1.65, w: 11, h: 0.4, fontSize: 13, color: NAVY, bold: true });
  s.addText("检索链路：jieba 切词提升命中 → 词根词缀 + 记忆法 sources 卡片", { x: MARGIN + 0.3, y: 2.1, w: 11, h: 0.3, fontSize: 11, color: GRAY });
  addFooter(s);
}

// ===== P37-40 附录 E：扩展测试 =====
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX E1", "扩展测试 · 教学：生态系统能量流动", "新场景验证 · 17 维画像闭环");
  addCard(s, MARGIN, 1.5, CONTENT_W, 4.5, WHITE);
  s.addText("教学扩展：从「能量从哪来」导入 → 生产者/消费者/分解者 → 能量金字塔 → 10% 传递效率 → 独立计算题", { x: MARGIN + 0.3, y: 1.8, w: 11, h: 1.5, fontSize: 13, color: NAVY, lineSpacingMultiple: 1.4 });
  s.addText("全部通过 · 17 维画像闭环生效", { x: MARGIN + 0.3, y: 3.6, w: 11, h: 0.5, fontSize: 14, color: GOLD, bold: true });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX E2", "扩展测试 · 教学：电磁感应", "新场景验证 · 确定性评估");
  addCard(s, MARGIN, 1.5, CONTENT_W, 4.5, WHITE);
  s.addText("教学扩展：从「发电机原理」导入 → 磁通量变化 → 感应电流方向（楞次定律）→ 应用实例 → 独立判断题", { x: MARGIN + 0.3, y: 1.8, w: 11, h: 1.5, fontSize: 13, color: NAVY, lineSpacingMultiple: 1.4 });
  s.addText("评估用确定性启发式，可复现", { x: MARGIN + 0.3, y: 3.6, w: 11, h: 0.5, fontSize: 14, color: GOLD, bold: true });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX E3", "扩展测试 · 倾诉：与朋友吵架", "危机协议验证 · 先回应再关怀");
  addCard(s, MARGIN, 1.5, CONTENT_W, 4.5, WHITE);
  s.addText("倾诉扩展：情绪识别 → 先回应感受 → 澄清事实 → 帮助看见矛盾 → 稳定后回归", { x: MARGIN + 0.3, y: 1.8, w: 11, h: 1.5, fontSize: 13, color: NAVY, lineSpacingMultiple: 1.4 });
  s.addText("危机信号先回应，不机械短路", { x: MARGIN + 0.3, y: 3.6, w: 11, h: 0.5, fontSize: 14, color: GOLD, bold: true });
  addFooter(s);
}
{
  const s = pres.addSlide();
  addAppHeader(s, "APPENDIX E4", "扩展测试 · 倾诉：自我怀疑迷茫", "价值观落地 · 陪伴式成长");
  addCard(s, MARGIN, 1.5, CONTENT_W, 4.5, WHITE);
  s.addText("倾诉扩展：从「我是不是有问题」→ 看见矛盾张力 → 认知真实 → 邀请重新站立", { x: MARGIN + 0.3, y: 1.8, w: 11, h: 1.5, fontSize: 13, color: NAVY, lineSpacingMultiple: 1.4 });
  s.addText("不教、不答、不解决，以注意力陪伴", { x: MARGIN + 0.3, y: 3.6, w: 11, h: 0.5, fontSize: 14, color: GOLD, bold: true });
  addFooter(s);
}

// ===== 保存 =====
pres.writeFile({ fileName: OUT }).then(() => {
  console.log("附录 A-E 已追加，总文件:", OUT);
}).catch(e => console.error("失败:", e));
