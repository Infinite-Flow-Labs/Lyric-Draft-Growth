# 02_launch_application 样本拆解

说明：以下拆解基于 `seed_articles_30d.reclassified.json` 中 `02_launch_application` 的 8 篇样本全文，不是只看标题或摘要。

---

## 1. 2033651724603240688

### 标题

How to run subagents in Codex

### 作者

@emanueledpt

### 子模式

`feature_playbook`

### stance

`instructional`

### release_signal

Codex 刚发布 subagents，新的并行子代理能力可用。

### reader_problem

读者听到“subagents”这个词，但不知道它实际解决什么问题，也不知道该怎么用。

### core_promise

把 subagents 从“新功能名词”翻译成可立即采用的工作方式、配置思路和使用边界。

### hook_move

先给发布消息，再立刻补一句 “Here's everything you need to know”，把新闻钩子转成采用钩子。

### proof_mode

- 白话机制解释
- prompt 示例
- model 选择建议
- best use cases
- when not to use

### reusable_parts

- 先解释旧工作流的噪音问题，再引出新 feature
- 用一个 prompt 例子快速落地
- 正反场景并列，帮读者做采用判断

### non_reusable_parts

- 对 Codex 内置 agent 名称和模型名的具体引用
- 特定 prompt 文案

### style_cue

英语技术帖的典型“清晰分段 + 快速定义 + 直接给例子”，像一个熟悉产品的人在做高密度入门说明。

---

## 2. 2033848539332415986

### 标题

清华团队开源 AI 课堂，人人都能学起来

### 作者

@oran_ge

### 子模式

`release_showcase`

### stance

`enthusiastic`

### release_signal

清华团队把 OpenMAIC 开源了。

### reader_problem

读者不知道 OpenMAIC 到底是什么，也不知道它与普通 AI 对话产品有何不同。

### core_promise

用最短时间让读者理解这款产品的定位、体验方式和典型场景，从而产生“想去试一下”的冲动。

### hook_move

先说“开源了个好东西”，再用“高级版 NotebookLM”做一秒钟定位。

### proof_mode

- 一句话定位
- 快速上手说明
- 多个使用场景
- 教育意义收束
- 链接出口

### reusable_parts

- `简单说，它是...` 这种白话定位
- 先讲怎么用，再给具体场景
- 用“大家都在怎么玩”把功能变成体验想象

### non_reusable_parts

- 清华团队的权威背书
- OpenMAIC 的具体产品名和链接

### style_cue

中文 AI 产品分享里比较顺滑的一种写法：低门槛定义、快速举例、把抽象功能翻成人人能想象的学习场景。

---

## 3. 2032283258650759362

### 标题

90%的亚马逊选品还不如算命，AI选品系统发布！！

### 作者

@bggg_ai

### 子模式

`pain_to_adoption`

### stance

`instructional`

### release_signal

作者发布了一套 AI 选品系统，并公开说明其工作逻辑和操作方式。

### reader_problem

跨境卖家知道要看数据，但现有选品流程依然依赖拍脑袋，指标过载却没有可执行结论。

### core_promise

把“数据很多但不会用”的痛点，转成一个能直接输出判断和策略的系统采用路径。

### hook_move

先用“90% 选品像算命”猛烈打穿旧认知，再把自己的系统命名成“选品算命”。

### proof_mode

- 旧流程痛点
- 仪表盘 walkthrough
- 评分逻辑解释
- AI 对话示例
- 数据导入与建模步骤

### reusable_parts

- 先打旧方法，再抬新方法
- 用控制台和操作路径证明不是空口卖点
- 既讲系统怎么判断，也讲系统怎么落地

### non_reusable_parts

- 飞书多维表格、卖家精灵、宠物类目等强业务细节
- “算命/排盘/吉凶”这套品牌化修辞

### style_cue

强销售转化感的产品文，但正文靠 dashboard、流程和评分逻辑撑住，不是单纯情绪营销。

---

## 4. 2033420708815208868

### 标题

龙虾专属模型来了，给你的虾换个好脑子吧

### 作者

@oran_ge

### 子模式

`pain_to_adoption`

### stance

`enthusiastic`

### release_signal

智谱发布了专门面向 OpenClaw/“龙虾”场景的 GLM-5-Turbo。

### reader_problem

现有模型更像“聊天脑”，在 Agent 场景下经常不稳定、不好用、不像真正能干活的大脑。

### core_promise

把“模型升级”翻译成“龙虾终于有了能干活的大脑”，并通过真实任务证明新模型值得采用。

### hook_move

从线下交流里发现的真实问题切入，不是从参数表或跑分开局。

### proof_mode

- 旧模型失灵场景
- 跑分背书
- 浏览器 / 多媒体 / 定时任务等真实任务测试
- 套餐和价格

### reusable_parts

- 先建错误基线，再说明新模型带来的质变
- 用多个具体任务证明“能干活”
- 从体验感受过渡到采用动作

### non_reusable_parts

- “龙虾”“好脑子”这套具体隐喻
- 智谱、GLM-5-Turbo、ListenHub 等具体产品名

### style_cue

口语强、画面感强、产品经理式体验分享和 KOC 式兴奋感混在一起，但中间用真实任务测试防止文章飘掉。

---

## 5. 2032978239853826228

### 标题

Claude 给了你 1M Token 的上下文，但别真的全塞满

### 作者

@xxx111god

### 子模式

