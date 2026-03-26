# Source Item x-idoubicc-24d5e5b67469

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/idoubicc/status/2035713349141643351
- Author: idoubicc
- Published At: 2026-03-22T13:40:58Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 14

## Content Preview

Post title: 微信 ClawBot 接入 OpenClaw 的原理，跟 Telegram 接入 OpenClaw，本质上是一致的👇 1. 微信实现了一个云端的中继服务 iLink 2. 微信实现了一个 OpenClaw 插件 openclaw-weixin 3. 用户在安装了 OpenClaw 的机器上安装 openclaw-weixin 插件，插件请求 iLink 服务，让用户扫码登录，登录凭证保存在 OpenClaw 的配置目录 4. openclaw-weixin 通过长轮询，拉 iLink 服务的消息，转发给 OpenClaw Gateway，调用 Agent Runtime 做任务（用户在微信 ClawBot 发消息） 5. openclaw-weixin 请求 iLink，把任务结果推送给用户（用户在微信 ClawBot 收到消息） ------ 简单总结就是这么个流程👇 微信 ClawBot -> 中继服务（公网部署） OpenClaw

Post summary: 微信 ClawBot 接入 OpenClaw 的原理，跟 Telegram 接入 OpenClaw，本质上是一致的👇 1. 微信实现了一个云端的中继服务 iLink 2. 微信实现了一个 OpenClaw 插件 openclaw-weixin 3. 用户在安装了 OpenClaw 的机器上安装 openclaw-weixin 插件，插件请求 iLink 服务，让用户扫码登录，登录凭证保存在 OpenClaw 的配置目录 4. openclaw-weixin 通过长轮询，拉 iLink 服务的消息，转发给 OpenClaw Gateway，调用 Agent Runtime 做任务（用户在微信 ClawBot 发消息） 5. openclaw-weixin 请求 iLink，把任务结果推送给用户（用户在微信 ClawBot 收到消息） ------ 简单总结就是这么个流程👇 微信 ClawBot -&gt; 中继服务（公网部署）&lt;- 桥接服务（长轮询）-&gt; OpenClaw idoubi (@idoubicc) 为什么不配置公网地址，也能在 Telegram 给电脑上的 Moltbot 发消息？主要是因为 Moltbot 的 Long Polling（长轮询）机制👇 1. 在 tg 创建机器人，把 token 填到 Moltbot 的配置文件 2. Moltbot 轮询 tg 的 API：/bot&lt;token&gt;/getUpdates?timeout=30，主动拉 tg 的消息 3. 用户在 tg 发的消息，被 Moltbot 拉到了，Moltbot 把消息发给 agent runtime(p-mono) 进行处理 4. Moltbot 把 agent runtime 的处理结果，调用 tg 的 API：/bot&lt;token&gt;/sendMessage 发给 tg 服务器 5. tg 服务器把消息推到用户对话框，完成一次交互 理论上，只要开放了拉消息和推消息 API 的 im 软件，都可以本地接入 Moltbot。官方支持 whatsapp、tg、discord 等，第三方实现了飞书机器人接入。 不支持长连接的 im 软件或机器人平台，比如企业微信、微信公众号等，则需要把 Moltbot 部署到公网（或内网穿透），然后再通过 Webhook（回调）模式接入，实现要复杂一些。 — https://nitter.net/idoubicc
