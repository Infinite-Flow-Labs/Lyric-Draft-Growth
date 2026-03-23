# Source Item x-chuhaiqu-978b8c1203e1

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/chuhaiqu/status/2034229910043001141
- Author: chuhaiqu
- Published At: 2026-03-18T11:26:19Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 18

## Content Preview

Post title: 我觉得 AI agent 真正该做的应该是像 Ernesto 他们做的那样 可以帮忙接管一个完整的业务闭环的（在用 TikTok 做增长的朋友一定要看看）。 他们其中一个 app 年收入 30 万美金，最开始靠的是 4 条 TikTok Spark Ads 撑了整个增长周期。后来这 4 条广告跑死了，他们没有去手动做新的，而是用 OpenClaw 搭了一套 AI agent（名字叫 Eddie） 系统，把「什么样的广告有效」这个判断权直接交给数据和模型。 📖 整套系统的设计大概是这样的： 先是竞品研究。Eddie 用 Apify 直接抓 Meta 广告库，把某个赛道里所有在投的视频广告全部拉下来，按投放时长排序（专于那些老的广告，因为他们通常越赚钱）。然后用 OpenAI Whisper 逐条转录，分析每个 hook 和卖点。 然后是写脚本，这步细节挺多的。 他们专门做了一套 markdown 文件体系，voice .md、product .md、icp .md，把品牌语气、产品细节、目标用户全部结构化喂给 Eddie。还有一个 writing-rules .md 专门过滤 AI 腔（维基百科那篇关于AI 写作特征的也被塞进去当训练材料）。 拿到竞品脚本之后，Eddie 针对每条广告出两个版本，原版角度拆解加上用自家品牌语气的改写。30 条竞品就是 30 条改写，再乘以不同用户画像（ICP），最终几十上百个变体就出来了。 接下来是分发。最好的脚本一部分发给真人 UGC 创作者，每条 15 到 50 美元；剩下的直接通过 API 推进 Arcads，AI 数字人批量渲染。同一个脚本配 5 个演员，同一个演员换 10 个 hook，几分钟几十条成片就出来了。 最后这个迭代循环是我觉得最有意思的部分。 广告跑完之后，CPA 数据通过 Singular 的 API 回流给 Eddie，它分析哪个方向 CPA 最低，下一轮就往那个方向重点生成。生成、评估、再生成，系统每跑一轮都在变好一点。 现在他们每个月测试 100 多条素材，整个流程基本不需要人盯。人只负责设定规则，剩下的都是 Eddie 的事。

Post summary: 我觉得 AI agent 真正该做的应该是像 Ernesto 他们做的那样 可以帮忙接管一个完整的业务闭环的（在用 TikTok 做增长的朋友一定要看看）。 他们其中一个 app 年收入 30 万美金，最开始靠的是 4 条 TikTok Spark Ads 撑了整个增长周期。后来这 4 条广告跑死了，他们没有去手动做新的，而是用 OpenClaw 搭了一套 AI agent（名字叫 Eddie） 系统，把「什么样的广告有效」这个判断权直接交给数据和模型。 📖 整套系统的设计大概是这样的： 先是竞品研究。Eddie 用 Apify 直接抓 Meta 广告库，把某个赛道里所有在投的视频广告全部拉下来，按投放时长排序（专于那些老的广告，因为他们通常越赚钱）。然后用 OpenAI Whisper 逐条转录，分析每个 hook 和卖点。 然后是写脚本，这步细节挺多的。 他们专门做了一套 markdown 文件体系，voice .md、product .md、icp .md，把品牌语气、产品细节、目标用户全部结构化喂给 Eddie。还有一个 writing-rules .md 专门过滤 AI 腔（维基百科那篇关于AI 写作特征的也被塞进去当训练材料）。 拿到竞品脚本之后，Eddie 针对每条广告出两个版本，原版角度拆解
