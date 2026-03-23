# Official X Guest RSS Catalog

## Overview
- Generated at: 2026-03-20T09:19:14Z
- Window: last 168 hours
- Handles checked: 3
- Posts discovered: 43
- Errors: 0

## @Gorden_Sun
- Posts in window: 18
- 2026-03-19T15:28:22Z | AI资讯日报，3月19日：https://gorden-sun.notion.site/3-19-AI-328594247325807db88ae98abc6dd98d?source=copy_link
  https://nitter.net/Gorden_Sun/status/2034653212196966691#m
- 2026-03-19T10:29:30Z | 谷歌Stitch更新 AI生成设计，更新了画布、Agent能力，新增语音输入，推出DESIGN.md目的是定义AI设计规范。 Stitch背后的模型是Gemini 3，前端设计审美不错，不过我觉得还是不如Variant AI（堪称AI生成UI届的Midjourney） 官方文档：https://stitch.withgoogle.com/docs/
  https://nitter.net/Gorden_Sun/status/2034578001095245830#m
- 2026-03-19T10:17:26Z | MolmoPoint：开源视觉模型 8B大小，基于Qwen3 8B，特点是没有视觉→坐标数字→文本的转换过程，而是直接从视觉特征中选择目标位置，视觉能力达到同等大小最佳，开源了通用视觉、GUI专用、视频专用3个版本的模型。 模型：https://huggingface.co/collections/allenai/molmopoint
  https://nitter.net/Gorden_Sun/status/2034574961793548701#m
- 2026-03-19T09:42:24Z | Chandra OCR 2：开源OCR模型 4B参数，评分比小红书开源的dots.ocr-1.5还高。 模型：https://huggingface.co/datalab-to/chandra-ocr-2
  https://nitter.net/Gorden_Sun/status/2034566145601331707#m
- 2026-03-19T03:36:55Z | MiroThinker-1.7：针对复杂任务强化的开源Agent MiroMind开源MiroThinker-1.7系列Agent基础设施，专门强化了长链条Agent任务能力和工具调用的能力，单任务最多300次工具调用。开源内容包括： · Agent框架：MiroFlow · 模型：MiroThinker-1.7和MiroThinker-1.7-mini · 数据集：MiroVerse · 评测脚本 Github：https://github.com/MiroMindAI/MiroThinker 论文：https://huggingface.co/papers/2603.15726
  https://nitter.net/Gorden_Sun/status/2034474169489113378#m

## @op7418
- Posts in window: 13
- 2026-03-20T02:29:55Z | Claude Code 官方远程连接 Telegram 和 Discord 插件配置流程。 具体的操作方式 - Telegram： 创建机器人： 在 Telegram 中打开 BotFather，创建后复制他给你的 Token 安装插件： /plugin install telegram@claude-plugins-official 配置 Token： /telegram:configure 使用命令启动： claude --channels plugin:telegram@claude-plugins-official Telegram 配对： 打开 Telegram 发送任何信息获取到配对码； 在 Claude Code 里面发送 /telegram:access pair 锁定访问权限： /telegram:access policy allowlist 具体的操作方式 - Discord： 创建 Discord Bot 并加进自己的服务器 ▫ 去 ￼ → New Application ▫ 创建 Bot，点「Reset Token」拿到 token ▫ 在 Bot 设置里打开 Message Content Intent ▫ 在 OAuth2 → URL Generator 里勾选 `bot` ▫ 然后给它这些权限：View Channels / Send Messages / Send Messages in Threads / Read Message History / Attach Files / Add Reactions ▫ 打开生成的链接，把 bot 邀请进自己的服务器 安装插件： /plugin install discord@claude-plugins-official 配置 Token： /discord:configure 命令启动 ClaudeCode： claude --channels plugin:discord@claude-plugins-official 配对 Discord 机器人： 私信你的机器人发配对码； 回到 Claude Code 发： /discord:access pair /discord:access policy allowlist
  https://nitter.net/op7418/status/2034819697858978070#m
