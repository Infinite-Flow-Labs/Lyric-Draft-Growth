# Source Item x-gorden_sun-4d1bb97e37f3

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/Gorden_Sun/status/2034269013275210149
- Author: Gorden_Sun
- Published At: 2026-03-18T14:01:42Z

## Signals
- Release Signals: release, rollout
- Task Hints: release, opinion_decode
- Fact Anchors: 21

## Content Preview

Post title: Mamba-3：新一代Memba架构 Mamba-2从训练场景出发，为训练速度做了大量简化；Mamba-3从推理场景出发，在不增加推理延迟的前提下显著提升模型质量。Mamba与Transformer混合使用效果优于纯模型，未来还是以混合使用为主。 博客：https://goombalab.github.io/blog/2026/mamba3-part1/

Post summary: Mamba-3：新一代Memba架构 Mamba-2从训练场景出发，为训练速度做了大量简化；Mamba-3从推理场景出发，在不增加推理延迟的前提下显著提升模型质量。Mamba与Transformer混合使用效果优于纯模型，未来还是以混合使用为主。 博客： goombalab.github.io/blog/202…

Canonical URL: https://x.com/Gorden_Sun/status/2034269013275210149

Linked source 1: https://goombalab.github.io/blog/2026/mamba3-part1/

[[Paper](https://arxiv.org/abs/2603.15569)] [[Code](https://github.com/state-spaces/mamba)] **This series is cross-posted at [tridao.me](https://tridao.me/blog/2026/mamba3-part1/)** 1. Part I 2. [Part II](https://goombalab.github.io/blog/2026/mamba3-part2/) Since the release of Mamba-2 in mid-2024, most architectures have switched from Mamba-1. Why? Mamba-2 made the bet that training efficiency was the largest bottleneck for state space models (SSMs), and thus simplified the underlying SSM mechanism to deliver 2-8\times faster training compared to its predecessor, leading to wider adoption. Since then, the LLM landscape has started to shift. While pretraining is still super important, more attention has been focused on post-training and deployment, both of which are _extremely inference-heavy_. The scaling of post-training methods, especially with reinforcement learning with verifiable rewards (RLVR) for coding or math, requires huge amounts of generated rollouts, and most recently,
