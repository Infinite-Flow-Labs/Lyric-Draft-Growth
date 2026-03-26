# 05_ab_benchmark 样本拆解

说明：以下拆解基于 `seed_articles_30d.reclassified.json` 中 `05_ab_benchmark` 的 2 篇样本全文。当前样本量偏少，结论仅作低置信度版本。

---

## 1. 2033748548915741131

### 标题

OpenClaw免费开源本地记忆系统：Tokens节省近 35.24%， 自动生成 Skill，越用越聪明

### 作者

@lxfater

### 子模式

`alternative_benchmark`

### problem

OpenClaw 长对话丢记忆、磨洋工、耗 token，普通用户体验差。

### comparison_lens

- 更好的模型
- 找合适的 skill
- 外接本地记忆系统

### core_decode

文章真正做的不是介绍一个项目，而是先否掉社区里最常见的两种解法，再把一个新的开源项目放上来作为更现实的折中解。

### hook_move

先从吐槽图和真实痛点切入，不是从项目功能切入。

### proof_mode

- 痛点复述
- 两种旧解法的缺点
- 安装配置
- 节省比例
- 自动进化机制

### reusable_parts

- 先立痛点，再做路线比较
- 把“为什么另外两种不现实”讲清楚
- 推荐方案要带安装和原理，不然像广告

### non_reusable_parts

- OpenClaw / MemOS / embedding 模型等具体生态和参数

### style_cue

这类样本更像“替你排雷后给一个更现实解”，不是纯产品介绍。

---

## 2. 2031922182436323468

### 标题

实测20款 OpenClaw 产品！腾讯阿里字节华为百度小米全线下场，最快部署仅需 1 分钟？（全名单）

### 作者

@ityouknows

### 子模式

`market_shortlist`

### problem

OpenClaw 类产品突然很多，普通用户根本不知道从哪里开始选。

### comparison_lens

- 部署速度
- 使用门槛
- 公司类型
- 体验和完成度

### core_decode

这篇的真实任务不是“测试 20 款”，而是替读者把市场快速分区、筛到值得关注的 shortlist，并把“最快能用”的那一个点出来。

### hook_move

先用“实测 20 款”“最快 1 分钟”建立极强筛选承诺。

### proof_mode

- 大盘覆盖
- 分类分组
- 代表产品点评
- 最终推荐
- 文档资源与社群导流

### reusable_parts

- 用大盘感建立权威
- 用分类分组降低复杂度
- 最终必须有 shortlist，不然信息太散

### non_reusable_parts

- OpenClaw 国内产品图谱和具体厂商信息
- 飞书妙搭等具体推荐

### style_cue

更像市场 roundup，但真正的价值点在于“已经替你先看了一圈，最后告诉你先看哪几个”。

---

## 初步观察

`05_ab_benchmark` 当前样本只有 2 篇，但至少可以确认：

- 它不是单纯的发布文
- 也不是普通产品介绍
- 它真正稳定的任务是：替读者完成第一轮筛选

后续如果继续补到 5 篇以上，再重新验证边界更稳妥。
