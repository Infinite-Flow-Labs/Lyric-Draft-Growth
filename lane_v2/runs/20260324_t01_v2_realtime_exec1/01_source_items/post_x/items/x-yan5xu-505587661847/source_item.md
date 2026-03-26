# Source Item x-yan5xu-505587661847

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/yan5xu/status/2034812566980239392
- Author: yan5xu
- Published At: 2026-03-20T02:01:35Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 10

## Content Preview

Post title: 还是没忍住把 http://pinix.ai 买了，搓手手

Post summary: 还是没忍住把 pinix.ai 买了，搓手手 yan5xu (@yan5xu) epiral 2.0 来啦，不过重点不是 epiral（🦞），这次是 pinix，大概是东半球第一个专门为 agent 设计的 os hhh 春节在迭代epiral 的时候，撞上一个问题：Agent 只靠 IM 交互，很多场景都有点难受。 比如 todo。让 Agent 管理很顺——它自己调命令，增删改查，清清楚楚。但我自己想看一眼今天的任务呢？纯靠对话去问，怎么都不如一个列表界面来得直接。 于是想通了一件事，Agent 需要命令行，人需要界面，但它们操作的是同一个东西。所以 Agent 时代的 app 就该同时有两个入口。 所以就有了 pinix。上面的应用叫 clip。每个 clip 长这样：底层是一组命令脚本（或者二进制 cli），Agent 直接调；上层是一个 web 页面，人直接用。同一份数据，两种交互方式。 然后有意思的来了：Agent 本身也是一个 clip。 就是你们在用的龙虾——对话、记忆、工具调用、浏览器控制——我把它整个做成了 pinix 上的一个应用。它不是系统的主人，它是系统上跑的一个 app，跟 todo、跟沙盒平级。Agent 通过命令跟其他 clip 交互，装一个新 clip，Agent 就自动多一个新能力。 看图就懂了👇 四个画面，同一个 pinix 节点： 左一：Agent clip——刚帮我批量更新 todo 状态，调的是 clip todo task-update，返回结构化结果自动整理成表格 左二：todo clip——同一批任务，我直接在看板上看，按项目分组，拖拽排优先级。Agent 改的数据，这边实时看到 左三：Clip Dock（桌面端）——所有 clip 的入口，哪些在线一目了然 右一：todo clip 的 iOS 端——同一个 web 页面，手机上直接用 UI 选了 web，跨平台就不用做了——桌面套 WebView，iOS 套 WKWebView，一个下午两端全通。每个 clip 跑在独立微型虚拟机里，安全也是顺手的事。 — https://nitter.net/yan5xu/status/2031381139227816257#m

Canonical URL: https://x.com/yan5xu/status/2034812566980239392