- 2026-03-19T23:19:13Z | Claude Code 推出了官方可以远程连接 Telegram 和 discord 的 MCP 直接设置就可以用手机远程控制 CC
  https://nitter.net/op7418/status/2034771704313250096#m
- 2026-03-19T10:55:41Z | 飞书做了一个超安全且功能更强大的龙虾！ 前段时间，龙虾爆火的时候，飞书因为健全的生态和开放的接入方式，成为了大家国内接入龙虾的首选 IM 平台。 但是毕竟 龙虾 有自己的体系，还有很多安全性问题，所以导致飞书服务的 to B 企业其实很多时候很难自己部署，或者是不敢自己部署。 这次飞书直接把他们的 aily 升级了，升级成了一个更安全、跟飞书契合度更高，而且更懂你的企业和你的龙虾。 你可以一键配置，随后它会直接生成一个联系人作为你的助手。你可以直接让他进行回复，或者在飞书中跟他聊天、给他安排任务。 他能读取你飞书里的所有信息，并帮你完成任务。此外，他还可以调用一些常见工具，甚至获取飞书之外的信息。 而且可以自定义 Skills，比如说：你的日报、PPT、安排日程，这些都可以让它去帮你做。 更强的是，他们还有一个专业版的 Aily，在网页上使用，自带了超级多的 Skills。 比如我这里就让他查找了一下对应的一个群，然后让他总结群里的信息，同时写了一个网页可视化的展示这些信息。 这个对于我们日常的企业管理和一些群的维护是非常好用的，而且还可以自动发送到比如说群里，对吧？ 同时，它支持更多超长的指令和复杂任务拆解，以及定时任务。他还给这个 Aily 配备了 Agent 电脑，支持更稳定的调用。 我们都知道龙虾强就强在它丰富的生态，也就是那些 Skills。 这次除了官方内置的大量 Skills 以外，你还可以通过 aily 专业版自己创建 Skills，同时支持上传以前自己制作的 Skills。 这个功能非常厉害，可以将很多个人流程直接落地： 比如我之前做的一些“去 AI 味儿”的指令 还有一些视频剪辑或文本生成的 Skills 你完全可以将自己的工作流落地到 Skills 里，Agent 的创建门槛已经变得非常低了。 目前你可以飞书搜索 Aily，就可以开通 Aily 助手； 同时去网页版（aily.feishu. cn）可以使用专业版的 Aily，都有免费额度，可以去玩玩，非常好玩。
  https://nitter.net/op7418/status/2034584589986042298#m
- 2026-03-19T09:46:21Z | 试了一下 LibLib 发布的这个 LibTV，这个有点厉害啊！ 尤其是 Skills，感觉突然开窍了。 他们做了一个 AI 视频创作平台。这个系统是同时面向人类和 Agent 设计的： 人类可以操作、Agent 也可以操作、人类和 Agent 还可以相互协作 具体包括两个部分，网站和 Skills。 首先网站： 它是一个无限画布的创作形式，你能用现在几乎市面上所有的图像模型和视频生成模型去创建视频。 支持五种类型的节点：文本、图片、视频、音频和脚本。 如果你用过 ComfyUI 或者其他同类型的这种无限画布式的产品的话，应该很容易上手。 而且你可以在这里一次性充值，就能用到几乎所有的图像和视频生成模型，非常方便。 我试了一下，这部分优化也挺好的，交互各方面都很方便。你拉过去以后，它就能直接选择节点并出现对应的设置，还能实现自动化批量运行。 第二部分就是 Skills： 它的 Skills 支持它所有的功能。你只需要在你的账号右上角生成一个 API Key，然后把它的开源 Skills 地址发给：你的龙虾或者是你的 Claude Code或者 Codex 其实都可以。 然后你的 agent 就可以去调用 LibTV 里面几乎所有的能力和所有的模型，去帮你自动化地生产：视频、图片、脚本。 比如我就直接给了它我那个项目的 GitHub 地址，然后让它读取信息，帮我生成一个类似高级化妆品广告的，这样一个生活方式的产品广告片。 你原有的 AI Agent 里的所有能力都可以调用，自动生成脚本，然后从脚本变成图片，从图片生成视频和音频。 比如说你可以让你的龙虾收集器在晚上帮你收集好昨天的 AI 新闻，然后调用 LibTV 帮你做成播客，甚至可以调用 LibTV 帮你做成视频。 这样你早上起来就可以“收菜”了，无论是你自己看还是发布出去都可以。 甚至你在 Liblib. tv 上创建了自动化的生成，然后你出去以后如果懒得打开网站，你也可以让你的 AI Agent 查询生成进度。 同时，你的 AI Agent 也可以操作你的微调项目，这样的话在外面不方便打开网页的时候也可以工作。 他们在定价上也非常猛：年卡最低可以到 39 折，订阅用户最高赠送 150 条 可灵O3 和 150 条 可灵 3.0。
  https://nitter.net/op7418/status/2034567141819613664#m
