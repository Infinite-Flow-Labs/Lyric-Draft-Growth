# KOC 内容 Playbook

- **日期**: 2026-03-17
- **状态**: Draft
- **关联产品**: 通用（YoloX 优先）

---

## 概述

从 40+ 个中英文对标账号的 120+ 条真实推文中，提炼出 **17 种内容类型**（9 种中文通用 + 8 种英文独立）。对每种类型，我们拆解：

1. **是什么** — 类型定义 + 核心结构
2. **案例** — 真实推文原文 + 创作方法分析
3. **怎么复制** — 生产流水线 + 工作流

## 核心生产模型

高效 KOC 内容的生产流程：

```
信息源采集 → AI 辅助加工（翻译/改写/结构化）→ 人工增值（选题/经验/比喻/情绪）→ 发布
```

人的核心价值在三件事：**选什么做**、**加入真实经验**、**调出个人语感**。其余环节均可用 AI 提效。

---

## 1. 🔧 工具安利 — "我帮你试过了"

**定义：** 推荐一个具体的工具/产品/开源项目，告诉读者它能干什么、怎么用。

**核心结构：** 痛点 → 工具 → 效果展示

**为什么有效：** 读者零成本获得价值，天然高收藏。加上"免费"、"开源"、"一键"等关键词放大传播。

### 案例