`feature_playbook`

### stance

`corrective`

### release_signal

Anthropic 开放 1M context window，且取消长上下文溢价。

### reader_problem

读者容易把“上下文变大”误解成“从此什么都可以塞进去”，忽略了使用方式才是真正瓶颈。

### core_promise

借发布消息完成一轮采用纠偏：告诉读者 1M context 的真实意义、真实限制和正确使用习惯。

### hook_move

先承认“这绝对是好事”，立刻接一个“但”，把热情转成判断。

### proof_mode

- 机制解释
- Reddit 用户反馈
- Claude Code 自己的 context compaction
- 个人实践经验
- 最终 best practices

### reusable_parts

- 发布消息只是入口，真正主体是采用纠偏
- 多层证据堆叠：原理、社区反馈、官方做法、个人经验
- 结尾给出一组明确行动建议

### non_reusable_parts

- Attention Sink、RoPE、context compaction 等具体术语
- Anthropic 和 Claude 的品牌上下文

### style_cue

这种样本的核心不是“介绍新功能”，而是“别被发布消息误导”。语气里有节制的兴奋，也有很强的技术现实主义。

---

## 6. 2032044423413182827

### 标题

《OpenClaw 从入门到精通指南》正式发布，开源免费！

### 作者

@canghe

### 子模式

`release_showcase`

### stance

`craftsmanship`

### release_signal

一份打磨很久的 OpenClaw 开源指南正式发布。

### reader_problem

初学者安装和理解 OpenClaw 很痛苦，而市面上很多材料要么不够细，要么不够接地气。

### core_promise

让读者相信这份指南值得收藏，因为它不是资料堆砌，而是基于大量亲身实践打磨出的入门到应用路径。

### hook_move

不是先吹内容，而是先讲“我们做了很久、手动敲了很多字、每一步都亲自实践过”。

### proof_mode

- 制作过程
- 覆盖内容
- 入门痛点
- 实际应用场景
- skill 推荐和打包

### reusable_parts

- 用制作过程本身证明质量
- 先解决“为什么这份资料值得信”
- 把“内容丰富”翻译成“拿来就能用”

### non_reusable_parts

- 团队协作背景
- OpenClaw 具体生态和团队成员名

### style_cue

强烈的“实践者背书”风格，不像官方文档发布，更像一个真的做过很多坑的人，把成果交给你。

---

## 7. 2033636057690800452

### 标题

You Should Be Using Subagents in Codex!

### 作者

@reach_vb

### 子模式

`feature_playbook`

### stance

`instructional`

### release_signal

Codex 支持 subagents，可以显式生成并行子代理。

### reader_problem

读者知道这个 feature 名字，但不清楚其运行方式、配置边界和最佳实践。

### core_promise

把 subagents 讲成一个清晰的运行模型，并给出正确的 agent 设计和使用原则。

### hook_move

开头不做铺垫，直接定义 subagents 是什么，以及它们在 runtime 中怎么存在。

### proof_mode

- 运行模型定义
- 自定义 agent 配置字段
- global limits
- role split 示例
- tips and principles

### reusable_parts

- 先定义，再限制，再给好用模式
- 很适合“功能本身需要概念澄清”的发布文
- 用 role example 帮读者看到用法，而不是只看配置项

### non_reusable_parts

- 特定配置字段和官方文档链接
- Codex 内部术语

### style_cue

比普通 KOC 文更接近 docs-to-human 的技术说明，句子完整、边界清楚，但仍保留“你应该这么用”的主张性。

---

## 8. 2032316152375099424

### 标题

这应该使用 OpenClaw 最简单的方案了，点击安装就能用，1 分钟绑定微信，直接在微信里让电脑干活。

### 作者

@ityouknows

### 子模式

`pain_to_adoption`

### stance

`instructional`

### release_signal

腾讯最新版 WorkBuddy 提供了更低门槛的 OpenClaw 使用方案。

### reader_problem

Windows 下命令行安装 OpenClaw 成本太高，普通用户容易卡在环境和配置问题里。

### core_promise

把复杂开源软件采用路径改造成产品化 onboarding，让普通用户也能快速上手。

### hook_move

直接从“命令行安装太费劲了”开场，立刻把产品化方案摆出来。

### proof_mode

- 安装步骤
- 注册和领取积分
- 微信绑定流程
- 主界面功能说明
- 群入口和后续资源

### reusable_parts

- 先建门槛，再强调“现在变简单了”
- 细步骤和利益点一起给
- 产品化差异一定要说透：为什么比开源原版顺滑

### non_reusable_parts

- 腾讯、WorkBuddy、微信绑定等强平台细节
- 积分赠送和社群导流

### style_cue

典型的“上手门槛降低型”文章，口气直接、动作密集、步骤完整，像一个已经替你踩过坑的人在带你装。

---

## 初步观察

`02_launch_application` 的共同点，不是“发布了就写”，而是：

- 有一个明确的新东西出现了
- 文章必须把这件事翻译成采用判断
- 中段必须回答“怎么开始”或“为什么值得试”
- 不能停留在产品宣传或新闻转述

从 8 篇样本看，这个父框架最稳的不是继续往下平铺出很多框架，而是收束成 3 个子模式：

- `feature_playbook`
- `pain_to_adoption`
- `release_showcase`

其中 `feature_playbook` 内部可以接受 `instructional` 和 `corrective` 两种口吻，但不需要因此新增一级框架。
