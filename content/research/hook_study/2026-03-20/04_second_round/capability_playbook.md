# Second-Round Capability Playbook

日期：2026-03-20

## 目标

第二轮不是继续“总结样本很优秀”，而是把样本里的稳定经验抽成后面可以反复复用的能力模块。

本轮结论基于两类输入：
- 新抓白名单 `article-like`：32 条
- framework 既有样本源：105 条
- 合并去重后研究池：85 条

上游研究池：
- [hook_study_pool.md](/home/lyric/growth-engine-pipeline/content/research/hook_study/2026-03-20/03_combined_pool/hook_study_pool.md)
- [hook_study_pool.json](/home/lyric/growth-engine-pipeline/content/research/hook_study/2026-03-20/03_combined_pool/hook_study_pool.json)

## 先明确一件事

白名单 `article-like` 并不等于“高质量标准样本”。

这一批里混着三类东西：
- 真正值得学的 article 入口或长帖包装
- 带一点观点和结构的转述包装
- 纯引流、纯站台、纯 `x.com/i/article/...` 外链壳

后续做 writer 学习时，必须先过滤掉第三类，不然会把“夸张站台、无实质 thesis、只有引流口吻”的坏味道学进去。

## 样本筛选规则

只有满足下面 4 条中的至少 3 条，才应该进入“可学习样本”集合：

1. 有明确 thesis，而不是只在转发/推荐别人。
2. 有至少一种证据展开：结果、过程、机制、对比、场景、清单。
3. 有正文节奏变化，而不是一口气说到底。
4. 有收束动作：判断、行动、边界、风险、上提一层。

应剔除的噪音样本：
- 纯站台：`关注 XXX 老师不会错`
- 纯链接壳：正文只剩 `x.com/i/article/...`
- 纯二次包装：自己没有 thesis，只把别人的文章再喊一遍
- 纯夸张收入诱饵：只有数字，没有过程和判断

## 我们真正要沉淀的 5 个能力

### 1. Title Hook

`title_hook` 的工作不是“把话说完整”，而是先打破默认理解，再把读者拉进这篇文章真正值钱的位置。

高频且稳定的 5 种标题动作：

1. 旧框架失效
- 例：`Mamba-2 赢在训练，Mamba-3 却把战场改到了推理`
- 适用：`article_x`、`podcast`、一部分 `official_x`
- 价值：让读者意识到“我之前理解这件事的方式已经不够了”

2. 大结果先打出来，再主动降温
- 例：`250 Meetings in 98 Days to $1.5M`
- 例：`一个月赚到特斯拉` 后马上承认“只是首付”
- 适用：`01_money_proof`
- 价值：先吸引，再防标题党反感

3. 发布信号转成采用判断
- 例：`How to run subagents in Codex`
- 例：`Claude 给了你 1M Token，但别真的全塞满`
- 适用：`official_x`、`article_x`
- 价值：不把标题浪费在“发布了”，而是直接打“怎么用/怎么判断”

4. 强反差或错位
- 例：`Productive Individuals Don't Make Productive Firms`
- 例：`龙虾刷屏全中国，硅谷却在打哈欠`
- 适用：`03`、`07`
- 价值：建立 tension，迫使读者继续往下读

5. 完整性承诺 / 筛选承诺
- 例：`一文讲全`
- 例：`实测 20 款`
- 适用：`06_checklist_template`、`05_ab_benchmark`
- 价值：降低读者搜索成本，承诺“我替你做了筛选和组织”

稳定复用要求：
- 标题里必须有 `旧理解 -> 新判断`、`大结果 -> 降温`、`发布 -> 采用`、`对比 -> 张力`、`完整性 -> 节省时间` 里的至少一种。
- 不能只写中性说明句。
- 不能只把 source 名和主题堆在一起。

### 2. Dek Function

`dek` 不是标题复述，也不是第二个摘要。

它在高质量样本里的真实任务是：
- 告诉读者“这篇真正值钱的地方在哪里”
- 给标题做第二次攻击
- 替文章定阅读合同：这不是普通发布、普通采访、普通教程

高质量 `dek` 的稳定功能：

1. 把文章重心拨正
- 例：不是“又发了个东西”，而是“判断方式变了”

2. 把标题的 hype 变成更可信的 stakes
- 例：不是为了更炸，而是为了告诉读者这件事会改写什么

3. 明确这篇会解决什么误判
- 例：这不是在教你更会 prompt，而是在解释为什么问题出在系统设计

稳定复用要求：
- `dek` 必须回答“这篇最值钱的点是什么”
- 不能只是换词复述标题
- 不能写成空泛情绪句

