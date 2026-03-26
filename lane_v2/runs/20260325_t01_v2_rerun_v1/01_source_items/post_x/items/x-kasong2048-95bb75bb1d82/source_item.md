# Source Item x-kasong2048-95bb75bb1d82

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/kasong2048/status/2036356708474429817
- Author: kasong2048
- Published At: 2026-03-24T08:17:27Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 7

## Content Preview

Post title: Harness Engineering 经常遇到一个问题 —— Agent 跑着跑着，没完成任务就停了。 这里有很多原因，其中一个重要原因是：Agent 有事停下来需要你确认。 这里有个设计 Harness Engineering 的小技巧：把「执行性质的工作」放到 subagent，用 Skill 来编排他们。 举个例子：你要实现一个功能，已经把功能拆解为 N 个 Todo，如果直接唤起 subagent 来编码，那长程任务很可能中途停下来。 这时候可以实现一个「编排 subagent 的 Skill」，由他来唤起所需数量的 subagent，除了给他们填充必要的信息（比如完成任务所需上下文、任务本身），还要让 subagent “遇到问题及时沟通” 。 很多常见的“导致 Agent 停下来的事儿”都能被 Skill 这层兜住，不会更多污染 main agent 导致任务停下来。

Post summary: Harness Engineering 经常遇到一个问题 —— Agent 跑着跑着，没完成任务就停了。 这里有很多原因，其中一个重要原因是：Agent 有事停下来需要你确认。 这里有个设计 Harness Engineering 的小技巧：把「执行性质的工作」放到 subagent，用 Skill 来编排他们。 举个例子：你要实现一个功能，已经把功能拆解为 N 个 Todo，如果直接唤起 subagent 来编码，那长程任务很可能中途停下来。 这时候可以实现一个「编排 subagent 的 Skill」，由他来唤起所需数量的 subagent，除了给他们填充必要的信息（比如完成任务所需上下文、任务本身），还要让 subagent “遇到问题及时沟通” 。 很多常见的“导致 Agent 停下来的事儿”都能被 Skill 这层兜住，不会更多污染 main agent 导致任务停下来。

Canonical URL: https://x.com/kasong2048/status/2036356708474429817