**案例 A — @guishou_56** [OpenClaw中文社区](https://x.com/guishou_56/status/2027675295201870244)（1,831 赞 · 156k 浏览）

> 原文：别再四处瞎存 OpenClaw 的碎片教程了。我把收藏夹里几十篇乱七八糟的攻略全删了,因为发现了一个堪称「保姆级」的OpenClaw中文社区。一个网站全搞定: 1. 告别环境配置地狱 -- 贴心提供国内镜像极速下载，零基础一键安装 2. 真正的全能助理 -- 能帮你回邮件、控制浏览器、运行本地脚本 3. 纯净开源无套路 -- 100% 免费……

**创作方法：** 信息来自网站介绍页，提取核心卖点后用列表体 + emoji 结构化呈现。人工价值在于「发现这个网站」和开头那句"别再瞎存"的情绪钩子。

---

**案例 B — @nishuang** [Twillot 效率工具](https://x.com/nishuang/status/1902376909297594647)（836 赞 · 121k 浏览 · 2025）

> 原文：继续推荐我的秘密效率工具 Twillot。简单而言它干了马斯克没干的事，把 X 变成了信息管理工具：管理我发过的推文、收藏夹、点赞记录，用 AI 自动把它们分类…所有数据同步到本地，极速搜索而且不怕马斯克封号…我会把推特当做笔记来用，想到什么立刻写下来、发出来。

**创作方法：** "它干了马斯克没干的事"是极强的钩子——借势大人物制造好奇心。然后用个人使用场景（"我把推特当笔记"）建立真实感。

---

**案例 C — @op7418** [开源语音模型 Zonos](https://x.com/op7418/status/1889119439314165834)（865 赞 · 93k 浏览）

> 原文：最强开源语音模型 Zonos，1.6B 参数，支持中文，5-30秒语音克隆，可调速度/音高/情绪。

**创作方法：** 从 README 提取技术参数（1.6B/5-30秒/中文），精简为一句话。人工价值在「最强」这个定性判断。

**英文案例 — @AlphaSignalAI** [GitNexus 代码知识图谱](https://x.com/AlphaSignalAI/status/2026846215644787196)（181 赞 · 13k 浏览 · 2026）

> 原文：Here's an easy way to turn your code base into an interactive knowledge graph. Popular vibe coding tools like Cursor, Claude Code, or Windsurf are powerful — but they don't fully know your codebase structure. When you edit a file, the AI often ignores 47 functions that depend on its return type...

**创作方法：** 先指出痛点（"vibe coding tools don't fully know your codebase"）→ 介绍工具 → 详细拆解架构。英文圈的工具安利更强调 **why it matters**，而非简单罗列功能。

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
GitHub Trending               翻译 README                  选哪个工具值得推（选题判断）
Product Hunt 每日新品          提取核心功能点               加入"我试了一下"的体验感
Hacker News Show HN           生成结构化推文                加入情绪钩子（"不敢相信"/"强推"）
Reddit r/singularity          润色为列表体+emoji            决定发布时机（跟热点）
X 关注的英文大V               改写为中文推文
```

### 中英文差异

| 维度 | 中文 | 英文 |
|------|------|------|
| 格式 | 列表体 + emoji 分隔 | Thread 清单 + "why" 解释 |
| 钩子 | "不敢相信"、"别再…了" | "You don't need X, you need Y" |
| CTA | 链接 | "What tools would you add?" |

### 可复制工作流

```
每日 10 分钟：
1. 刷 GitHub Trending / Product Hunt / HN
2. 选 1 个感兴趣的工具
3. 中文号：AI 生成列表体推文（参考 @guishou_56 风格）
   英文号：AI 生成 "Here's why this matters" 格式（参考 @nonmayorpete 风格）
4. 加入一句个人体验
5. 发布
```

---

## 2. 📖 保姆级教程 — "我走过的路帮你铺平"

**定义：** 手把手分步骤教读者完成一件事，面向零基础，每一步都写清楚。

**核心结构：** 目标 → 步骤1 → 步骤2 → … → 完成 → 注意事项

**为什么有效：** 解决具体问题，读者跟着做就行。"保姆级"、"从零开始"、"有手就行" 是流量密码。

### 案例

**案例 A — @guishou_56** [2026年 Gmail 注册方法](https://x.com/guishou_56/status/2021083223594500260)（254 赞 · 50k 浏览）

> 原文：2026年注册Gmail变难了,赶紧多注册几个备用。谷歌升级了风控措施: 电脑端注册需要扫码验证,大概率过不去；手机号无法验证。现在唯一能成功的方法: 用手机注册。具体步骤: 1. 全程开美国魔法 2. 打开手机Gmail APP 3. 添加账号 -> 输入信息 4. 手机号验证 5. 按提示走完流程。注册成功后必做: 添加辅助邮箱和辅助手机号……

**创作方法：** 多次试错后总结出唯一可行路径，再结构化为步骤 1→2→3→4→5。"现在还能注册，等风控再升级可能连手机都注册不了"是紧迫感钩子，驱动立即行动。

---

**案例 B — @Astronaut_1216** [香港一日游开户攻略](https://x.com/Astronaut_1216/status/2030467763026739458)（319 赞 · 124k 浏览）

> 原文：香港一日游开户攻略（众安银行+汇丰银行），从手机漫游设置到每个银行APP操作步骤逐一讲解……附带顺路旅游路线推荐（福田口岸->尖沙咀->维港->中环）。定位"从不会用手机教起"的小白级别教程。

**创作方法：** 亲身经历整理成教程，旅游路线推荐是个人体验的加分项。受众定位极精准——"从不会用手机教起"，把门槛降到最低。

---

**英文对应类型：→ 见 #16 Open Source Drop。** 英文圈的"教程"更倾向直接开源 repo，而非手把手教步骤。

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
自己实际操作的过程              录屏/截图 → AI 整理成步骤     亲身踩坑（这是AI无法替代的）
（注册账号、配置工具、           把口语化记录润色为教程体      标注"注意事项"（踩坑经验）
  开银行卡、搭建服务）          生成"步骤1→步骤2"结构       设定受众级别（"零基础"/"有手就行"）
```

### 关键洞察

**保姆级教程是 AI 参与度最低的类型。** 核心价值是「我真的做过」——AI 可以帮你把操作过程整理成结构化的推文，但操作本身必须是真实的。这也是为什么这类内容的信任度和转化率最高。

### 可复制工作流

```
1. 做某件事时打开录屏/笔记
2. 边做边记录每个步骤和遇到的问题
3. 做完后把笔记丢给 AI："整理成一条保姆级教程推文，分步骤，标注注意事项，语气像在教朋友"
4. 检查 AI 输出，补充自己的踩坑细节
5. 配图（截图/录屏GIF）
```

---

## 3. 🔥 热点快评 — "我比你快 10 分钟"

**定义：** 对刚发生的行业事件/新产品/新政策，快速给出一句话判断或简短解读。

**核心结构：** 事件 → 一句话判断（或短评）

**为什么有效：** 速度是核心竞争力。第一个发的人吃掉大部分流量。不需要深度，只需要快+有观点。

### 案例

**案例 A — @op7418** [Seedance 2.0](https://x.com/op7418/status/2019813598051373309)（307 赞 · 62k 浏览）

> 原文：Seedance 2.0 是当前世界最强视频模型，字节终于站起来了。

**创作方法：** 看到消息→秒发判断，一句话搞定。核心价值 = 速度 + "世界最强"这个大胆定性。

---

**案例 B — @fkysly** [OpenCode Black 售罄](https://x.com/fkysly/status/2008733710116622806)（59 赞 · 24k 浏览）

> 原文：OpenCode 推出 Black 套餐（$200/月），一小时内售罄。对标 Claude Max / Codex Pro。

**创作方法：** 信息 + 简短对标判断。格式固定：事实 + "对标 XXX"。

---

**英文对应类型：→ 见 #12 Signal Boost。** 英文热点快评的极端形式是零分析纯转述——引言本身就是观点。

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
X Timeline 英文大V            几乎不需要                   速度（第一个发中文版的人）
官方博客/公告                  简单翻译（如果是英文）        一句话判断（"世界最强"/"要完"）
Discord/Slack 社区消息          -                          选择性（哪些值得发，哪些不值得）
```

### 关键洞察

**热点快评的核心不是 AI，是信息源的宽度和反应速度。** 赢在"我比你早看到 10 分钟"。AI 唯一能帮的是翻译英文消息。

### 可复制工作流

```
1. 建立信息源矩阵：关注 20-30 个英文 AI 大V + 3-5 个 Discord 频道
2. 开启通知，看到重要消息 5 分钟内发
3. 格式："[消息] + [一句话判断]"，不要写长文
4. 如果是英文：AI 翻译→加判断→发
```

---

## 4. 💡 概念翻译器 — "英文世界的搬运工"

**定义：** 把复杂的技术概念/论文/英文内容，用通俗比喻或中文翻译讲清楚。

**核心结构：** 原始概念 → 通俗比喻/翻译 → "所以这意味着……"

**为什么有效：** 信息不对称是最大的流量来源。英文世界的内容翻译到中文，论文翻译成人话，都是降维打击。

### 案例（最能证明 AI 深度参与的类型）

**案例 A — @fkysly** [拉尔夫循环](https://x.com/fkysly/status/2008862457591419364)（1,106 赞 · 120k 浏览）

> 原文：解读 "拉尔夫循环（Ralph Loop）" 概念 — Agent 执行到上限后自动重新注入 prompt 继续执行。形象比喻为"老板甩鞭子让实习生继续干活"。提到有人靠此跑了 3 个月循环做出一个完整编程语言。

**创作方法：** 英文社区概念翻译为中文，加了"老板甩鞭子让实习生干活"这个生活化比喻。**比喻是全文传播力的核心**——同一个概念，有比喻和没比喻的传播效果差 10 倍。

---

**案例 B — @dotey** [Anthropic 2026 Agent 八大趋势](https://x.com/dotey/status/2021102914450673721)（702 赞 · 109k 浏览）

> 原文：万字长文解读 Anthropic 报告，涵盖多 Agent 协同、长时间运行 Agent、编程民主化、安全双刃剑等八大趋势。核心观点：软件开发从"写代码"转变为"编排 Agent 写代码"。

**创作方法：** Anthropic 英文博客全文翻译+解读，在原文发布后数小时内产出。人工价值在于"编排 Agent 写代码"这个核心提炼——把万字报告浓缩成一句话记忆点。

---

**案例 C — @dotey** [OpenAI Codex 负责人访谈翻译](https://x.com/dotey/status/2025790870155370584)（129 赞 · 99k 浏览）

> 原文：翻译 20VC 对 OpenAI Codex 负责人的访谈，核心观点：OpenAI 内部多数人已不打开 IDE、AI 瓶颈是人类打字速度、所有 Agent 本质上都是编码 Agent、通用 Agent 会打败垂直 Agent。

**创作方法：** 播客音频 → 转录 → 翻译 → **从长文中挑出 4 条最有冲击力的金句**。内容量很大时，「挑什么」比「翻什么」更重要。

---

**英文案例 — @AlphaSignalAI** [Claude Cowork 引发 $285B 市场崩盘](https://x.com/AlphaSignalAI/status/2019641856225866247)（63 赞 · 16k 浏览 · 2026）

> 原文：Anthropic's Claude Cowork just caused a $285B market crash... "SaaSpocalypse" was coined by Jefferies to describe investors aggressively selling off SaaS stocks...

**创作方法：** 英文圈的"概念翻译"不是语言翻译，而是**把复杂事件翻译成一个词**——"SaaSpocalypse"。给现象命名就是拥有话语权。中文圈翻译语言，英文圈翻译复杂度。

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
英文博客（Anthropic/OpenAI）   全文翻译                     选题：哪篇值得翻（判断力）
英文播客/访谈                  音频转录+翻译                 提炼金句（不是全翻，是挑重点）
英文论文                       摘要翻译+通俗化              加入通俗比喻（这是核心差异化）
GitHub README                  翻译+结构化                  加入"所以这意味着…"的判断
英文推文/Thread                翻译+改写                    加入中文语境的类比
```

### 关键洞察

**@dotey 的核心竞争力不是翻译本身（AI 都能翻），而是「选什么翻」和「怎么加评」。**

翻译是 AI 最擅长的事。但：
- **选题判断**（这篇 Anthropic 博客为什么重要）是人的价值
- **通俗比喻**（"老板甩鞭子"）是人的价值
- **个人评论**（"这意味着软件开发要变了"）是人的价值

### 可复制工作流

```
每日 15 分钟：
1. 刷英文信息源（Anthropic Blog / OpenAI Blog / HN / 英文大V）
2. 发现一个有趣的概念/文章
3. 丢给 AI："翻译这篇文章的核心观点，用中文，1000字以内"
4. 人工加工：
   - 加一个通俗比喻（"这就像…"）
   - 加一句判断（"这意味着…"）
   - 如果是长文：提炼 3-5 个核心观点，不全翻
5. 发布
```

### @dotey 的具体工作流推测

```
Anthropic 发布英文博客
    ↓
AI 全文翻译（Claude/GPT-4）
    ↓
人工阅读翻译稿，提炼核心观点
    ↓
加入个人解读："这意味着…" "核心变化是…"
    ↓
整理成万字长文推文（可能用 Thread 格式）
    ↓
发布（时效性：英文发布后 2-6 小时内）
```

---

## 5. 💰 数据晒单 — "用数字建立信任"

**定义：** 公开具体的收入数字、增长数据、里程碑，展示真实结果。

**核心结构：** 具体数字 → 怎么做到的 → 可复制的要点

**为什么有效：** 数字是最强的注意力钩子。"30w"、"$10000/月" 比任何标题都有点击率。失败数据同样有效——真实感 > 完美叙事。

### 案例

**案例 A — @gefei55** [出海AI网站流量榜](https://x.com/gefei55/status/1877288130358743152)（278 赞 · 65k 浏览 · 2025）

> 原文：出海AI网站流量榜前50名里有16名在哥飞社群了，大家都很牛。

**创作方法：** 极短一句话，但信息量极大——"前50名有16名在我社群"同时做到了数据晒单 + 社群背书。**数字越具体越有冲击力，"16/50"比"很多人"强 10 倍。**

---

**英文对应类型：→ 见 #13 Engagement CTA 和 #14 Insider Preview。** ammaar 的 486k 浏览帖同时属于两种英文独立类型——产品内测邀请（Insider）+ "drop a reply" 触发算法（CTA）。

---

**英文案例 C — @ramsri_goutham** [Supermeme 合伙人故事](https://x.com/ramsri_goutham/status/1863851365539471700)（18 赞 · 1.6k 浏览 · 2025）

> 原文：A story on how three strangers on the internet were unified by the idea of AI meme generator! Today, we're running a SaaS business generating $5,000+ in monthly revenue — without ever meeting in person!

**创作方法：** "三个陌生人+从未见面+$5000/月"的叙事组合。数字不大，但故事性极强。**小数据晒单靠故事弥补。**

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
自己的真实数据                  把散乱笔记整理成             真实数据（AI 无法替代）
（收入、粉丝、里程碑）          结构化 Thread                 故事叙述（从什么到什么）
                              润色语言                      选择公开什么（策略性透明）
```

### 关键洞察

**数据晒单是「真实性」要求最高的类型。** AI 能帮你把经历写得更好看，但数字必须是真的。这也是为什么这类内容互动最高——稀缺性。

**可复制点：** 长 Thread 的高效产出方式——口述/语音备忘录记录核心观点 → 整理成结构化文字 → 补充细节和数字。

---

## 6. 🛡️ 避坑预警 — "我替你踩了这个坑"

**定义：** 警告读者某件事的风险、某个操作可能导致的问题，帮人避免损失。

**核心结构：** "注意！" → 风险描述 → 正确做法

**为什么有效：** 损失厌恶心理——"避免亏损"比"获得收益"更有驱动力。天然激发收藏和转发。

### 案例

**案例 A — @fkysly** [OAuth 登录可能封号](https://x.com/fkysly/status/2008155808132173983)（171 赞 · 68k 浏览）

> 原文：警告用 OAuth 方式在 OpenCode 登录 Claude 可能导致封号，附 GitHub Issue 链接。

**创作方法：** 信息源是 GitHub Issue，自己验证后快速预警。核心是信息源的广度和反应速度。

---

**案例 B — @AxtonLiu** [不要依赖自动 compact](https://x.com/AxtonLiu/status/2026148495347085472)（50 赞 · 13k 浏览）

> 原文：这就是我从不依赖自动 compact 的原因。Summer Yue 的 OpenClaw 清空了她的邮箱：上下文太长触发自动压缩，压缩过程把「别动手」的指令丢了。我每天用 Claude Code 高强度工作，早就踩过类似的坑，总结了两个习惯：1）定期手动让 AI 记录工作日志 2）手动压缩并带 focus on 参数明确哪些信息必须保留。

**创作方法：** 引用别人的案例（Summer Yue）+ 自己的经验总结。「别人踩坑→我有解法」的双信息源叠加，建立权威感。

---

**案例 C — @Astronaut_1216** [全网教安装，我教你删除](https://x.com/Astronaut_1216/status/2030336350524735568)（291 赞 · 51k 浏览）

> 原文：全网都在讲OpenClaw安装教程，但没人讲如何彻底删除它。指出OpenClaw不适用于所有人，"可能用了一段时间后发现还不如豆包好用"。推荐了一个删除教程。

**创作方法：** 逆向选题——所有人教安装，他教删除。「还不如豆包好用」故意制造争议。**当一个话题过热时，反向切入是最有效的差异化。**

---

**英文对应类型：→ 见 #11 犀利 Rant。** 英文圈的避坑预警更偏"行业警告 + 情绪输出"，与 Rant 类型重合。

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
自己踩坑                       几乎不需要                   踩坑经历（真实性）
GitHub Issues                  翻译（如果是英文）            快速验证+预警
社区讨论（Discord/群聊）        -                           选题判断（逆向思维）
别人的踩坑分享                  -                           补充自己的解决方案
行业现象观察                    -                           给现象命名（英文特色）
```

### 可复制工作流

```
1. 日常使用 AI 工具时注意记录问题
2. 关注 GitHub Issues 中的高频问题
3. 发现坑→验证→5 分钟内发预警
4. 格式："⚠️ 注意！[问题] → [原因] → [正确做法]"
```

---

## 7. 💸 省钱攻略 — "信息差就是钱"

**定义：** 教读者如何用更低成本获得同样的服务/产品，包括白嫖、拼车、替代方案。

**核心结构：** 正常价格 → 省钱方法 → 操作步骤 → 省了多少

**为什么有效：** AI 工具贵是共识痛点。"白嫖"、"免费"、"省钱" 天然自带流量。

### 案例

**案例 A — @fkysly** [闲鱼大法](https://x.com/fkysly/status/2030502401464218029)（700 赞 · 123k 浏览）

> 原文："闲鱼大法" — 用 Sub2API + 阿里云 + 闲鱼拼车 Codex Team 账号，实现低成本使用高级模型的完整方案。

**创作方法：** 之前有一条"折腾到半夜3点终于搞好了"的碎碎念（9 赞 · 6k 浏览），第二天整理成完整攻略。**「碎碎念→攻略」是一个两条推文的组合打法**——碎碎念建立真实感，攻略帖收获流量。

---

**案例 B — @Astronaut_1216** [Sonnet5 套利指南](https://x.com/Astronaut_1216/status/2019033914807902389)（517 赞 · 66k 浏览）

> 原文：《sonnet5准备发布，能赚钱的套利指南》。分享闲鱼年销10400元经验，教大家通过闲鱼+gamsgo信息差套利，包含完整操作步骤（选品、定价、文案、定位技巧等），以及分佣合伙人新玩法。

**创作方法：** 真实经验整理成详细教程（选品、定价、文案全覆盖）。标题蹭了"sonnet5发布"的热点时机——**省钱攻略 + 热点绑定是双重流量加速器。**

---

**英文对应：** 英文圈的"省钱"叫 bootstrapping——用最少资源做最大产出。这种内容在英文圈通常以 #16 Open Source Drop 或数据晒单的形式出现，而非独立的"省钱攻略"。

### 还原的生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
自己折腾省钱方案                把方案整理成步骤              真实验证过（"折腾到3点"）
社区里看到的拼车/替代方案        润色为教程体                 计算具体省了多少钱
价格变动/新套餐发布             翻译+对比                    判断值不值得分享
```

---

## 8. 🧠 认知升级 — "我读了 10 本书帮你总结"

**定义：** 输出一套思考框架/方法论/反常识观点，改变读者看问题的方式。

**核心结构：** 反常识钩子 → 论证 → 新框架

**为什么有效：** 反常识的钩子制造认知冲突，驱动阅读和讨论。长文但收藏率极高。

### 案例（AI 参与度最高的类型之一）

**案例 A — @AxtonLiu** [我给自己造了 70 人 AI 团队](https://x.com/AxtonLiu/status/2028275905018163596)（233 赞 · 34k 浏览 · 2026）

> 原文：五个月构建 70+ Claude Skills，分布在六条链路（内容创作 28、视觉设计 14、知识管理 7、商业运营 6、开发者基建 13、工具 6）。三个阶段演进：单点突破（字幕校对从1小时到几分钟）→ 共享记忆（9个创作Skill共享风格档案）→ 系统自运转（Skill调度Skill，两天剪完15个视频）。MAPS四维罗盘：Mindset、Architecture、Prompt、Systems。

**创作方法：** "70人AI团队"是数字钩子。三阶段递进叙事 + 自创方法论命名（MAPS）。**给方法论起名字是品牌化的关键。**

---

**案例 B — @AxtonLiu** [我给自己造了 70 人 AI 团队](https://x.com/AxtonLiu/status/2028275905018163596)（233 赞 · 34k 浏览）

> 原文：五个月构建 70+ Claude Skills，分布在六条链路（内容创作 28、视觉设计 14、知识管理 7、商业运营 6、开发者基建 13、工具 6）。三个阶段演进：单点突破（字幕校对从1小时到几分钟）→ 共享记忆（9个创作Skill共享风格档案）→ 系统自运转（Skill调度Skill，两天剪完15个视频）。MAPS四维罗盘：Mindset、Architecture、Prompt、Systems。

**创作方法：** 5 个月实践经验提炼为三阶段递进叙事 + 自创方法论命名（MAPS）。**给方法论起名字是品牌化的关键**——"MAPS" 比 "我的 Claude Skills 工作流" 传播力强 10 倍。

---

**英文对应类型：→ 见 #11 犀利 Rant。** 英文圈的认知升级常以 Rant 形式出现——通过质疑主流叙事来输出新认知。中文圈更依赖框架输出，英文圈更依赖争议驱动。

### 还原的生产流水线

```
信息源                        AI 加工                         人工增值
──────────────────────────────────────────────────────────────────────
读书笔记/播客笔记               把散乱笔记整理成框架             核心观点/框架（灵魂）
个人实践经验                    润色为长文 Thread                个人故事（让框架可信）
与人交流获得的洞察               生成结构（问题→分析→建议）       反常识的角度（"90%不适合"）
多个案例的归纳                  命名框架（如"MAPS"）            判断什么框架有传播力
```

### 具体推测：kasong 的创作流程

```
日常积累（读书、做项目、和人聊天）
    ↓
产生一个观点："大多数程序员不适合独立开发"
    ↓
语音备忘录/笔记 app 记下核心论点
    ↓
丢给 AI："我想写一条推文，观点是 XXX，我的论据有 XXX，帮我组织成一个 Thread，
         开头要有一个反常识的钩子，结尾给建议"
    ↓
AI 输出初稿（结构化、2000 字）
    ↓
人工修改：加入具体个人经验、调整语气、确保观点准确
    ↓
发布
```

---

## 9. 🫶 真情实感 — "唯一不需要 AI 的类型"

**定义：** 分享个人真实经历、情绪、困境，不卖课不安利，纯粹的人格化表达。

**核心结构：** 场景/情绪 → 真实感受 → （可选）感悟

**为什么有效：** 工具安利建立实用价值，真情实感建立情感连接。二者缺一不可。对粉丝留存和信任感至关重要。

### 案例

**案例 A — @dev_afei** [中年危机](https://x.com/dev_afei/status/1815247828190392755)（192 赞 · 61k 浏览）

> 原文：第一次感受到了中年危机 😐 家里老人生病住院了，一下子老人、小孩都没人照顾。公司最近在裁员，假还不敢请多了。再过两天 35 岁，这危机来的可真准 🥲

**创作方法：** 文字朴素，没有结构，没有 emoji 列表，没有 CTA。纯粹的情绪输出。**和他的工具安利帖风格完全不同，正是这种「不完美」建立了真实感。**

---

**案例 B — @nishuang** [爱死机第四季回归](https://x.com/nishuang/status/1909702995727491355)（334 赞 · 111k 浏览 · 2025）

> 原文：曾经的神作，"爱，死亡和机器人"第四季即将回归

**创作方法：** 一句话，无结构，纯粹的个人兴奋。但 111k 浏览说明：**话题本身有流量时，简短的真实感受就够了。** 不需要分析，不需要观点，只需要"我也期待"。

---

**案例 C — @fkysly** [折腾到半夜3点](https://x.com/fkysly/status/2030360894165917929)（9 赞 · 6k 浏览）

> 原文：折腾到半夜3点终于搞好了

**创作方法：** 一句话碎碎念，但为第二天 700 赞的「闲鱼大法」攻略帖提供了真实感背书。**碎碎念是爆款帖的信任锚点——读者回看发现"他真的折腾了一宿"。**

### 关键洞察

**真情实感是最不需要刻意生产的类型，但对账号长期健康不可或缺。** 它建立的是「这是一个真人」的感知，让其他类型的内容更有说服力。

**策略：不用单独规划，在做其他事（折腾、踩坑、加班）的时候顺手发就好。**

**英文对应类型：→ 见 #15 Vibe Post 和 #17 Career Narrative。** 英文圈的"真情实感"分化为两种独立类型——轻松幽默的 Vibe Post 和完整弧线的 Career Narrative。中文圈偏焦虑/困境基调，英文圈偏轻松/成长基调。

---

## 10. 📋 Curator 模式 — "我帮你整理了"（英文特有）

**定义：** 不生产原创内容，而是筛选、整理、汇总别人的作品或信息，成为某个领域的信息策展人。

**核心结构：** "过去 [时间段] 最好的 [N] 个 [主题]" → 逐一展示 → "What did I miss?"

**为什么有效：** 信息过载时代，帮读者做筛选本身就是巨大价值。且不需要原创能力，纯靠选品和整理速度。

### 案例

**案例 A — @heyBarsee** [OpenAI 4o 图像生成 14 个最佳案例](https://x.com/heybarsee/status/1904891940522647662)（163,457 赞 · **5,190 万浏览**）

> 原文：It's been 24 hours since OpenAI unexpectedly shook the AI image world with 4o image generation. Here are the 14 most mindblowing examples so far (100% AI-generated): 1. Studio Ghibli style memes...

**创作方法：** 热点发生 24 小时内，从全网筛选出 14 个最好的案例，配图整理成 Thread。**不生产任何原创图片，纯筛选 = 5100 万浏览。** 核心能力是速度和审美。

---

**案例 B — @mreflow** [本周 AI 新闻汇总](https://x.com/mreflow/status/2027473814809194948)（73 赞 · 5.8k 浏览）

> 原文：Here are the biggest AI news stories from the week — let me know what I missed! [17 条新闻] What stood out to you?

**创作方法：** 每周固定栏目，汇总 17-25 条新闻。"What did I miss?"让读者补充，形成双向互动。**固定栏目 = 读者预期 = 稳定流量。**

---

**案例 C — @heyBarsee** [AI 视频模型 12 强](https://x.com/heybarsee/status/1896939877331333348)（933 赞 · 170k 浏览 · 2025）

> 原文：AI-generated videos are getting out of hand. This is ridiculous how far we have come in just 1 year. It might get its own ChatGPT moment soon. Here are 12 leading AI models that just changed AI-generated videos forever:

**创作方法：** "getting out of hand"情绪钩子 + "12 leading models"清单格式。整理别人的作品，自己不生产视频。**Curator 不生产内容，只筛选最好的。**

### 生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
X Timeline 热门帖子            收集+截图                    筛选"最好的 N 个"（审美/判断）
Reddit/HN 热门讨论             汇总为清单                   控制节奏和排序
官方公告/产品更新               翻译+摘要                    加入"What did I miss?" CTA
竞品账号的内容                  -                           发布时机（热点后 24 小时内）
```

### 可复制工作流

```
1. 热点发生后，立即开始收集相关内容（截图/链接/引用）
2. 筛选出最好的 10-15 个
3. AI 辅助整理成 Thread 格式（配图 + 编号 + 一句话点评）
4. 结尾加 "What did I miss?" 或 "What stood out to you?"
5. 24 小时内发布（速度是关键）
```

### 关键洞察

**Curator 模式是 AI 自动化程度最高的类型之一——信息采集、汇总、格式化全部可以自动化。** 人的唯一价值是「选什么」和「排什么顺序」。这也是最适合 KOC 养号冷启动的类型：不需要个人经验，不需要原创观点，只需要速度和审美。

---

## 11. 🔥 犀利 Rant — "这是垃圾"（英文特有）

**定义：** 对行业现象、产品问题、虚假叙事发表强烈批评，语气直接甚至带脏话，不怕得罪人。

**核心结构：** 强烈情绪开头 → 具体案例/证据 → 为什么这很重要

**为什么有效：** 英文 X/Twitter 的算法奖励争议。强烈观点触发 reply 和 quote，推高分发。中文圈同类内容容易被举报，英文圈则是增长利器。

### 案例

**案例 A — @bentossell** ["I'm so fucking sick of bad AI software"](https://x.com/bentossell/status/1915392814390694184)（673 赞 · 137k 浏览）

> 原文：i'm so fucking sick of bad AI software. we've been promised the world will change, everyone will get rich, no-one has to work again bla bla bla... [详细拆解 Perplexity 助手的问题] ...i think hyped launches add new paying users which is contributing to these not quite true $000's M ARR stats we're seeing.

**创作方法：** 强烈情绪开头（"so fucking sick of"）+ 具体产品拆解（Perplexity）+ 行业层面的判断（ARR 虚报）。**不是无理取闹，而是有据可查的批评。**

---

**案例 B — @svpino** ["I think it's all bullshit"](https://x.com/svpino/status/2019199832825688337)（946 赞 · 94k 浏览）

> 原文：There are so many people telling these amazing stories of how they built these great applications overnight using AI... And I think it's all bullshit.

**创作方法：** 质疑主流叙事（"非开发者用 AI 一夜构建应用"）。**当所有人都在正面宣传时，反面声音天然稀缺。**

---

**案例 C — @svpino** [AI virtue signaling](https://x.com/svpino/status/1967562806972350536)（148 赞 · 32k 浏览）

> 原文：The AI virtue signaling is out of control. One of the most stupid trends I've seen is for companies to advertise their product as 'AI this' and 'AI that'.

**创作方法：** 指出行业通病（AI 洗标签），给这个现象命名（"AI virtue signaling"）。**给现象命名 = 拥有这个概念的话语权。**

### 生产流水线

```
信息源                        AI 加工                      人工增值
───────────────────────────────────────────────────────────────────
自己使用产品的糟糕体验            AI 可以帮整理论据             真实的愤怒/失望（核心驱动力）
行业里的虚假宣传                 辅助查找数据支撑              具体案例（不能空喊）
社区里的共识吐槽                 -                           敢说别人不敢说的话
```

### 关键洞察

**Rant 的关键不是骂人，而是「说出大家想说但没人敢说的话」。** 必须有具体案例和证据，否则只是抱怨。这种类型对中文号要谨慎使用（举报风险），但在英文号上是最强的互动触发器之一。

---

## 12. 📢 Signal Boost — "他说的，不是我说的"（英文特有）

**定义：** 转述行业大佬的震撼性原话，自己不加任何分析，让引言本身成为内容。

**核心结构：** [人名 + 身份] + 原话引用。就这样，没有第二段。

### 案例

**案例 A — @AiBreakfast** [Nadella 对董事会的话](https://x.com/aibreakfast/status/1770832950722015660)（5,553 赞 · **227 万浏览** · 2025）

> 原文：Microsoft CEO Satya Nadella to board members: "If OpenAI disappeared tomorrow, we have all the IP rights and all the capability..."

**创作方法：** 零原创内容。找到一句足够震撼的引言，原样贴出。**引言越有冲击力，越不需要分析。** 加分析反而会稀释冲击。

### 关键洞察

**与中文「热点快评」的区别：** 中文快评至少加一句判断（"世界最强"），Signal Boost 连判断都不加。信息本身就是观点。英文圈更接受"不加评论的转发"，中文圈则期望看到博主自己的判断。

### 可复制工作流

```
1. 监控英文大佬的发言（财报电话、播客、演讲、采访）
2. 提取最有冲击力的一句话
3. 格式："[Name], [Title] to [audience]: '[quote]'"
4. 不加任何评论，直接发布
5. 引言越反直觉/越有争议，传播越广
```

---

## 13. 💬 Engagement CTA — "来聊聊"（英文特有）

**定义：** 内容的核心目的不是传递信息，而是触发 reply。reply 数越多，算法推荐越广。

**核心结构：** [话题/邀请] + "drop a reply" / "What did I miss?" / "What would you add?"

### 案例

**案例 A — @ammaar** [AI Studio 新设计征集反馈](https://x.com/ammaar/status/1937588078849241185)（2,836 赞 · **486k 浏览** · 2025）

> 原文：We're cooking up a fresh new design for AI Studio! And we'd absolutely love your input. If you want to test an early prototype and share your thoughts on a call, just drop a reply below!

**创作方法：** "drop a reply"把单向传播变成双向互动。486k 浏览主要由 reply 数驱动的算法放大实现。**内容质量不如参与感重要。**

---

**案例 B — @mreflow** [每周新闻 + "What did I miss?"](https://x.com/mreflow/status/2027473814809194948)（73 赞 · 5.8k 浏览 · 2026）

> 原文：Here are the biggest AI news stories from the week — let me know what I missed!

**创作方法：** 把新闻汇总的结尾变成互动入口。"What did I miss?"让读者觉得自己的补充有价值，触发 reply。

### 关键洞察

**这种类型在中文圈几乎不存在。** 中文 X 的互动文化以转发/收藏为主，"评论区互动"不是主要的分发驱动力。但英文 X 的算法高度权重 reply，所以 Engagement CTA 是英文号的必备技巧。

### 可复制工作流

```
1. 任何内容帖结尾都可以加 CTA：
   - "What would you add?"
   - "What did I miss?"
   - "Drop a reply if you want early access"
   - "Which one is your favorite?"
2. 产品相关帖用"参与感"CTA（内测邀请、反馈征集）
3. 清单帖用"补充"CTA（让读者加内容）
4. 不要问 yes/no 问题，要问开放性问题
```

---

## 14. 🔑 Insider Preview — "我有你没有"（英文特有）

**定义：** 利用自己在特定公司/团队的身份，分享外部无法获取的产品预览、内部视角或独家信息。

**核心结构：** [身份暗示] + [独家内容] + [个人使用体验]

### 案例

**案例 A — @itsandrewgao** [Vibecoding 终端 with remote agents](https://x.com/itsandrewgao/status/2019864488967872799)（188 赞 · 57k 浏览 · 2026）

> 原文：i vibecoded a fully working terminal from scratch using parallel remote agents, w/o editing a single line of code. took the best agent just ~6 hrs. would take me ~6-12 mo to do the same by hand w/o ai

**创作方法：** 在 Cognition（Devin 母公司）工作 → 拥有别人没有的工具和视角 → 分享实验结果。"parallel remote agents"是大多数人用不到的功能。

### 关键洞察

**不是所有人都有 Insider 身份。** 但可以复制思路：成为某个 AI 产品的最早期用户/测试者。很多 AI 工具的 beta 测试是开放申请的，第一批体验并分享就能获得类似效果。

### 可复制工作流

```
1. 积极申请 AI 产品的 beta/early access
2. 加入产品的 Discord/社区，成为活跃用户
3. 产品更新时第一个发 Thread 分享体验
4. 如果有机会，争取成为 community champion / ambassador
```

---

## 15. ✨ Vibe Post — "不正经但有记忆点"（英文特有）

**定义：** 极短的、轻松的、带内部梗或幽默的帖子，不传递信息，纯粹经营人设和氛围。

**核心结构：** 一句话或一张图，让人会心一笑。

### 案例

**案例 A — @itsandrewgao** [Cognition creatine](https://x.com/itsandrewgao/status/1973443827194368084)（352 赞 · 35k 浏览 · 2025）

> 原文：who wants some @cognition creatine?

**创作方法：** 一句话 + 产品梗图。"creatine"（肌酸）暗示 Cognition 团队像健身一样疯狂。**35k 浏览说明轻松的内容也有传播力。**

---

**案例 B — @itsandrewgao** [Devin 工会](https://x.com/itsandrewgao/status/1965094568820703642)（85 赞 · 10k 浏览 · 2025）

> 原文：shoot, the devins heard about the cognition fundraise and are threatening to unionize

**创作方法：** 把 AI agent 拟人化（Devin 要组工会），用幽默方式暗示融资消息。**Vibe post 的隐含信息量可以很大——融资、产品进展、团队文化都在一句玩笑里。**

### 关键洞察

**Vibe Post 和中文「真情实感」的区别：** 中文真情实感是"我很累/很焦虑/很感慨"，基调偏沉重。英文 Vibe Post 是"哈哈我们公司很酷"，基调偏轻松。两者都建立真实人设，但情绪方向相反。

---

## 16. 📦 Open Source Drop — "代码都在这了"（英文特有）

**定义：** 把自己的项目/prompt/过程直接开源到 GitHub，推文只是通知——不教步骤，让读者自己去看代码。

**核心结构：** "I'm open sourcing [project]" + "Here's everything: [repo link]"

### 案例

**案例 A — @ammaar** [SkyRoads Codex 开源](https://x.com/ammaar/status/2030529307039437304)（524 赞 · 46k 浏览 · 2026）

> 原文：OK! I'm open sourcing all of the progress and learnings I've made so far, this includes: Every prompt I wrote along the way to steer Codex, its own approach, process, pitfalls. The current working Rust build which runs natively on Mac!

**创作方法：** 不写教程，直接开源 prompt + 代码 + 踩坑记录。**"Open source my learnings" 比 "Here's a tutorial" 在英文圈更有号召力——前者暗示你是 builder，后者暗示你是 teacher。**

### 关键洞察

**与中文「保姆级教程」的区别：** 中文教程手把手教每一步，面向小白。Open Source Drop 假设读者有能力自己读代码，只提供原材料。**中文圈帮你消化好了喂到嘴边，英文圈把食材给你自己做。**

### 可复制工作流

```
1. 做项目时把所有 prompt 和过程记录在 repo 里
2. 达到一个阶段后发推："I'm open sourcing everything"
3. 列出 repo 里包含什么（prompt, code, pitfalls）
4. 不写教程，让读者自己探索
5. 后续可以根据 Issue/Discussion 里的问题再写教程
```

---

## 17. 📖 Career Narrative — "从 A 到 B 的故事"（英文特有）

**定义：** 讲述个人职业旅程的长叙事——从哪里来、经历了什么、到了哪里。不是简短的感慨，而是完整的弧线。

**核心结构：** [起点身份] → [关键转折] → [现在的身份] + "From X to Y"

### 案例

**案例 A — @bentossell** [加入 Factory AI](https://x.com/bentossell/status/1968666196019974434)（605 赞 · 109k 浏览 · 2025）

> 原文：I'm excited to join @FactoryAI as Head of Dev Rel. [完整职业回顾：Product Hunt -> Makerpad -> 卖给 Zapier -> AI Newsletter -> AI Fund -> Factory] From not technical at all, to technical non-technical member of technical staff.

**创作方法：** "From not technical at all, to technical non-technical member of technical staff" 是全文的核心句——用身份变迁概括整个旅程。**Career Narrative 的钩子不是数字，而是身份转变。**

### 关键洞察

**与中文「真情实感」和「数据晒单」的区别：** 中文晒单靠数字（"30w"），中文感悟靠情绪（"中年危机"）。英文 Career Narrative 靠身份弧线（"from X to Y"）。这是文化差异——英文圈更推崇「reinvention narrative」（自我重塑叙事）。

---

## 总览：AI 可提效空间

各内容类型中，AI 能承担的工作比例：

```
中文通用类型：
🫶 真情实感     ▓░░░░░░░░░  ~0%    纯个人表达，不需要 AI
🔥 热点快评     ▓▓░░░░░░░░  ~10%   AI 辅助翻译，但速度靠人
🛡️ 避坑预警     ▓▓░░░░░░░░  ~15%   AI 辅助整理，但踩坑靠人
📖 保姆级教程   ▓▓▓░░░░░░░  ~30%   AI 辅助结构化，但操作靠人
💰 数据晒单     ▓▓▓░░░░░░░  ~30%   AI 辅助叙事包装，但数据靠人
💸 省钱攻略     ▓▓▓▓░░░░░░  ~40%   AI 辅助整理步骤，但方案靠人折腾
🔧 工具安利     ▓▓▓▓▓░░░░░  ~50%   AI 辅助写推文，人负责选品+试用
🧠 认知升级     ▓▓▓▓▓▓▓░░░  ~70%   AI 辅助结构化长文，人负责观点+经验
💡 概念翻译器   ▓▓▓▓▓▓▓▓░░  ~80%   AI 负责翻译/改写，人负责选题+比喻

英文独立类型：
🔥 犀利 Rant    ▓░░░░░░░░░  ~5%    真实情绪+具体案例，AI 帮不了
✨ Vibe Post    ▓░░░░░░░░░  ~0%    纯人设经营，梗和幽默不可自动化
📖 Career Nar. ▓▓░░░░░░░░  ~15%   AI 辅助结构化，但故事弧线靠人
🔑 Insider     ▓▓░░░░░░░░  ~10%   核心是身份资源，不是内容技巧
📦 OS Drop     ▓▓▓░░░░░░░  ~25%   AI 辅助整理 repo，但代码/prompt 靠人
💬 Engage CTA  ▓▓▓▓▓░░░░░  ~50%   AI 辅助生成内容，但 CTA 设计靠人
📢 Signal Bst  ▓▓▓▓▓▓▓░░░  ~70%   AI 辅助监控信息源，人选哪条转发
📋 Curator     ▓▓▓▓▓▓▓▓▓░  ~90%   AI 负责采集+整理，人负责筛选+排序
```

---

## KOC 养号的内容生产 SOP（基于 Claude Code）

基于以上逆向工程，结合 Claude Code + 已安装的 Skills 能力，大部分流程可以自动化。

### 自动化架构

```
信息采集（全自动）→ 选题判断（人工 2 分钟）→ 内容生成（半自动）→ 去 AI 味（人工 5 分钟）→ 发布
```

### 每日 SOP — 信息采集（全自动，Cron 定时）

用 Claude Code 定时任务自动采集信息源，每天早上生成「今日选题池」：

```bash
# 每日 8:00 自动运行，结果写入 content/daily_feed/YYYY-MM-DD.md

自动采集源：
1. GitHub Trending（Today / This Week）
   → Claude Code 用 WebFetch 抓取 https://github.com/trending
   → 提取 Top 10 项目名、Star 数、描述

2. Hacker News Show HN
   → 用 /niche-hn skill 自动抓取
   → 过滤 AI/开发者工具相关帖子

3. Product Hunt 每日新品
   → 用 /niche-ph skill 自动抓取
   → 提取 Top 5 AI 相关产品

4. 英文 AI 大V 推文
   → 用 x-tweet-fetcher 抓取 @AndrewYNg @karpathy @sama 等最新推文
   → AI 自动翻译+摘要

5. Anthropic / OpenAI / Google AI 博客
   → 用 agent-reach 的 Jina Reader 定时抓取
   → 检测新文章，自动翻译摘要

输出格式：
---
# 2026-03-18 选题池

## 🔧 可推荐的工具（3 个）
1. [工具名] - 一句话描述 - GitHub Star / PH 票数
2. ...

## 🔥 今日热点（2 个）
1. [事件] - 来源 - 为什么重要
2. ...

## 💡 可翻译的概念/文章（2 个）
1. [文章标题] - 来源 URL - 核心观点一句话
2. ...
---
```

### 每日 SOP — 选题+生产（人工 10 分钟 + AI 5 分钟）

```
[2 分钟] 看选题池，选 1-2 个今天要发的
  → 选题判断是人不可替代的核心价值

[5 分钟] Claude Code 生成推文草稿

  **中文号 Prompt：**

  工具安利：
  "读取 [工具 README/产品页]，写一条中文推文：
   - 开头：好奇钩子（'不敢相信…' '别再…了'）
   - 中间：3-5 个亮点，列表体 + emoji
   - 结尾：链接
   - 参考风格：@guishou_56"

  概念翻译：
  "翻译这篇文章核心观点，中文 800 字以内：
   - 用一个日常比喻开头
   - 提炼 3-5 个核心观点
   - 结尾：'这意味着…'
   - 参考风格：@fkysly '拉尔夫循环'"

  热点快评：
  "[事件]。50 字以内中文快评，事实+一句判断。参考：@op7418"

  **英文号 Prompt：**

  Tool recommendation：
  "Write a tweet about [tool]. Format:
   - Hook: 'You don't need X. You need Y.' or 'This just changed how I...'
   - 3-5 bullet points with WHY each matters
   - End: 'What tools would you add?'
   - Style ref: @nonmayorpete"

  Curator roundup：
  "Compile the top [N] [topic] from this week. Format:
   - '24 hours since [event]. Here are the [N] most [adjective] examples:'
   - Numbered list with one-line description each
   - End: 'What did I miss?'
   - Style ref: @heyBarsee"

  Hot take：
  "[Topic]. Write a contrarian take in 2-3 sentences.
   Be direct, even provocative. No hedging.
   - Style ref: @svpino or @bentossell"

[5 分钟] 人工增值（不可跳过）
  - 加入一句真实体验
  - 检查去 AI 味清单
  - 发布
```

### 每周 SOP — 长文创作（人工 30 分钟 + AI 15 分钟）

```
[10 分钟] 回顾本周做过的事，选一个值得写的
  - 踩过的坑 → 保姆级教程 或 避坑预警
  - 学到的东西 → 认知升级
  - 省钱的方法 → 省钱攻略
  - 达到的里程碑 → 数据晒单

[10 分钟] 口述核心内容（语音备忘录 / 笔记）

[15 分钟] Claude Code 整理成 Thread
  "把以下笔记整理成一条 Twitter Thread：
   - 开头要有反常识的钩子
   - 用 1/n 格式
   - 加入具体步骤/数字
   - 结尾给一个可操作的建议
   - 检查去 AI 味清单后输出"

[10 分钟] 人工修改：加个人故事、调语气、配图
```

### 每周 SOP — 自动复盘（全自动）

```bash
# 每周日 20:00 自动运行

用 x-tweet-fetcher 抓取本周发布的所有推文
  → 按互动数据排序
  → 分析哪种类型表现最好
  → 生成复盘报告写入 campaigns/koc/weekly_review/YYYY-WXX.md

报告格式：
---
本周发布：X 条
最高浏览：[推文] - XX k
最高互动率：[推文] - X.X%
内容类型分布：工具安利 X 条 / 热点 X 条 / ...
建议：下周多发 [类型]，减少 [类型]
---
```

### 可进一步自动化的环节

| 环节 | 当前 | 可升级为 |
|------|------|---------|
| 信息采集 | Cron 定时抓取 | MCP + RSS 实时推送，有新内容即通知 |
| 工具安利 | 手动选题 + AI 写 | GitHub Trending 自动筛选 AI 相关 → 自动生成草稿 → 人审核 |
| 热点快评 | 手动刷 Timeline | 监控英文大 V 推文 → 实时翻译 → 推送草稿到手机 |
| 发布 | 手动发布 | 用 baoyu-post-to-x skill 自动发布（已安装但需配置） |
| 复盘 | 每周手动 | x-tweet-fetcher Growth Tracker 自动追踪每条推文数据 |

---

## 11 种类型效能排名

按最高单条浏览量排序（含中英文数据）：

| 排名 | 类型 | 中文最高 | 英文最高 | 核心驱动力 | 建议频率 |
|------|------|---------|---------|-----------|--------|
| 1 | 📋 Curator 模式 | — | **51,900k** (Barsee) | 筛选+速度 | 热点时立即发 |
| 2 | 💰 数据晒单 | 466k (kasong) | 486k (ammaar) | 数字钩子 | 有了就发 |
| 3 | 📖 保姆级教程 | 245k (vista8) | 193k (nonmayorpete) | 实操价值 | 每周 1 篇 |
| 4 | 💡 概念翻译器 | 120k (fkysly) | 109k (dotey→bentossell) | 信息不对称 | 每周 1-2 条 |
| 5 | 🔧 工具安利 | 156k (guishou) | 193k (nonmayorpete) | 零成本价值 | 每日 1 条 |
| 6 | 🔥 犀利 Rant | — | 137k (bentossell) | 争议+共鸣 | 有真情绪时发 |
| 7 | 💸 省钱攻略 | 123k (fkysly) | — | 痛点精准 | 跟热点发 |
| 8 | 🧠 认知升级 | 166k (kasong) | 94k (svpino) | 认知冲突 | 每周 1 条 |
| 9 | 🔥 热点快评 | 62k (op7418) | 2,267k (AiBreakfast) | 速度+观点 | 实时跟 |
| 10 | 🫶 真情实感 | 79k (dev_afei) | 54k (ammaar) | 情感连接 | 自然发 |
| 11 | 🛡️ 避坑预警 | 68k (fkysly) | — | 损失厌恶 | 发现就发 |

---

## 各账号 × 内容类型矩阵

一图看清每个账号的内容侧重（●主力 ○偶尔 ·不涉及）：

**中文账号：**

| 账号 | 工具安利 | 保姆教程 | 热点快评 | 概念翻译 | 数据晒单 | 避坑预警 | 省钱攻略 | 认知升级 | 真情实感 | Curator | Rant |
|------|---------|---------|---------|---------|---------|---------|---------|---------|---------|---------|------|
| @dev_afei | ● | ● | · | · | ● | ○ | · | · | ● | · | · |
| @guishou_56 | ● | ● | · | · | · | · | · | ○ | · | · | · |
| @kasong2048 | · | · | · | · | ● | · | · | ● | ○ | · | · |
| @Astronaut_1216 | ○ | ● | ○ | · | · | ● | ● | · | ○ | · | · |
| @fkysly | ○ | ● | ● | ● | · | ● | ● | · | ○ | · | · |
| @thinkingjimmy | ○ | · | · | ● | ● | · | · | ● | ○ | · | · |
| @AxtonLiu | ○ | ○ | · | · | · | ○ | · | ● | · | · | · |
| @gefei55 | ○ | ● | · | · | · | · | · | ● | · | · | · |
| @vista8 | ○ | ● | · | ● | · | · | ○ | · | · | · | · |
| @op7418 | ● | · | ● | · | · | · | · | · | · | · | · |
| @dotey | · | · | · | ● | · | · | · | ○ | · | · | · |
| @nishuang | ● | · | · | · | · | · | · | · | · | · | · |

**英文账号：**

| 账号 | 工具安利 | 保姆教程 | 热点快评 | 概念翻译 | 数据晒单 | 避坑预警 | 省钱攻略 | 认知升级 | 真情实感 | Curator | Rant |
|------|---------|---------|---------|---------|---------|---------|---------|---------|---------|---------|------|
| @ramsri_goutham | · | · | · | · | ● | · | · | · | ○ | · | · |
| @itsandrewgao | · | · | · | · | · | · | · | · | ○ | · | ● |
| @AlphaSignalAI | · | · | ○ | ● | · | · | · | · | · | · | · |
| @nonmayorpete | ● | · | · | · | · | · | · | · | · | ● | · |
| @ammaar | · | · | · | · | · | · | · | · | ● | · | · |
| @mreflow | · | · | · | · | · | · | · | ○ | · | ● | · |
| @bentossell | · | ○ | · | · | · | · | · | · | ○ | · | ● |
| @heyBarsee | · | · | · | · | · | · | · | · | · | ● | · |
| @svpino | · | · | · | · | · | · | · | ● | · | · | ● |
| @AiBreakfast | · | · | ● | · | · | · | · | · | · | ○ | · |

---

## 去 AI 味清单

### 中文

| AI 典型痕迹 | 修改方向 |
|------------|---------|
| "值得注意的是" | 删掉，直接说 |
| "首先…其次…最后…" 过于工整 | 打乱顺序，或删掉一个 |
| 每段都是差不多长度 | 故意让某段短、某段长 |
| "这无疑是" / "不可否认" | 换成口语："说实话" / "我觉得" |
| 无任何个人经历 | 加一句"我之前也…" |
| 排比句式 × 3 | 删掉一个，或换成不同结构 |
| 完美的总分总结构 | 偶尔不写总结，留白 |
| emoji 数量过多且均匀分布 | 减少，或只在重点处用 |

### English

| AI tell | Fix |
|---------|-----|
| "It's worth noting that..." | Delete, just say it |
| "In today's rapidly evolving landscape..." | Cut the preamble, start with the point |
| "Delve into", "Leverage", "Utilize" | Use normal words: "look at", "use" |
| Perfect parallel structure × 3 | Break the pattern, vary sentence length |
| Every paragraph starts with a transition | Remove half the transitions |
| Ending with "In conclusion..." | Just stop. Or end with a question |
| No contractions (do not, cannot, it is) | Use contractions: don't, can't, it's |
| Overly balanced "on one hand... on the other" | Pick a side. Have an opinion |