### 3. Opening Move

高质量开头最稳定的结构不是“背景介绍”，而是三步：

1. 先立旧理解 / 常见误判 / 默认视角
2. 立刻打破它
3. 再把 source 主体、这篇价值和 reader stake 接进来

这也是为什么很多样本的第一段并不“完整介绍背景”，而是先让读者感到：
- 自己原本的理解可能错了
- 这件事不是表面上那样
- 说这话的人/做这件事的人值得看

开头必须解决的 4 个问题：
- 这篇为什么现在值得看
- 这不是普通哪一类内容
- 主体是谁 / 为什么值得信
- 后文最值得拿走的判断是什么

这一步尤其要修正当前 writer 常见问题：
- 主体身份不清
- 一上来先讲背景
- 开头像解释器，不像文章

### 4. Mid-Article Attention Reset

这是第二轮最重要的新结论。

真正好的文章不是只有开头有钩子，而是中段会反复“重抓”读者。

稳定规律是：
- 不能连续 3 到 4 段都只做同一种解释动作
- 基本每 2 到 4 段就要出现一次 attention reset

最常见的 6 种 `mid reset`：

1. 更重的判断
- 从“这是个 feature”升级成“它在改写判断框架”

2. 换视角
- 从用户体验切到工作流
- 从产品切到组织
- 从结果切到机制

3. 抽象转具体
- 用一个场景、动作、角色、失败点把前面的抽象论点落下来

4. 主动回应怀疑
- 例：这不是模板垃圾、不是标题党、不是参数表 hype

5. 抬高 stakes
- 从“这个工具很好用”抬到“这会改变谁更有优势”

6. 结构性格式变化
- 小标题
- 点列
- 引用
- 链接 CTA

注意：
- 排版只是辅助
- 真正的 `mid reset` 还是认知动作，不是“多加几个小标题”

### 5. Closing Carry

高质量结尾不是重复 thesis，也不是流程话术，更不是“这里先拆到这，后面再说”。

好结尾稳定在做一件事：
- 把这篇从局部事实重新抬高一层

最常见的 4 种 `closing carry`：

1. 工具层 -> 工作流层
- 这不是某个功能，而是工作方式变化

2. 个案层 -> 普遍判断
- 这不是某一个人的成功，而是某类路径成立了

3. 发布层 -> 采用判断
- 这不是消息，而是一个该不该接入的决策

4. 结论层 -> 未决问题 / 风险 / 下一步判断
- 让读者带着判断离开，而不是带着摘要离开

必须避免：
- 再说一遍前文
- 突然掉进流程说明
- 以写作过程、管道过程结尾

## 第二轮确认下来的“全局反模式”

这些是后面应该显式禁止 writer 学进去的东西：

1. 背景先行
- 先讲背景，再讲人物，再讲为什么重要

2. 标题是说明句
- 说清了，但没拉力

3. `dek` 复述标题
- 让第二击白白浪费

4. 主体匿名
- 像 `vi Mowshowitz` 这种读者根本不知道是谁

5. 中段平推
- 连续几段全是同密度解释，没有节奏变化

6. 列表替代论证
- 只有点列，没有解释和判断

7. 结尾掉进流程话术
- 例如“后面如果稳定，再继续拆成 thread / post”

8. 学到白名单里的坏样本
- 站台、引流、链接壳、空转述

## 这 5 个能力如何接回系统

后续不要把它们继续写成“散落在 prompt 里的感觉性要求”，而应该变成明确 packet。

建议的 writer 输入能力包：

1. `title_attack_packet`
- `old_frame`
- `replacement_frame`
- `stakes`
- `anti_hype_clause`
- `allowed_title_moves`

2. `dek_value_packet`
- `real_value_of_piece`
- `not_just_a`
- `reader_payoff`

3. `opening_value_packet`
- `who_or_what_matters`
- `why_now`
- `opening_break_move`
- `identity_anchor`

4. `mid_reset_plan`
- `reset_count_min`
- `allowed_reset_moves`
- `section_turn_targets`

5. `closing_carry_packet`
- `carry_level`
- `closing_question_or_judgment`
- `forbidden_endings`

这些 packet 的来源应该优先是：
- source
- framework sample refs
- 第二轮研究结论

而不是继续让我凭感觉补。

## 当前推荐顺序

1. 先把这份 playbook 变成结构化 JSON。
2. 再从里面选最小必要字段接回 `rewrite_context`。
3. 最后才调 writer。

不建议跳过第 2 步直接改 prompt。
