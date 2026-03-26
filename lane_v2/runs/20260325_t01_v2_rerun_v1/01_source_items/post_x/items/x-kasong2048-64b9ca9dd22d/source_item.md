# Source Item x-kasong2048-64b9ca9dd22d

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/kasong2048/status/2036297006961009108
- Author: kasong2048
- Published At: 2026-03-24T04:20:13Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 15

## Content Preview

Post title: 如果你想尝试 Harness Engineering，我建议从「构建 约束环境 开始」 设想，任何时候，你问 Agent 任何项目问题，Agent 要做的第一步永远是：了解足够的项目背景。 所以，「能让 Agent 快速检索需要的项目背景」是第一要务。 比如： 文件目录层面：语义化的路径 Agent 最常用的命令就是 ls，如果路径能表达业务边界与归属，能极大减少 Agent 检索的成本 比如，好的： - billing/invoices/compute.ts - auth/tokens/verify.ts - web/routes/orders/[orderId]/loader.ts 坏的： utils/helpers.ts common/index.ts shared/misc.ts 代码架构层面：模块分层设计，单向依赖 比如，代码按如下功能分层，每一层只能依赖上一层的数据： Types -> Config -> Repo -> Service -> Runtime -> UI Agent 只要确认“当前用户需求属于哪个层级的范畴”就能快速定位改动范围与上下文（因为依赖都是单向的） 以上这些约束依靠如下方式保证落地： 1. 代码生成时的规范（AGENTS.md 中的要求） 2. Linter、测试 的强制约束，没过约束不能提交代码 2. 定期的 Agent 自动 Review

Post summary: 如果你想尝试 Harness Engineering，我建议从「构建 约束环境 开始」 设想，任何时候，你问 Agent 任何项目问题，Agent 要做的第一步永远是：了解足够的项目背景。 所以，「能让 Agent 快速检索需要的项目背景」是第一要务。 比如： 文件目录层面：语义化的路径 Agent 最常用的命令就是 ls，如果路径能表达业务边界与归属，能极大减少 Agent 检索的成本 比如，好的： - billing/invoices/compute.ts - auth/tokens/verify.ts - web/routes/orders/[orderId]/loader.ts 坏的： utils/helpers.ts common/index.ts shared/misc.ts 代码架构层面：模块分层设计，单向依赖 比如，代码按如下功能分层，每一层只能依赖上一层的数据： Types -&gt; Config -&gt; Repo -&gt; Service -&gt; Runtime -&gt; UI Agent 只要确认“当前用户需求属于哪个层级的范畴”就能快速定位改动范围与上下文（因为依赖都是单向的） 以上这些约束依靠如下方式保证落地： 1. 代码生成时的规范（AGENTS.md 中的要求） 2. Linter、测试 的强制约束，没过约束不能提交代码 2. 定期的 Agent 自动 Review

Canonical URL: https://x.com/kasong2048/status/2036297006961009108
