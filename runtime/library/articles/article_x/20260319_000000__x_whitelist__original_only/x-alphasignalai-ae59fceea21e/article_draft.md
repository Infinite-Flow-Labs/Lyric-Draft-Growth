# 同样一笔 credit，短问答和整次重构一个价：Windsurf 终于把这个扭曲的计价拆掉了

*它把按请求扣费换成日/周配额，真正被改掉的不是价格表，而是“这次提问值不值”的心理账本。*

最刺眼的不是 Windsurf 改了价格，而是它终于承认了一件事：按请求扣 credit，会把人逼成提问囤积者。一个一行提示和一次完整重构，过去居然能按同样的 rate 计费，这种规则本身就会把使用方式扭曲掉。

于是你看到的不是“更便宜”四个字，而是计费逻辑的反转。Windsurf 现在把 per-request credits 换成了 daily 和 weekly quotas，覆盖所有计划。Free 版给的是 unlimited tab completions，加上 light quota；Pro 是 $20/月，拿到 all frontier models 和更高 quota；Max 是 $200/月，按它自己的说法是 power-user-grade limits；Teams 则是 $40/seat，带 admin dashboard 和 priority support。

这件事听起来轻，实际上戳中了一个很具体的瓶颈。以前你不是在问问题，你是在先算账：这个小问题值不值得烧一个 credit？如果答案不确定，就干脆攒着，等下次一起丢进一个巨大的 prompt 里。

问题是，模型并不会因为你把十个问题揉成一个长句，就自动把输出质量抬上去。恰恰相反，source 里点出了那个后果：为了省 credit，用户会把东西批量塞进一个超大 prompt，质量反而下滑。所谓“节省”，最后常常变成了把清晰度换掉。

Windsurf 这次改的，就是这个心理摩擦。配额制并不神奇，但它把最碍事的那层犹豫拿掉了。你可以更随手地问小问题，不需要每一次都先做一次价值评估。

从产品系统看，这其实是在重新定义“如何使用”而不是只改“怎么收费”。credit 时代更像是一次次独立交易；quota 时代更像是一段时间内的使用预算。两者看似都有限制，但对用户行为的引导完全不同。

更重要的是，Windsurf 没有把增长压力全都压到“无限使用”这种模糊承诺上。source 里明确写了：如果你真的撞到上限，额外使用还是可以按 API pricing 购买。也就是说，它不是把约束抹掉，而是把约束放到更容易理解的层级上。

这也是为什么这个改动值得单独拿出来看。它并不靠一句“更先进”站住脚，而是靠一个很朴素的事实：如果一个计价方式会逼用户把本来该拆开的事情硬塞成一团，那这个计价方式本身就是产品的一部分问题。

Free、Pro、Max、Teams 这几档价格并不是重点，重点是它们背后的行为设计开始变了。Free 版的 unlimited tab completions、Pro 的 higher quota、Max 的 power-user-grade limits、Teams 的 admin dashboard 和 priority support，都是在把不同层级的使用场景重新分流，而不是让所有人都在同一把 credit 尺子下挣扎。

如果只看表面，这只是一次 pricing update。但如果把用户心里那句“这值不值一个 credit”算进去，它更像是在修一个经常被忽略的瓶颈：当工具开始逼你先算成本，你就会开始减少探索；当探索变少，输出质量也会跟着变差。

Windsurf 这次真正押注的，不是某个看起来更漂亮的价格表，而是让小问题重新变得可以随口一问。这个判断能不能成立，最后要看用户是不是会真的停止囤积 prompt；如果会，那被改掉的就不只是计费方式，而是整个使用习惯。

---

- Framework: 01_money_proof / metric_postmortem
- Output Language: zh-CN
- Human Review Required: True

## Preserved Fact Anchors
- Windsurf replaced per-request credits with daily and weekly quotas across all plans
- Free: unlimited tab completions, light quota
- Pro ($20/mo): all frontier models, higher quota
- Max ($200/mo): power-user-grade limits
- Teams ($40/seat): admin dashboard, priority support
- Credits charged the same rate for a one-liner and a full refactor
- Extra usage is still buyable at API pricing if you hit the ceiling

## Open Questions
- source 没有说明 Windsurf 此次调整的直接触发原因，因此我没有补写任何外部动机
- source 没有提供新旧方案的具体配额数值，所以文中只保留了已明确公开的档位与规则
