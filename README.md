# Growth Engine

Infinite Flow Labs 的增长系统。独立于任何单一产品，可复用于 YoloX 及未来产品线。

## 项目结构

```
growth-engine/
├── strategy/        # 增长策略文档
├── accounts/        # 矩阵账号定义与运营规范
├── content/         # 内容框架、模板、素材库
├── playbook/        # 可复用的增长 Playbook
└── campaigns/       # 具体产品的增长战役（按产品分子目录）
```

## 核心架构：内容矩阵

四层账号矩阵漏斗：

1. **KOC 养号** — 泛 AI 流量蓄水池，与品牌解耦
2. **创始人/Builder 号** — Build in Public 人设，信任背书
3. **业务场景号** — 按垂直方向精准触达
4. **品牌官方号** — 转化承接层

流量路径：KOC + 创始人号 → 业务场景号 → 品牌官方号（转化）

详见 [`strategy/content_matrix_strategy.md`](strategy/content_matrix_strategy.md)

## 文档规范

- 文档语言：中文为主，技术术语用英文
- 命名：snake_case，日期前缀用 YYYY-MM 格式
- 每个文档包含元数据头：标题、日期、状态（Draft / Active / Archived）、关联产品
