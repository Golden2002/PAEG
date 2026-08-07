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

    # ============ 语言学（v0.25 · 6 层体系） ============
    "linguistics.foundation.symbol_system": {
        "id": "linguistics.foundation.symbol_system", "subject": "linguistics", "topic": "foundation",
        "concept": "symbol_system", "level": "middle_school", "difficulty": 2,
        "definition": "语言是符号系统：任意性（音义结合无必然联系）、线条性（线性排列）、组合关系与聚合关系、语言与言语的区别。",
        "intuition": "任意性：'狗'和'dog'都指同一个动物，但声音完全不同——说明音义没有必然联系，是约定俗成。组合与聚合像'搭积木'：横着拼（组合），竖着换（聚合）。",
        "explanation_variants": {
            "intuitive": "用'红绿灯'理解符号：红灯'=停'是约定，不是红灯本身有'停'的意思",
            "formal": "索绪尔：语言符号由能指（音响形象）与所指（概念）结合而成；组合关系是句段上的线性排列，聚合关系是同一位置可替换的联想",
        },
        "common_misconceptions": ["以为'象声词'反驳任意性（拟声词只占极小部分）", "混淆'语言'（langue）与'言语'（parole）"],
        "worldview_fit": {"1": 0.2, "2": 0.5, "3": 0.2, "4": 0.1},
    },
    "linguistics.phonetics.ipa": {
        "id": "linguistics.phonetics.ipa", "subject": "linguistics", "topic": "phonetics",
        "concept": "ipa", "level": "high_school", "difficulty": 4,
        "definition": "语音学与音系学：国际音标（IPA）、发音器官、元音/辅音分类（发音部位/方式）、音位与音位变体、对立与互补、区别特征。",
        "intuition": "音位像'声调的身份证'：一个音位可以有多个'长相不同但算同一个人'的变体（音位变体）。对立（换一个音就换一个词）说明它们是不同音位。",
        "explanation_variants": {
            "intuitive": "用'身份证'理解：n 在不同词里发音略不同（变体），但都是同一个'人'（音位）",
            "formal": "最小对立对（minimal pair）：/p/ 与 /b/ 在 pin/bin 中对立 → 不同音位；互补分布 → 同一音位的条件变体",
        },
        "common_misconceptions": ["混淆'字母'与'音素'（字母是书写，音素是语音）", "以为音位变体是'发音错误'"],
        "worldview_fit": {"1": 0.15, "2": 0.6, "3": 0.15, "4": 0.1},
    },
    "linguistics.grammar.syntax_tree": {
        "id": "linguistics.grammar.syntax_tree", "subject": "linguistics", "topic": "grammar",
        "concept": "syntax_tree", "level": "high_school", "difficulty": 5,
        "definition": "语法：语法单位（语素/词/短语/句子）、组合规则与聚合规则、句法层次性与句法树形图、语言结构类型（孤立语/屈折语/黏着语）。",
        "intuition": "句法树像'家族谱系图'：'我爱语言学'不是三个词平排，而是'我'+'爱语言学'（主谓），'爱语言学'又分'爱'+'语言学'（动宾）——层层嵌套。",
        "explanation_variants": {
            "intuitive": "把句子当'俄罗斯套娃'：大结构里套小结构，每层都有主谓/动宾关系",
            "formal": "句法树形图：NP(我) + VP(V 爱 + NP 语言学)；递归性：一个成分里可以再嵌同类成分",
        },
        "common_misconceptions": ["把语法当'规则背诵'（其实是结构分析）", "混淆'词类'（词的性质）与'句子成分'（词的句法角色）"],
        "worldview_fit": {"1": 0.1, "2": 0.65, "3": 0.15, "4": 0.1},
    },
    "linguistics.semantics.speech_act": {
        "id": "linguistics.semantics.speech_act", "subject": "linguistics", "topic": "semantics",
        "concept": "speech_act", "level": "undergraduate", "difficulty": 5,
        "definition": "语义与语用：词义关系（多义/同义/反义/上下位/语义场）、句义（蕴涵/预设/真值）、语用（语境/话题与说明/焦点/言语行为理论）。",
        "intuition": "言语行为：'你能把窗户关了吗？'字面是问能力（言内），实际是请求（言外）——一句话同时在做三件事：说、指、行。",
        "explanation_variants": {
            "intuitive": "用'请客'理解：'这杯茶真不错'在饭局上常是'再给我倒一杯'的暗示——语境决定言外之意",
            "formal": "奥斯汀：言内行为（locution）/言外行为（illocution）/言后行为（perlocution）；格赖斯合作原则与含义推导",
        },
        "common_misconceptions": ["把'语义'与'语用'混为一谈（语义是字面，语用是语境）", "以为'预设'就是'含义'"],
        "worldview_fit": {"1": 0.15, "2": 0.5, "3": 0.25, "4": 0.1},
    },
    "linguistics.writing.chinese_characters": {
        "id": "linguistics.writing.chinese_characters", "subject": "linguistics", "topic": "writing",
        "concept": "chinese_characters", "level": "undergraduate", "difficulty": 4,
        "definition": "文字与书面语：文字的基本性质（记录语言）、文字类型（意音文字/表音文字）、汉字的特点与发展、口语与书面语的关系。",
        "intuition": "文字是'语言的照相'：汉字直接'照'意义（象形/会意），拼音文字'照'声音（表音）——两种不同的'拍照方式'。",
        "explanation_variants": {
            "intuitive": "用'照片 vs 录音'理解：汉字像照片（记形义），拼音像录音（记声音）",
            "formal": "意音文字：兼表音义（汉字）；表音文字：音节文字（日文假名）/音位文字（英文）；文字相对独立于语言",
        },
        "common_misconceptions": ["以为文字'等于'语言（文字是语言的再编码）", "把'简体繁体'当'不同语言'"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },
    "linguistics.change.contact": {
        "id": "linguistics.change.contact", "subject": "linguistics", "topic": "change",
        "concept": "contact", "level": "undergraduate", "difficulty": 6,
        "definition": "语言演变与接触：语言分化（社会方言/地域方言/亲属语言/谱系分类）、语言接触（借词/语言联盟/洋泾浜与混合语）、语音演变规律与历史比较法。",
        "intuition": "语言像'河流'：源头同一条（共同祖先），分叉成不同支流（方言/亲属语言）；两河交汇会'混水'（语言接触/借词）。",
        "explanation_variants": {
            "intuitive": "用'家族树'理解谱系：汉语/藏语同属汉藏语系，像兄弟姐妹从同一个'语言祖父母'分化",
            "formal": "历史比较法：通过语音对应规律重建祖语；语法化：实词虚化（'把'从动词到介词）；洋泾浜→克里奥尔语",
        },
        "common_misconceptions": ["以为方言是'错误的普通话'（方言有完整系统）", "混淆'语言接触'与'语言谱系'"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },
    "linguistics.applied.computational": {
        "id": "linguistics.applied.computational", "subject": "linguistics", "topic": "applied",
        "concept": "computational", "level": "undergraduate", "difficulty": 6,
        "definition": "应用语言学与计算语言学导览：语料库语言学、语言习得（母语/二语）、语言与认知、计算语言学（N-gram/词性标注/依存分析）、语言学在 LLM 中的价值（tokenization/语法结构理解）。",
        "intuition": "计算语言学让电脑'看懂语言'：把语言当数据（语料库），用统计找规律（N-gram）——这也解释了为什么大模型能'懂'语言。",
        "explanation_variants": {
            "intuitive": "用'统计'理解 N-gram：'吃了'后面更可能跟'饭'而不是'桌子'——模型靠大量语料的概率搭配",
            "formal": "语料库驱动学习（DDL）：真实语料中发现语言规律；计算语言学：分词/词性标注/依存句法分析/机器翻译",
        },
        "common_misconceptions": ["以为语言模型'真正理解'（统计规律 ≠ 语义理解）", "把计算语言学当'纯编程'（核心是语言学建模）"],
        "worldview_fit": {"1": 0.2, "2": 0.5, "3": 0.2, "4": 0.1},
    },

    # ============ 大气科学（v0.25 · 7 层体系） ============
    "atmospheric_science.structure.layers": {
        "id": "atmospheric_science.structure.layers", "subject": "atmospheric_science", "topic": "structure",
        "concept": "layers", "level": "middle_school", "difficulty": 2,
        "definition": "大气垂直分层：对流层（天气现象所在，随高度降温）、平流层（臭氧层，气流平稳）、中间层、热层；太阳辐射与地面辐射、温室效应。",
        "intuition": "大气像'多层蛋糕'：最下面一层（对流层）是我们'住在里面'、天气发生的层；越往上越冷（对流层内），到平流层反而升温（臭氧吸热）。",
        "explanation_variants": {
            "intuitive": "用'蒸锅'理解温室效应：太阳光进来容易（加热），地面热量出去难（被温室气体挡住）",
            "formal": "对流层顶约 8-18km；平流层臭氧吸收紫外线导致逆温；大气辐射平衡：吸收太阳短波 = 发射长波",
        },
        "common_misconceptions": ["以为'高处更冷'适用所有层（平流层逆温）", "混淆'温室效应'（正常）与'全球变暖'（增强）"],
        "worldview_fit": {"1": 0.1, "2": 0.7, "3": 0.1, "4": 0.1},
    },
    "atmospheric_science.motion.circulation": {
        "id": "atmospheric_science.motion.circulation", "subject": "atmospheric_science", "topic": "motion",
        "concept": "circulation", "level": "high_school", "difficulty": 5,
        "definition": "大气运动：气压梯度力/科里奥利力/摩擦力、地转风、三圈环流（Hadley/Ferrel/Polar）、季风、高空急流、气压带风带。",
        "intuition": "风是'空气从高压往低压跑'（气压梯度力），但地球自转让它'拐弯'（科里奥利力）——北半球往右偏，所以台风逆时针转。三圈环流像'三个传送带'分配全球热量。",
        "explanation_variants": {
            "intuitive": "用'旋转木马'理解科里奥利力：在旋转的圆盘上沿直线走，看起来却拐弯",
            "formal": "地转平衡：气压梯度力 = 科里奥利力；Rossby 数判别尺度；Hadley 环流：赤道上升→高空向极地→30°下沉（副热带高压）",
        },
        "common_misconceptions": ["以为风'直接'从高压吹向低压（实际受科氏力偏转）", "混淆'季风'与'海陆风'（尺度不同）"],
        "worldview_fit": {"1": 0.1, "2": 0.65, "3": 0.15, "4": 0.1},
    },
    "atmospheric_science.weather.fronts": {
        "id": "atmospheric_science.weather.fronts", "subject": "atmospheric_science", "topic": "weather",
        "concept": "fronts", "level": "high_school", "difficulty": 5,
        "definition": "天气系统：气团与锋面（冷锋/暖锋/准静止锋）、气旋与反气旋、台风（热带气旋）的结构与移动路径、雷暴与龙卷。",
        "intuition": "锋面是'两种气团的战场'：冷锋（冷空气推暖空气）带来骤雨降温，暖锋（暖空气爬冷空气）带来连绵阴雨。台风是'巨大的旋转风暴'，中心是风平浪静的台风眼。",
        "explanation_variants": {
            "intuitive": "用'拔河'理解锋面：冷气团和暖气团谁赢，决定天气怎么变",
            "formal": "冷锋过境：气温骤降/气压上升/风雨；暖锋：降水范围广而缓；台风结构：眼区（下沉/晴）/眼壁（最强上升/最大风）",
        },
        "common_misconceptions": ["以为台风中心风最大（眼区反而风平浪静）", "混淆'气旋'（低压）与'反气旋'（高压）的旋转方向"],
        "worldview_fit": {"1": 0.1, "2": 0.65, "3": 0.15, "4": 0.1},
    },
    "atmospheric_science.climate.enso": {
        "id": "atmospheric_science.climate.enso", "subject": "atmospheric_science", "topic": "climate",
        "concept": "enso", "level": "undergraduate", "difficulty": 6,
        "definition": "气候与气候变化：气候系统、厄尔尼诺/拉尼娜（ENSO）、季风气候、温室气体与全球变暖、气候模式与预测。",
        "intuition": "ENSO 是'太平洋的跷跷板'：厄尔尼诺（东太平洋异常暖）让全球天气'错位'（有些地方涝、有些地方旱）；拉尼娜相反。气候变暖像'给地球盖厚被子'。",
        "explanation_variants": {
            "intuitive": "用'跷跷板'理解 ENSO：西太平洋暖池与东太平洋冷水异常互换位置，牵动全球大气环流",
            "formal": "ENSO 指数（Niño3.4 区海温距平）；南方涛动（SOI）；气候模式：GCM 求解流体力学+热力学方程组",
        },
        "common_misconceptions": ["把'天气'与'气候'混为一谈（天气=短期，气候=长期统计）", "以为厄尔尼诺'只影响太平洋'（实为全球遥相关）"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },
    "atmospheric_science.chemistry.pollution": {
        "id": "atmospheric_science.chemistry.pollution", "subject": "atmospheric_science", "topic": "chemistry",
        "concept": "pollution", "level": "undergraduate", "difficulty": 6,
        "definition": "大气化学与观测：大气成分、臭氧层与臭氧洞、空气污染（PM2.5/光化学烟雾/酸雨）、气象观测与数值天气预报。",
        "intuition": "臭氧洞是'平流层臭氧被氟利昂破坏'出的洞（南极尤甚）；光化学烟雾是'汽车尾气+阳光'反应的产物。PM2.5 小到能穿透肺泡进血液。",
        "explanation_variants": {
            "intuitive": "用'防晒霜被撕破'理解臭氧洞：臭氧是地球的防晒层，氟利昂像'撕洞的剪刀'",
            "formal": "O₃ 损耗：Cl 催化循环；光化学烟雾：NOx+VOC+阳光→O₃/过氧乙酰硝酸酯；逆温层抑制污染物扩散",
        },
        "common_misconceptions": ["以为臭氧洞'是洞'（是浓度变稀，不是真洞）", "把'雾'与'霾'混为一谈（雾=水滴，霾=颗粒物）"],
        "worldview_fit": {"1": 0.15, "2": 0.55, "3": 0.2, "4": 0.1},
    },

    # ============ 量子场论 QFT（v0.25 · 7 层体系，仅大学） ============
    "qft.prelude.motivation": {
        "id": "physics.qft.prelude.motivation", "subject": "physics", "topic": "prelude",
        "concept": "motivation", "level": "undergraduate", "difficulty": 7,
        "definition": "量子场论动机：粒子产生与湮灭、相对论性量子力学困难（负能量解）、多粒子系统、散射实验（如高能对撞）为什么必须用量子场论。",
        "intuition": "粒子不是'台球'而是'场的涟漪'：真空中充满各种场，粒子是场的局域激发——就像水面上的波浪不是'东西'，是水（场）的扰动。",
        "explanation_variants": {
            "intuitive": "用'水面涟漪'理解：波浪可以产生、消失、合并——粒子也一样（场的激发可产生湮灭）",
            "formal": "量子场论 = 量子力学 + 狭义相对论 + 多粒子系统；粒子数不再守恒（产生/湮灭算符）",
        },
        "common_misconceptions": ["以为真空是'空无一物'（真空是场的基态，有零点能）", "把 QFT 当'更高级的量子力学'（是不同框架）"],
        "worldview_fit": {"1": 0.2, "2": 0.5, "3": 0.2, "4": 0.1},
    },
    "qft.quantization.scalar_field": {
        "id": "physics.qft.quantization.scalar_field", "subject": "physics", "topic": "quantization",
        "concept": "scalar_field", "level": "undergraduate", "difficulty": 8,
        "definition": "标量场正则量子化：Klein-Gordon 方程、谐振子类比（每个动量模是独立谐振子）、产生/湮灭算符、真空与单粒子态、费曼传播子。",
        "intuition": "把场看成'无数个弹簧的集合'：每个动量模式是一根弹簧（谐振子），量子化就是给每根弹簧'数弹簧量子'——一个量子就是一个粒子。",
        "explanation_variants": {
            "intuitive": "用'弹簧床'理解：场是弹簧床面，每个位置是一根弹簧；激发一根弹簧（给它能量）= 产生一个粒子",
            "formal": "φ(x) = Σ(a_k e^{ikx} + a†_k e^{-ikx})；[a_k, a†_k'] = δ_{kk'}；真空 |0⟩ 满足 a_k|0⟩=0",
        },
        "common_misconceptions": ["混淆'场算符'与'经典场'（算符有对易关系）", "以为粒子'真的'从真空产生（是场从基态到激发态）"],
        "worldview_fit": {"1": 0.2, "2": 0.55, "3": 0.15, "4": 0.1},
    },
    "qft.spinor.dirac_field": {
        "id": "physics.qft.spinor.dirac_field", "subject": "physics", "topic": "spinor",
        "concept": "dirac_field", "level": "undergraduate", "difficulty": 9,
        "definition": "旋量与狄拉克场：洛伦兹群旋量表示、狄拉克方程、负能量解的物理解释（费米海/反粒子）、自旋-统计定理、费米子场反对易。",
        "intuition": "狄拉克方程的负能量解不是'无解'而是'反粒子'：就像欠债（负能量）不是'没有'，而是'反向的财富'——电子的反粒子是正电子。",
        "explanation_variants": {
            "intuitive": "用'账本'理解反粒子：能量为负的解，看成'反向的粒子'（正电子）——费米海孔洞图像",
            "formal": "狄拉克方程 (iγ^μ∂_μ - m)ψ = 0；ψ†γ^0ψ 为概率密度；自旋 1/2 费米子满足反对易关系 {ψ_a, ψ†_b} = δ_ab",
        },
        "common_misconceptions": ["以为狄拉克方程只是'修正'（它预言反物质）", "混淆旋量与四矢量（不同洛伦兹表示）"],
        "worldview_fit": {"1": 0.15, "2": 0.6, "3": 0.15, "4": 0.1},
    },
    "qft.gauge.qed": {
        "id": "physics.qft.gauge.qed", "subject": "physics", "topic": "gauge",
        "concept": "qed", "level": "undergraduate", "difficulty": 9,
        "definition": "规范场论与 QED：U(1) 局域规范对称性、协变导数、光子场、QED 拉格朗日量、费曼规则（电子-光子顶点）、g-2 因子。",
        "intuition": "规范对称性 = '每个点可以自由选择相位'：要求物理在局部相位变换下不变，就必须引入光子场来'补偿'——对称性'要求'有相互作用。",
        "explanation_variants": {
            "intuitive": "用'地图重绘'理解规范：每点可旋转自己的坐标（局域对称），为保持一致必须引入'联络'（规范场=光子）",
            "formal": "L_QED = ψ̄(iγ^μD_μ - m)ψ - ¼F_μνF^μν；D_μ = ∂_μ - ieA_μ；局域 U(1) 不变性 ⇒ 电磁相互作用",
        },
        "common_misconceptions": ["以为规范对称是'对称性'（是'冗余描述'，物理不变）", "混淆'规范固定'与'破缺'"],
        "worldview_fit": {"1": 0.15, "2": 0.6, "3": 0.15, "4": 0.1},
    },
    "qft.renormalization.uv_divergence": {
        "id": "physics.qft.renormalization.uv_divergence", "subject": "physics", "topic": "renormalization",
        "concept": "uv_divergence", "level": "undergraduate", "difficulty": 9,
        "definition": "重整化：紫外发散（圈图积分发散）、维数正规化、重整化常数、可重整性、重整化群与有效场论思想。",
        "intuition": "圈图发散 = '理论在极短距离失效'：重整化是'重新标定参数'（质量/电荷吸收无穷大），就像用'实测值'校准理论，不关心裸参数。",
        "explanation_variants": {
            "intuitive": "用'测量校准'理解：裸质量是'理论未修正'，实验测的是'重整化后'——发散被吸收进可测参数",
            "formal": "维度正规化：d=4-ε；重整化条件；β 函数与跑动耦合常数；有效场论：低能行为由高能细节'退耦'",
        },
        "common_misconceptions": ["以为重整化是'扔掉无穷大'（是系统性的重参数化）", "以为'可重整'= '已解决所有问题'（是理论自洽条件）"],
        "worldview_fit": {"1": 0.15, "2": 0.6, "3": 0.15, "4": 0.1},
    },
    "qft.sm.higgs": {
        "id": "physics.qft.sm.higgs", "subject": "physics", "topic": "sm",
        "concept": "higgs", "level": "undergraduate", "difficulty": 9,
        "definition": "标准模型导览：粒子谱（费米子三代/规范玻色子）、希格斯机制（自发对称破缺赋予质量）、QCD 与 QED 统一、标准模型的成就与局限。",
        "intuition": "希格斯机制 = '宇宙充满的粘稠介质'：粒子穿过它'感到阻力'（获得质量）——有的阻力大（顶夸克重），有的几乎无阻力（光子无质量）。",
        "explanation_variants": {
            "intuitive": "用'蜂蜜罐'理解：粒子在希格斯场里'蘸蜂蜜'——蘸得多的质量大，光子不蘸所以无质量",
            "formal": "希格斯势 V = μ²φ†φ + λ(φ†φ)²；μ²<0 ⇒ 自发对称破缺；Goldstone 玻色子被吸收（纵向分量）",
        },
        "common_misconceptions": ["以为希格斯粒子'产生质量'（是希格斯场与粒子耦合）", "以为标准模型是'终极理论'（不含引力/暗物质）"],
        "worldview_fit": {"1": 0.2, "2": 0.55, "3": 0.15, "4": 0.1},
    },

    # ============ 电子科学与技术（v0.26 · 8 层体系） ============
    "electronics.circuits.kcl_kvl": {
        "id": "electronics.circuits.kcl_kvl", "subject": "electronics", "topic": "circuits",
        "concept": "kcl_kvl", "level": "undergraduate", "difficulty": 3,
        "definition": "电路抽象与基本定律：集中参数模型、基尔霍夫电流定律（KCL）与电压定律（KVL）、节点分析与网格分析、叠加定理、戴维南/诺顿等效。",
        "intuition": "KCL 是'流进节点的电流=流出的'（电荷守恒）；KVL 是'绕一圈电压升=电压降'（能量守恒）。电路像水管：节点是接口，电流像水流，电压像水压差。",
        "explanation_variants": {
            "intuitive": "把电路当'水循环'：KCL 是每个管口进出水量平衡，KVL 是绕一圈水位变化总和为零",
            "formal": "KCL: ΣI_in = ΣI_out；KVL: ΣV = 0（绕闭合回路）；戴维南等效：有源线性二端网络 → 电压源+串联电阻",
        },
        "common_misconceptions": ["把电压当'流过'的（电压是两点间电位差）", "忘记叠加定理只适用于线性电路"],
        "worldview_fit": {"1": 0.1, "2": 0.65, "3": 0.15, "4": 0.1},
    },
    "electronics.devices.transistor": {
        "id": "electronics.devices.transistor", "subject": "electronics", "topic": "devices",
        "concept": "transistor", "level": "undergraduate", "difficulty": 5,
        "definition": "半导体器件：PN 结与二极管 I-V 特性、BJT 放大原理、MOSFET 特性与开关模型、小信号模型。",
        "intuition": "晶体管是'电控阀门'：BJT 用基极电流控制集电极大电流（电流放大），MOSFET 用栅极电压控制沟道导通（电压控制）。像'水龙头'——小旋钮控制大水流。",
        "explanation_variants": {
            "intuitive": "把三极管当'可控水阀'：基极是旋钮，集电极是水管，发射极是出水口",
            "formal": "BJT: IC = β·IB（放大区）；MOSFET: ID = ½μnCox(W/L)(VGS-Vth)²（饱和区）",
        },
        "common_misconceptions": ["以为晶体管是'电流放大'的绝对真理（本质是受控源）", "混淆 BJT（电流控制）与 MOSFET（电压控制）"],
        "worldview_fit": {"1": 0.1, "2": 0.65, "3": 0.15, "4": 0.1},
    },
    "electronics.digital.cmos": {
        "id": "electronics.digital.cmos", "subject": "electronics", "topic": "digital",
        "concept": "cmos", "level": "undergraduate", "difficulty": 5,
        "definition": "数字抽象与 CMOS：数字抽象（高/低电平）、CMOS 逻辑门（NMOS+PMOS 互补）、组合逻辑（卡诺图/PLA）、时序逻辑（锁存器/寄存器/FSM）。",
        "intuition": "数字电路把连续电压抽象成 0/1：CMOS 用 NMOS+PMOS 对实现'要么导通要么关断'——几乎不耗静态功耗。数字世界像'开关组合'：输入开关组合决定输出。",
        "explanation_variants": {
            "intuitive": "把逻辑门当'开关电路'：与门是串联开关，或门是并联开关，非门是反向开关",
            "formal": "CMOS 反相器：NMOS 下拉 + PMOS 上拉，静态功耗近似为零；组合逻辑最小化用卡诺图",
        },
        "common_misconceptions": ["以为数字电路不耗电（动态功耗随频率上升）", "混淆组合逻辑（无记忆）与时序逻辑（有状态）"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },

    # ============ 计算机科学（v0.26 · 8 层体系） ============
    "computer_science.algorithms.complexity": {
        "id": "computer_science.algorithms.complexity", "subject": "computer_science", "topic": "algorithms",
        "concept": "complexity", "level": "undergraduate", "difficulty": 4,
        "definition": "算法与复杂度：大 O 记号、常见复杂度（常数/对数/线性/平方/指数）、排序与搜索算法、递归与分治。",
        "intuition": "大 O 是'输入变大时运行时间怎么长'：O(1) 是'不管多大都一样快'，O(n²) 是'翻倍输入时间变 4 倍'。像'整理书'——线性扫一遍 vs 两两比较。",
        "explanation_variants": {
            "intuitive": "用'找书'理解复杂度：直接翻到（O(1)）、按页找（O(n)）、两两比对（O(n²)）、二分折半（O(log n)）",
            "formal": "二分查找 O(log n)；快速排序平均 O(n log n)；动态规划通过子问题重用法避免指数爆炸",
        },
        "common_misconceptions": ["把 O(2^n) 与 O(n²) 混淆（指数远快于多项式）", "忽略空间复杂度（只记时间）"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },
    "computer_science.systems.os": {
        "id": "computer_science.systems.os", "subject": "computer_science", "topic": "systems",
        "concept": "os", "level": "undergraduate", "difficulty": 5,
        "definition": "计算机系统与操作系统：CPU/存储层次/IO、进程与线程、调度、内存管理（虚拟内存/分页）、文件系统。",
        "intuition": "操作系统是'资源管理员'：CPU 调度像'多任务分配'，虚拟内存像'假的内存更大'（磁盘当内存用），进程隔离像'每个程序有自己的房间'。",
        "explanation_variants": {
            "intuitive": "把 OS 当'公寓管理员'：进程是住户（各住各的），线程是同居者（共享空间），虚拟内存是'借邻居的房间'（磁盘）",
            "formal": "时间片轮转调度；虚拟内存：页表 + 缺页中断 + LRU 替换；进程间通信：管道/消息队列/共享内存",
        },
        "common_misconceptions": ["混淆进程与线程（进程隔离，线程共享）", "以为虚拟内存'真的'有大内存（是映射机制）"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },
    "computer_science.programming.recursion": {
        "id": "computer_science.programming.recursion", "subject": "computer_science", "topic": "programming",
        "concept": "recursion", "level": "undergraduate", "difficulty": 3,
        "definition": "编程基础：控制流、递归与分治、抽象数据类型（ADT）、函数式/OOP 范式、Python 代码实践。",
        "intuition": "递归是'函数调用自己'：像俄罗斯套娃——处理一个 = 处理一半 + 处理剩下（分治）。关键是'基准情形'（何时停止）。",
        "explanation_variants": {
            "intuitive": "用'套娃'理解递归：打开一层套娃，里面还是套娃，直到最小那个（基准情形）",
            "formal": "def fact(n): return 1 if n<=1 else n*fact(n-1)；分治：T(n)=2T(n/2)+O(n) → O(n log n)",
        },
        "common_misconceptions": ["忘记基准情形导致无限递归（栈溢出）", "以为递归比迭代'高级'（两者等价，递归更清晰）"],
        "worldview_fit": {"1": 0.1, "2": 0.6, "3": 0.2, "4": 0.1},
    },

    # ============ 人工智能（v0.26 · 8 层体系） ============
    "artificial_intelligence.ml.supervised": {
        "id": "artificial_intelligence.ml.supervised", "subject": "artificial_intelligence", "topic": "ml",
        "concept": "supervised", "level": "undergraduate", "difficulty": 4,
        "definition": "机器学习基础：监督学习（线性回归/Logistic/SVM/决策树）、无监督（聚类/PCA）、模型评估（过拟合/正则化/偏差方差）。",
        "intuition": "监督学习是'有答案的学习'：给例子+正确答案，让模型找规律。像'教小孩认猫'——看很多猫的图（特征），标注'这是猫'（标签）。",
        "explanation_variants": {
            "intuitive": "用'猜价格'理解回归：根据房子面积/位置（特征）预测价格（标签）——找一条线拟合数据",
            "formal": "线性回归：最小化 MSE；逻辑回归：sigmoid 输出概率；过拟合：高方差低偏差，用正则化（L1/L2）缓解",
        },
        "common_misconceptions": ["混淆过拟合（记住训练集）与欠拟合（没学够）", "以为更多特征总更好（维数灾难）"],
        "worldview_fit": {"1": 0.15, "2": 0.55, "3": 0.2, "4": 0.1},
    },
    "artificial_intelligence.llm.transformer": {
        "id": "artificial_intelligence.llm.transformer", "subject": "artificial_intelligence", "topic": "llm",
        "concept": "transformer", "level": "undergraduate", "difficulty": 6,
        "definition": "Transformer 与大模型：自注意力机制、多头注意力、位置编码（RoPE）、MoE、KV Cache、训练与对齐（SFT/RLHF）。",
        "intuition": "自注意力是'每个词看所有词决定自己该关注谁'：像开会时每个人听所有发言，决定谁的贡献重要。Transformer 让所有词并行处理（不像 RNN 逐个）。",
        "explanation_variants": {
            "intuitive": "用'开会'理解注意力：每个词（参会者）对每个其他词（发言）分配注意力权重（谁重要听谁）",
            "formal": "Attention(Q,K,V)=softmax(QKᵀ/√d)V；多头注意力并行多个注意力头；位置编码让模型感知词序",
        },
        "common_misconceptions": ["以为 LLM'真理解'（是统计模式学习）", "混淆 SFT（指令微调）与 RLHF（人类反馈强化学习）"],
        "worldview_fit": {"1": 0.2, "2": 0.5, "3": 0.2, "4": 0.1},
    },
    "artificial_intelligence.agents.design": {
        "id": "artificial_intelligence.agents.design", "subject": "artificial_intelligence", "topic": "agents",
        "concept": "design", "level": "undergraduate", "difficulty": 6,
        "definition": "智能体设计：ReAct（推理+行动）、Tool Use、Planning、多 Agent 协作、RAG（检索增强生成）。",
        "intuition": "智能体是'会行动的 AI'：不只说话，还能思考→决定→调用工具→观察结果→再思考（ReAct 循环）。像'有手有脚的助手'。",
        "explanation_variants": {
            "intuitive": "用'做饭'理解 ReAct：思考（要炒什么菜）→ 行动（开火/放油）→ 观察（油热了吗）→ 再思考（下一步）",
            "formal": "ReAct：Thought→Action→Observation 循环；Tool Use：LLM 输出函数调用；RAG：检索相关文档增强生成",
        },
        "common_misconceptions": ["以为 Agent=LLM（Agent 是 LLM+工具+循环）", "忽略工具调用的错误处理（失败重试）"],
        "worldview_fit": {"1": 0.2, "2": 0.5, "3": 0.2, "4": 0.1},
    },
}


def load_extended_subjects(subjects: dict):
    """把扩展学科节点注册进 knowledge_base.subjects。"""
    for nid, node in EXTENDED_SUBJECTS.items():
        subjects[nid] = node
