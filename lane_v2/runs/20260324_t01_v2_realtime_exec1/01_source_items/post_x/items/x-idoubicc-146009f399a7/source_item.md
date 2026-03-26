# Source Item x-idoubicc-146009f399a7

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/idoubicc/status/2036061283255275974
- Author: idoubicc
- Published At: 2026-03-23T12:43:32Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 19

## Content Preview

Post title: 哥你写的真好👍

Post summary: 哥你写的真好👍 Soran (@Soranlan) 微信 ClawBot 的万能钥匙 一行命令让所有 Agent 走同一扇门 1/5 · 一扇门，一把钥匙 微信官方上线了 ClawBot 插件，这是今年 Agent 生态最重要的入口之一 微信第一次对 AI Agent 开放消息通道 但这扇门，目前只给了 OpenClaw 一把钥匙。 你的 Claude Code、Cursor、Gemini、Kimi、Codex——全被挡在门外。 今天， @idoubicc 扔出了一个 MIT 开源的桥接工具：WeClaw。 一行命令，让所有被拦住的 Agent 名正言顺地走进同一扇门。 ↓ 2/5 · 架构：走正门，不翻墙 在此之前，社区的解法要么只针对一个模型（claude-code-wechat-channel 只支持 Claude Code）， 要么绕道飞书/企业微信（cc-connect），根本吃不到微信 ClawBot 原生的系统级交互 WeClaw 的定位： 唯一走微信 ClawBot 官方通道 + 支持任意 Agent 的桥接工具。 底层走的是微信官方 ilink 协议（ ilinkai.weixin.qq.com ）。53AI 技术拆解说得很清楚：ilink 本质上是一个与 AI 类型无关的通用消息通道 标准 HTTP 长轮询 + Token 认证。没有逆向，没有模拟协议。WeClaw 只是让其他 Agent 也能合法地走这条路 3/5 · 调度：手机变成全局遥控器 ① 电脑端一行命令启动 ② 手机微信扫码接入 ClawBot ③ 发消息默认给你的主力 Agent（比如设为 Claude Code） ④ 指令级热切换：在微信对话框敲 /cc 发给 Claude Code，/gm 发给 Gemini，/oc 发给 OpenClaw 自动发现本地的 OpenClaw / Claude Code / Codex / Gemini / Cursor / Kimi / OpenCode，其他 Agent 可自行配置。 底层支持 ACP / CLI / HTTP 三大接口。终端 Agent、桌面 Agent、Web Agent 全部打通。 4/5 · 执剑人：连接的执念 这套举重若轻的架构 出自前腾讯微信支付后台开发、独立开发者艾逗笔（ @idoubicc ） 看他的履历，你会发现一种极其清晰的技术惯性： MCP.so ：全球最大 MCP 应用市场（收录 18000+ 服务，被 a16z 报告引用，Google 搜索 "MCP Servers" 排名 #1） ShipAny：AI SaaS 开发框架（预售 4 小时破 $10K） WorkAny：桌面 Agent + 云端 Bot 他在腾讯做了 5 年微信支付的「支付连接」 裸辞后做的全是「工具连接」和「Agent 连接」 WeClaw 只是他对「连接」这件事的又一次肌肉记忆。 5/5 · 现实与终局 微信给 OpenClaw 开了一扇门，WeClaw 把这把钥匙配成了万能的。 但作为技术拆解，必须诚实交代它的初期局限： ⚠️ 早期属性：今天刚发布，必然有边缘 Bug ⚠️ 物理前提：本地桥接，电脑必须开着，Agent 得挂在后台 ⚠️ 生态灰度：目前微信 ClawBot 插件 iOS 先行 👇 如果微信完全放开，你最想把谁设成默认底层模型？ — https://nitter.net/Soranlan/status/203601489301
