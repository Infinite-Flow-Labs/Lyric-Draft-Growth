# Source Item x-kasong2048-99c3f1a02c37

- Platform: x
- Source Kind: x_thread
- Canonical URL: https://x.com/kasong2048/status/2036285004440060355
- Author: kasong2048
- Published At: 2026-03-24T03:32:32Z

## Signals
- Release Signals: 
- Task Hints: 
- Fact Anchors: 17

## Content Preview

Post title: 什么时候 Vibe Coding（与 AI 结对编码），什么时候 Harness Engineering（设计编码环境，AI 自主完成全部编码）？ 当你设计了完整编码环境： 「开发（SDD + TDD）、验证、提PR、Review 代码、基于 Review 修改、继续提 PR、PR 通过合并」 这套 编码Loop 完全由 Agent 自主完成。那么这类编码工作就是 Harness Engineering。 接下来，假设你想修改下环境，比如： 你使用 superpowers 串联 SDD 完整流程，superpowers 默认为每个任务创建一个 git worktree，虽然能保证代码隔离，但跑测试时你希望有全新的 DB 副本，所以希望将流程改成： 「每个任务创建一个 Dev Container（Docker 环境），有全新的数据副本与代码，跑完任务提交 PR 通过后再销毁环境」 那就需要修改 superpowers 内的 using-git-worktree SKILL。 如果是修改代码，你有完整的 Loop 可以让 Agent 执行。但修改 Skill 内的自然语言，你还没设计一套完整的 Loop。所以你选择： 1. 告诉 Agent 你希望如何修改 using-git-worktree SKILL 2. Agent 修改完后你再人工 Review 3. Review 没问题后跑几下试试效果 这个过程就是 Vibe Coding。 核心区别就是：不管是针对 编程语言还是自然语言，关键是「你有没有一个完整的环境，可以对 Agent 的行为进行约束、观测、校验、回退」 有，就是 Harness Engineering 没有，需要人工介入，就是 Vibe Coding

Post summary: 什么时候 Vibe Coding（与 AI 结对编码），什么时候 Harness Engineering（设计编码环境，AI 自主完成全部编码）？ 当你设计了完整编码环境： 「开发（SDD + TDD）、验证、提PR、Review 代码、基于 Review 修改、继续提 PR、PR 通过合并」 这套 编码Loop 完全由 Agent 自主完成。那么这类编码工作就是 Harness Engineering。 接下来，假设你想修改下环境，比如： 你使用 superpowers 串联 SDD 完整流程，superpowers 默认为每个任务创建一个 git worktree，虽然能保证代码隔离，但跑测试时你希望有全新的 DB 副本，所以希望将流程改成： 「每个任务创建一个 Dev Container（Docker 环境），有全新的数据副本与代码，跑完任务提交 PR 通过后再销毁环境」 那就需要修改 superpowers 内的 using-git-worktree SKILL。 如果是修改代码，你有完整的 Loop 可以让 Agent 执行。但修改 Skill 内的自然语言，你还没设计一套完整的 Loop。所以你选择： 1. 告诉 Agent 你希望如何修改 using-git-worktree SKILL 2. Agent 修改完后你再人工 Review 3. Review 没问题后跑几下试试效果 这个过程就是 Vibe Coding。 核心区别就是：不管是针对 编程语言还是自然语言，关键是「你有没有一个完整的环境，可以对 Agent 的行为进行约束、观测、校验、回退」 有，就是 Harness Engineering 没有，需要人工介
