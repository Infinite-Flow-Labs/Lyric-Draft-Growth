# Source Item x-dotey-76be1937abae

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/dotey/status/2036530915103612976
- Author: dotey
- Published At: 2026-03-24T19:49:41Z

## Signals
- Release Signals: 
- Task Hints: opinion_decode
- Fact Anchors: 19

## Content Preview

Post title: 今天刚发生的重大安全事件，Karpathy 亲自发帖警告。 litellm 被投毒：一次教科书级的供应链攻击 今天（3月24日），AI 开发者常用的 Python 库 litellm 在 PyPI 上被植入恶意代码。版本 1.82.8 在 UTC 时间 10:52 发布到 PyPI，包含一个名为 litellm_init.pth 的恶意文件，会在每次 Python 进程启动时自动执行。不需要你主动调用这个库，装上就中招。 litellm 是干什么的？它是一个统一调用各家大模型 API 的 Python 库，GitHub 超过 4 万星，每月下载量超过 9500 万次。很多 AI 工具链都依赖它，包括 DSPy、MLflow、Open Interpreter 等，总共有 2000 多个包把它当作依赖项。 也就是说，你可能从来没有手动安装过 litellm，但你用的某个工具替你装了。 恶意代码会系统性地收集主机上的敏感数据：SSH 密钥、AWS/GCP/Azure 云凭证、Kubernetes 密钥、环境变量文件、数据库配置，甚至加密货币钱包。收集完毕后加密打包，发送到攻击者控制的域名。 如果检测到 Kubernetes 环境，恶意代码还会利用服务账户令牌在集群的每个节点上部署特权 Pod，进行横向扩散。 怎么发现的？攻击者自己写了个 bug 发现过程颇具讽刺意味。FutureSearch 的 Callum McMahon 在 Cursor 编辑器里用了一个 MCP 插件，这个插件间接依赖了 litellm。恶意 .pth 文件在每次 Python 启动时都会触发，子进程又触发同一个 .pth，形成指数级的 fork bomb，直接把机器内存撑爆了。 Karpathy 在推文里说得很清楚：如果攻击者没有在写恶意代码时犯这个 bug，这个投毒可能好几天甚至好几周都不会被发现。 攻击链：安全工具反成突破口 根源在于 litellm 的 CI/CD 流程中使用了 Trivy（一个漏洞扫描工具），而 Trivy 本身在 3 月 19 日就已经被同一个攻击组织 TeamPCP 攻陷了。攻击者通过被污染的 Trivy 窃取了 litellm 的 PyPI 发布令牌，然后直接往 PyPI 上推送了带毒版本。 litellm 1.82.7 在 UTC 10:39 发布，1.82.8 在 10:52 发布，两个版本都包含恶意代码。 时间线更完整地看：3月19日 TeamPCP 攻陷 Trivy，3月23日攻陷 Checkmarx KICS，3月24日轮到 litellm。Wiz 安全研究员 Gal Nagli 的评价是：开源供应链正在形成连锁崩塌，Trivy 被攻破导致 litellm 被攻破，数万个环境的凭证落入攻击者手中，而这些凭证又会成为下一次攻击的弹药。 攻击者还试图“灭口” 社区成员在 GitHub 上提交 issue 报告此事后，攻击者在 102 秒内用 73 个被盗账号发了 88 条垃圾评论试图淹没讨论，然后利用被盗的维护者账号把 issue 关闭。社区不得不另开 issue 并转移到 Hacker News 继续讨论。 Karpathy 借此事重提了他对软件依赖的警惕态度：供应链攻击是现代软件中最可怕的威胁，每次安装一个依赖，都可能在依赖树的深处引入一个被投毒的包。他现在越来越倾向于用大模型直接生成简单功能的代码，而不是引入外部依赖。 如果你的环境中有 litellm，立刻运行 pip show litellm 检查版本。1.8