- 2026-03-19T01:26:49Z | 早上就发了个小米的新闻，微信公众号那边，他妈的，那评论区乌烟瘴气的，都不能看。 很多翻起来还是关注了一年多的老粉。我在想，这帮逼关注了一年，关注点啥呀？我操，真丢人，教这些人
  https://nitter.net/op7418/status/2034441428051669153#m

## @AlphaSignalAI
- Posts in window: 12
- 2026-03-19T21:58:53Z | Math just got a compiler. Math, Inc. open-sourced OpenGauss, an AI agent that translates human math into machine-verifiable Lean proofs. → Beats rival agents with no time limit, using only 4 hours → Formalized the Strong Prime Number Theorem in 3 weeks vs. 18+ months for human experts → Runs many subagents in parallel Think of it like a compiler for mathematical truth: you write the idea, it generates code a machine can verify is correct. Math proofs that took top experts years can now be verified automatically, making formally verified AI training data finally scalable. https://github.com/math-inc/OpenGauss
  https://nitter.net/AlphaSignalAI/status/2034751488308723866#m
- 2026-03-19T15:05:23Z | x.com/i/article/203414257168…
  https://nitter.net/AlphaSignalAI/status/2034647427609751913#m
- 2026-03-18T23:36:34Z | x.com/i/article/203413395081…
  https://nitter.net/AlphaSignalAI/status/2034413681916936671#m
- 2026-03-18T20:37:33Z | An AI model just helped build the next version of itself. MiniMax released M2.7, a coding agent that handles 30-50% of its own training workflow autonomously. → 56% on SWE-Pro, near top global models → 66.6% medal rate on ML research competitions → Fixes live production bugs in under 3 minutes → 97% skill adherence across 40+ complex tasks The trick: it runs experiments, reads logs, debugs failures, then rewrites its own code over 100+ iteration loops. You can now point it at a real codebase and let it plan, execute, and self-correct end-to-end without babysitting every step. https://opencode.ai/go
  https://nitter.net/AlphaSignalAI/status/2034368632721936426#m
- 2026-03-18T12:01:54Z | Someone just built an OpenClaw robot that is shockingly aware. > Tracks who visited a room and when > Answers questions like "where did I last see my keys?" > Understands cause-and-effect across hours of footage Standard AI memory runs on text tokens. It has no sense of time or physical space. That breaks the moment you add video, depth sensors, or moving objects. OpenClaw solves this by storing space, objects, and time into a structured memory the robot can query later. Robots usually operate only in the present moment, reacting to sensor input without remembering the past. Now, they can build a running record of its environment and reason about it later. If this technology continues evolving, robots could begin to understand environments, track events, and reason about the physical world in ways that previously required human perception. Fully open-source.
  https://nitter.net/AlphaSignalAI/status/2034238865616093371#m
