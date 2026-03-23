# Source Item x-op7418-a20aa8c443d2

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/op7418/status/2034082485798314489
- Author: op7418
- Published At: 2026-03-18T01:40:30Z

## Signals
- Release Signals: release
- Task Hints: release
- Fact Anchors: 19

## Content Preview

Post title: Claude Code 创建者写的如何使用和创建 Skills 如果你还不了解的话，强烈推荐看看！ Anthropic 内部现在有数百个 Skills 在用，从 API 文档到部署流程全覆盖。他们把这些经验总结出来了。 做个笔记📒： ====== Skills 不只是 Markdown 文件 很多人以为 Skills 就是写个 Markdown 文档，其实不是。Skills 是一个文件夹，里面可以放脚本、资源文件、数据，甚至注册钩子函数。 代理可以发现这些内容，读取它们，执行脚本，在特定时机触发钩子。这才是 Skills 最有意思的地方。 最好的 Skills 都在创造性地使用这些配置选项和文件夹结构。 ====== 九种 Skills 类型 Anthropic 把内部的 Skills 整理了一遍，发现它们基本归为九类。好的 Skills 能明确归入一类，混乱的 Skills 往往跨了好几类。 ------ 1. 库与 API 参考 解释怎么用某个库、CLI 或 SDK。可以是内部库，也可以是 Claude 经常搞错的常用库。 通常包含一个代码片段文件夹，加上一份"别踩这些坑"的清单。 比如： ▸ billing-lib — 你们内部计费库的边界情况和常见坑 ▸ internal-platform-cli — 内部 CLI 的每个子命令和使用场景 ▸ frontend-design — 让 Claude 更懂你们的设计系统 ------ 2. 产品验证 描述怎么测试或验证代码是否正常工作。通常配合 Playwright、tmux 这些工具。 验证 Skills 极其重要，值得让工程师花一周时间专门打磨。 可以让 Claude 录制测试视频，或者在每一步强制执行程序化断言。这些通常通过在 Skill 里放各种脚本实现。 比如： ▸ signup-flow-driver — 在无头浏览器里跑注册流程，每步都有状态断言钩子 ▸ checkout-verifier — 用 Stripe 测试卡驱动结账界面，验证发票状态 ▸ tmux-cli-driver — 测试需要 TTY 的交互式命令行工具 ------ 3. 数据获取与分析 连接你的数据和监控栈。可能包含带凭据的数据获取库、仪表盘 ID、常见工作流说明。 比如： ▸ datadog-metrics — 预设的仪表盘链接和常用查询 ▸ postgres-query-helper — 连接生产数据库的只读凭据和常用查询模板 ▸ user-analytics — 获取用户行为数据的脚本和分析模板 ------ 4. 业务自动化 自动化重复的业务流程。比如创建 Jira ticket、发 Slack 通知、更新文档。 这类 Skills 通常包含调用内部 API 的脚本，加上业务流程的说明。 比如： ▸ incident-reporter — 创建事故报告并通知相关人员 ▸ release-notes-generator — 从 Git 提交生成发布说明 ▸ onboarding-automation — 新员工入职的自动化流程 ------ 5. 代码脚手架 生成项目或组件的初始代码结构。包含模板文件和生成脚本。 比如： ▸ react-component-scaffold — 生成符合团队规范的 React 组件 ▸ api-endpoint-generator — 生成 API 端点的样板代码和测试 ▸ microservice-template — 创建新微服务的完整结构
