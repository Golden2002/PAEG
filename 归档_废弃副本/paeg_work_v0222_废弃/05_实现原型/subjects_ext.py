"""
PAEG 学科知识扩展（v0.8.2）
15 学科体系 × 学段分层补充节点。
本文件以数据驱动方式批量注册节点，保持与 knowledge_base.py 一致的节点结构。

用法：在 KnowledgeBase._load_demo_data() 中调用 load_extended_subjects(self.subjects)
"""

# 学科扩展节点数据（subject.topic.concept -> 节点 dict）
# level: middle_school(初中) / high_school(高中) / undergraduate(本科)
# difficulty: 1-10（水平）

EXTENDED_SUBJECTS = {
    # ============ 语文（中学） ============
    "chinese.classical.poetry_reading": {
        "id": "chinese.classical.poetry_reading", "subject": "chinese", "topic": "classical",
        "concept": "poetry_reading", "level": "middle_school", "difficulty": 3,
        "definition": "读懂古诗的基本方法：疏通字词→理解意象→把握情感→赏析手法。",
        "intuition": "读诗像看画：先看清每个'颜色块'（意象），再看整幅画想表达什么情绪。",
        "explanation_variants": {
            "intuitive": "把'枯藤老树昏鸦'当成一幅画面来'看'",
            "formal": "意象是融入了主观情意的客观物象；意境是意象组合形成的整体氛围",
        },
        "common_misconceptions": ["以为逐字翻译就是读懂诗", "忽略题目与注释的提示作用"],
        "worldview_fit": {"1": 0.1, "2": 0.3, "3": 0.5, "4": 0.1},
    },
    "chinese.classical.essay_analysis": {
        "id": "chinese.classical.essay_analysis", "subject": "chinese", "topic": "classical",
        "concept": "essay_analysis", "level": "high_school", "difficulty": 5,
        "definition": "文言文阅读分析：实词虚词、句式、文意理解、内容概括与鉴赏。",
        "intuition": "文言文像'半懂的外语'：常用字词是词汇表，句式是语法，读懂后就能翻译成现代汉语。",
        "explanation_variants": {
            "intuitive": "把'之乎者也'当成'现代汉语的连接词'来理解功能",
            "formal": "文言句式：判断句/被动句/倒装句/省略句；实词活用：名作动/使动/意动",
        },
        "common_misconceptions": ["忽略古今异义（'妻子'≠现代'妻子'）", "不懂句式直接硬翻"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.4, "4": 0.1},
    },

    # ============ 政治（中学/考研） ============
    "politics.theory.marxism_basics": {
        "id": "politics.theory.marxism_basics", "subject": "politics", "topic": "theory",
        "concept": "marxism_basics", "level": "high_school", "difficulty": 4,
        "definition": "马克思主义基本原理：唯物论、辩证法、认识论、唯物史观的核心观点。",
        "intuition": "辩证法说'万物都在变，且因矛盾而变'；唯物史观说'社会发展的根本动力是生产力'。",
        "explanation_variants": {
            "intuitive": "用'一粒种子长成大树'理解质量互变：量变积累到一定程度发生质变",
            "formal": "对立统一规律是唯物辩证法的实质与核心；矛盾分析法是根本方法",
        },
        "common_misconceptions": ["把辩证法和'和稀泥'混为一谈", "记不住原理与方法的对应"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.4, "4": 0.1},
    },
    "politics.law.citizen_rights": {
        "id": "politics.law.citizen_rights", "subject": "politics", "topic": "law",
        "concept": "citizen_rights", "level": "middle_school", "difficulty": 2,
        "definition": "公民的基本权利与义务：人身权、财产权、受教育权、监督权等。",
        "intuition": "权利是你'可以做的事'，义务是你'应该做的事'，两者都受法律保护与约束。",
        "explanation_variants": {
            "intuitive": "用'借东西'理解权利与义务：你有使用权（权利），也要爱护归还（义务）",
            "formal": "权利与义务具有一致性：没有无义务的权利，也没有无权利的义务",
        },
        "common_misconceptions": ["以为权利可以放弃义务也可以不履行", "混淆'违法行为'与'犯罪行为'"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.3, "4": 0.2},
    },

    # ============ 历史学 ============
    "history.ancient.chinese_civilization": {
        "id": "history.ancient.chinese_civilization", "subject": "history", "topic": "ancient",
        "concept": "chinese_civilization", "level": "middle_school", "difficulty": 3,
        "definition": "中华文明起源与早期国家：从夏商周到春秋战国，分封制、宗法制、百家争鸣。",
        "intuition": "把分封制想成'老板把分公司交给亲戚管'，宗法制是'按血缘排继承顺序'。",
        "explanation_variants": {
            "intuitive": "周天子分封诸侯像'建立分公司网络'，诸侯再分封卿大夫",
            "formal": "分封制：授民授疆土；宗法制：嫡长子继承制；礼乐制：等级规范",
        },
        "common_misconceptions": ["混淆分封制与郡县制（分封世袭，郡县任免）", "忘记宗法制'嫡长子'的核心"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.4, "4": 0.1},
    },
    "history.modern.industrial_revolution": {
        "id": "history.modern.industrial_revolution", "subject": "history", "topic": "modern",
        "concept": "industrial_revolution", "level": "high_school", "difficulty": 5,
        "definition": "两次工业革命：蒸汽时代→电气时代，对生产力、社会结构与世界格局的影响。",
        "intuition": "第一次工业革命'机器代替手工'，第二次'电力代替蒸汽'，每次都是'能源+动力'的升级。",
        "explanation_variants": {
            "intuitive": "把工业革命想成'手机换代'：每次换代都改变生活方式和世界格局",
            "formal": "第一次：珍妮机→蒸汽机→工厂制度；第二次：电力/内燃机→垄断组织→瓜分世界",
        },
        "common_misconceptions": ["忽略工业革命对'社会结构'（无产阶级）的影响", "记不清两次革命的关键发明"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },

    # ============ 英语 ============
    "english.grammar.tenses": {
        "id": "english.grammar.tenses", "subject": "english", "topic": "grammar",
        "concept": "tenses", "level": "middle_school", "difficulty": 3,
        "definition": "英语时态体系：一般现在时、一般过去时、现在进行时、一般将来时等基本用法。",
        "intuition": "时态 = 时间（现在/过去/将来）× 状态（一般/进行/完成）。先定时间轴，再选状态。",
        "explanation_variants": {
            "intuitive": "把'时间轴'画出来：时态就是'在哪段时间 + 动作处于什么状态'",
            "formal": "现在完成时 have done：过去发生对现在有影响；过去完成时 had done：过去的过去",
        },
        "common_misconceptions": ["混淆一般过去时与现在完成时", "忘记第三人称单数加s"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },
    "english.writing.argumentation": {
        "id": "english.writing.argumentation", "subject": "english", "topic": "writing",
        "concept": "argumentation", "level": "high_school", "difficulty": 5,
        "definition": "英语议论文写作：论点句、段落结构（topic sentence + supporting details）、衔接词。",
        "intuition": "英语议论文像'三明治'：开头论点（上层），中间论据（夹心），结尾总结（底层）。",
        "explanation_variants": {
            "intuitive": "每段第一句是'观点'，后面是'证据+解释'，用 First/Second/However 衔接",
            "formal": "TEE结构：Topic sentence → Evidence → Explanation；注意连接词与句式多样性",
        },
        "common_misconceptions": ["整篇没有主题句", "衔接词滥用或缺失", "中式英语（Chinglish）直译"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.3, "4": 0.2},
    },

    # ============ 法语 ============
    "french.basics.pronunciation": {
        "id": "french.basics.pronunciation", "subject": "french", "topic": "basics",
        "concept": "pronunciation", "level": "middle_school", "difficulty": 2,
        "definition": "法语发音基础：字母读音、元音辅音、鼻化元音、连诵（liaison）。",
        "intuition": "法语发音规则很规律：看到字母组合基本能读对，不像英语那么多例外。",
        "explanation_variants": {
            "intuitive": "法语'怎么说就怎么写'（大体上）：学会字母组合规律就能读",
            "formal": "鼻化元音 an/on/in/un；连诵：辅音结尾的词后接元音开头的词时发音",
        },
        "common_misconceptions": ["用英语发音习惯读法语", "忽略连诵规则导致句子读不连贯"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.3, "4": 0.2},
    },

    # ============ 德语 ============
    "german.basics.verb_position": {
        "id": "german.basics.verb_position", "subject": "german", "topic": "basics",
        "concept": "verb_position", "level": "high_school", "difficulty": 4,
        "definition": "德语句框结构：动词在陈述句中居第二位，从句动词放句末，可分动词的框架。",
        "intuition": "德语像'把动词钉在句子里'：主句动词永远第二位，从句动词放最后。",
        "explanation_variants": {
            "intuitive": "把德语动词想成'句子的核心枢纽'：主句枢纽在第二位，从句枢纽在句尾",
            "formal": "主句：动词第二位（V2）；从句：动词置于句末；可分前缀与动词形成句框",
        },
        "common_misconceptions": ["动词位置错乱", "忽略可分动词的框架结构"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },

    # ============ 日语 ============
    "japanese.basics.hiragana": {
        "id": "japanese.basics.hiragana", "subject": "japanese", "topic": "basics",
        "concept": "hiragana", "level": "middle_school", "difficulty": 2,
        "definition": "五十音图（平假名）与基本发音：清音、浊音、拗音、长音、促音。",
        "intuition": "五十音像'日语的拼音'：先背熟它，之后所有单词都能读出来。",
        "explanation_variants": {
            "intuitive": "把五十音当'ABC'背：行（あかさたな…）× 段（あいうえお）",
            "formal": "清音46个 + 浊音20个 + 拗音36个；长音表拉长，促音表停顿",
        },
        "common_misconceptions": ["跳过五十音直接记单词", "混淆平假名与片假名（外来语用片假名）"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.3, "4": 0.2},
    },

    # ============ 哲学 ============
    "philosophy.epistemology.knowledge": {
        "id": "philosophy.epistemology.knowledge", "subject": "philosophy", "topic": "epistemology",
        "concept": "knowledge", "level": "undergraduate", "difficulty": 6,
        "definition": "知识的定义：被辩护的真信念（JTB），以及葛梯尔问题对它的挑战。",
        "intuition": "'知道'不只是'相信且为真'，还得'有理由'——但葛梯尔说这还不够。",
        "explanation_variants": {
            "intuitive": "你'知道'答案了吗？要满足三条件：是真的、你相信、你有依据",
            "formal": "JTB：Justified True Belief；葛梯尔反例：合理但错误的证据导致'碰巧为真'",
        },
        "common_misconceptions": ["把'相信'当'知道'", "忽略'辩护'（理由）这一条件"],
        "worldview_fit": {"1": 0.2, "2": 0.4, "3": 0.3, "4": 0.1},
    },

    # ============ 美学 ============
    "aesthetics.art.interpretation": {
        "id": "aesthetics.art.interpretation", "subject": "aesthetics", "topic": "art",
        "concept": "interpretation", "level": "undergraduate", "difficulty": 5,
        "definition": "艺术作品的解读：形式分析、内容阐释、语境理解，以及'作者意图'问题。",
        "intuition": "看一幅画，先看'怎么画的'（形式），再想'表达了什么'（内容），最后想'为什么这样画'（语境）。",
        "explanation_variants": {
            "intuitive": "像'破案'：形式是现场，内容是动机，语境是时代背景",
            "formal": "形式主义：重构成；意图谬误：作品意义≠作者意图；接受美学：读者参与建构",
        },
        "common_misconceptions": ["只凭'像不像'评判艺术", "把解读等同于'作者想表达什么'"],
        "worldview_fit": {"1": 0.2, "2": 0.2, "3": 0.5, "4": 0.1},
    },

    # ============ 化学 ============
    "chemistry.basics.chemical_reaction": {
        "id": "chemistry.basics.chemical_reaction", "subject": "chemistry", "topic": "basics",
        "concept": "chemical_reaction", "level": "middle_school", "difficulty": 3,
        "definition": "化学反应的特征：有新物质生成；伴随现象（放热/变色/沉淀/气体）。",
        "intuition": "化学反应 = '物质变身'：铁生锈、蜡烛燃烧，都是生成了新物质。",
        "explanation_variants": {
            "intuitive": "把'新物质生成'当判据：糖溶水是物理变化（还能变回糖），纸燃烧是化学变化",
            "formal": "化学变化本质：原子重新组合，分子种类改变；伴随能量变化",
        },
        "common_misconceptions": ["把'冒泡'全当化学变化（沸腾是物理变化）", "忽略'新物质'这一本质判据"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },
    "chemistry.inorganic.acid_base": {
        "id": "chemistry.inorganic.acid_base", "subject": "chemistry", "topic": "inorganic",
        "concept": "acid_base", "level": "high_school", "difficulty": 5,
        "definition": "酸碱理论：酸碱指示剂、pH、酸碱反应（中和）、电离。",
        "intuition": "酸是'给质子'的，碱是'收质子'的；酸碱中和像'互相抵消'。",
        "explanation_variants": {
            "intuitive": "把酸碱想成'性格相反的两个角色'：一见面就'中和'，pH 趋近 7",
            "formal": "阿伦尼乌斯：酸电离出H+，碱电离出OH-；质子论：酸是质子给予体",
        },
        "common_misconceptions": ["混淆'浓度'与'强弱'（浓盐酸≠强酸）", "pH 计算忽略水的电离"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },

    # ============ 生物学 ============
    "biology.cell.structure": {
        "id": "biology.cell.structure", "subject": "biology", "topic": "cell",
        "concept": "structure", "level": "middle_school", "difficulty": 3,
        "definition": "细胞的基本结构：细胞膜、细胞质、细胞核（真核）；动植物细胞差异。",
        "intuition": "细胞像'微型工厂'：细胞膜是围墙，细胞核是厂长办公室，线粒体是发电厂。",
        "explanation_variants": {
            "intuitive": "把细胞当'工厂'：各细胞器各司其职，细胞核发号施令",
            "formal": "细胞膜：选择透过性；线粒体：有氧呼吸主要场所；叶绿体：光合作用场所（植物）",
        },
        "common_misconceptions": ["以为所有细胞都有细胞核（原核没有）", "混淆动植物细胞特有结构"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },
    "biology.genetics.mendel": {
        "id": "biology.genetics.mendel", "subject": "biology", "topic": "genetics",
        "concept": "mendel", "level": "high_school", "difficulty": 5,
        "definition": "孟德尔遗传定律：分离定律与自由组合定律，显隐性、配子、基因型与表现型。",
        "intuition": "遗传像'抽签'：每个性状由一对'基因签'决定，配子随机各取一个。",
        "explanation_variants": {
            "intuitive": "豌豆高茎×矮茎→子一代全高：显性'盖过'隐性，子二代 3:1",
            "formal": "分离定律：等位基因随同源染色体分离；自由组合：非同源染色体上的基因独立分配",
        },
        "common_misconceptions": ["把'显性'理解为'常见'", "计算概率时漏掉配子组合"],
        "worldview_fit": {"1": 0.1, "2": 0.5, "3": 0.3, "4": 0.1},
    },

    # ============ 地理学 ============
    "geography.climate.weather_climate": {
        "id": "geography.climate.weather_climate", "subject": "geography", "topic": "climate",
        "concept": "weather_climate", "level": "middle_school", "difficulty": 3,
        "definition": "天气与气候的区别；影响气候的主要因素：纬度、海陆、地形、洋流。",
        "intuition": "天气是'今天的心情'（多变），气候是'一个地方的性格'（长期稳定）。",
        "explanation_variants": {
            "intuitive": "天气=短时间的大气状态；气候=长时间的平均与变化规律",
            "formal": "纬度→热量；海陆→水汽与温差；地形→海拔与坡向；洋流→增温增湿/降温减湿",
        },
        "common_misconceptions": ["混淆天气与气候", "忽略多个因素的综合作用"],
        "worldview_fit": {"1": 0.1, "2": 0.4, "3": 0.4, "4": 0.1},
    },

    # ============ 数学补充分层 ============
    "math.geometry.triangle": {
        "id": "math.geometry.triangle", "subject": "math", "topic": "geometry",
        "concept": "triangle", "level": "middle_school", "difficulty": 3,
        "definition": "三角形基础：内角和180°、全等判定（SSS/SAS/ASA/AAS/HL）、勾股定理。",
        "intuition": "三角形是'最稳定的形状'：三边确定，形状就唯一（这就是全等的道理）。",
        "explanation_variants": {
            "intuitive": "全等=两个三角形'完全重合'；勾股定理=直角边的平方和=斜边平方",
            "formal": "全等判定本质：确定一个三角形所需的最少独立条件",
        },
        "common_misconceptions": ["SSA 不是全等判定（角不是夹角时）", "勾股定理忘了是'斜边'最大"],
        "worldview_fit": {"1": 0.05, "2": 0.7, "3": 0.1, "4": 0.15},
    },
    "math.calculus.limit": {
        "id": "math.calculus.limit", "subject": "math", "topic": "calculus",
        "concept": "limit", "level": "high_school", "difficulty": 6,
        "definition": "极限的定义与运算：数列极限、函数极限、ε-δ 语言、无穷小与两个重要极限。",
        "intuition": "极限是'无限逼近但不一定到达'：让 x 越来越靠近 a，f(x) 越来越靠近 L。",
        "explanation_variants": {
            "intuitive": "极限像'追着目标跑'：无论你要多近（ε），我都能让你更近（δ）",
            "formal": "ε-δ 定义：∀ε>0，∃δ>0，使 0<|x-a|<δ 时 |f(x)-L|<ε",
        },
        "common_misconceptions": ["把极限当'代入'（0/0 不能直接代）", "混淆'极限存在'与'函数有定义'"],
        "worldview_fit": {"1": 0.05, "2": 0.7, "3": 0.1, "4": 0.15},
    },

    # ============ 物理学补充分层 ============
    "physics.mechanics.newton_laws": {
        "id": "physics.mechanics.newton_laws", "subject": "physics", "topic": "mechanics",
        "concept": "newton_laws", "level": "high_school", "difficulty": 5,
        "definition": "牛顿三定律：惯性、F=ma、作用力与反作用力，及受力分析。",
        "intuition": "牛顿第一定律说'没人推你就停不下来'（惯性）；第二定律说'力越大、动得越快'。",
        "explanation_variants": {
            "intuitive": "推购物车：轻车好推（a=F/m），重车难推——这就是 F=ma",
            "formal": "F=ma：合力等于质量×加速度；第三定律：力总是成对出现（大小相等方向相反）",
        },
        "common_misconceptions": ["混淆作用力与反作用力（作用在不同物体上）", "忽略摩擦力/重力等'隐形'力"],
        "worldview_fit": {"1": 0.05, "2": 0.7, "3": 0.1, "4": 0.15},
    },
}


def load_extended_subjects(subjects: dict):
    """把扩展学科节点注册进 knowledge_base.subjects。"""
    for nid, node in EXTENDED_SUBJECTS.items():
        subjects[nid] = node
