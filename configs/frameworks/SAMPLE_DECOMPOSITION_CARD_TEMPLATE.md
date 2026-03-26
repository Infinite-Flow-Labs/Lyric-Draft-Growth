# 单篇标准样本拆解卡模板

说明：本模板用于拆解 `seed_articles_30d.reclassified.json` 中已确认要研究的标准样本。
目标不是评价内容“好不好”，而是提取“这篇为什么能代表某个框架，以及哪些部分可以被稳定复用”。
其中 `section_flow` 只用于提炼隐式骨架，后续生成时不能机械照抄成外显小标题模板。

---

# [sample_id] [sample_title]

- `framework_id`:
- `framework_label_zh`:
- `sample_url`:
- `author`:
- `created_at`:
- `source_file`:
- `decomposer`:
- `status`: `draft | reviewed | locked`

## 1. 标准样本判定

- `why_standard`:
  为什么这篇能代表该框架，而不是仅仅“数据好”或“作者强”。
- `main_strength`:
  这篇最强的地方是什么。只能选 1-2 个核心点，如 `hook` / `structure` / `evidence` / `language` / `rhythm`。
- `best_reader_need`:
  它最精准满足了读者什么需求。

## 2. 核心承诺

- `target_reader`:
- `core_problem`:
- `core_promise`:
- `expected_gain`:
  读者读完后预期会得到什么，必须写成具体结果，而不是抽象评价。

## 3. Hook 拆解

- `hook_type`:
  只能从以下类型里选：`数字型` / `反常识型` / `发布应用型` / `观点转述型` / `预警型` / `对比型` / `教程承诺型` / `其他`
- `hook_sentence`:
  记录标题或正文开头中真正承担钩子作用的那一句。
- `hook_trigger`:
  这句钩子靠什么吸引读者继续看，如 `收益` / `速度` / `稀缺信息` / `省钱` / `避坑` / `身份背书`。
- `value_promise`:
  钩子向读者承诺了什么价值。

## 4. 结构推进

按“功能段”拆，不按自然段机械切分。每个功能段都写清楚它在推动什么。
这里提炼的是后台结构，不是要求未来生成时把这些段名原样写出来。

| step | section_name | section_function | section_summary | evidence_type | reusable |
|---|---|---|---|---|---|
| 1 | Hook | 抓注意力 |  |  | Y/N |
| 2 |  |  |  |  | Y/N |
| 3 |  |  |  |  | Y/N |
| 4 |  |  |  |  | Y/N |
| 5 |  |  |  |  | Y/N |

补充：
- `section_flow_summary`:
  用一句话概括全文推进逻辑，例如 `问题 -> 方案 -> 配置步骤 -> 效果 -> 风险提示 -> 收束判断`
- `turning_point`:
  文中真正让读者“继续看下去”的转折点在哪里。

## 5. 证据系统

- `evidence_types`:
  允许多选，如 `数据` / `亲身经历` / `操作步骤` / `截图/配置` / `外部观点` / `案例` / `对比实验` / `风险案例`
- `evidence_order`:
  这些证据按什么顺序出现。
- `trust_source`:
  这篇内容的可信度主要来自哪里。
- `weakest_evidence`:
  哪一块证据最弱，后续改写时最容易空心化。

## 6. 语言与节奏

- `tone`:
  如 `直接` / `保姆级` / `判断式` / `煽动式` / `口语化` / `冷静分析`
- `sentence_rhythm`:
  句长节奏如何，如 `短句连续推进` / `短长交替` / `列表体为主`
- `language_markers`:
  记录可复用的语言动作，而不是具体措辞堆砌。
- `rhetorical_moves`:
  如 `先打痛点` / `先下结论` / `先讲失败再讲修正` / `不断反问` / `给动作指令`
- `repetition_pattern`:
  是否有重复动作帮助建立节奏，如反复出现 `先…再…`、`问题是…`
- `voice_distance`:
  这篇更像是在“教朋友”“给同事交接”“做系统拆解”“替读者做选择”中的哪一种。
- `surface_form`:
  这篇表面主要靠什么形式承载结构，如 `场景对话` / `目录` / `步骤` / `FAQ` / `案例` / `清单`

## 7. 可复用 / 不可复用

- `reusable_parts`:
  只写可迁移到其他 source 的部分，如结构、推进顺序、证据组合、语言动作。
- `non_reusable_parts`:
  只写作者特有、身份特有、资源特有、经历特有的部分。
- `rewrite_risks`:
  后续套框架改写时最容易失真的点。

## 8. 框架归纳输入

- `framework_signals`:
  这篇之所以属于该框架，最强的 3 个识别信号是什么。
- `suitable_source_types`:
  哪类 source 最适合套这个框架。
- `unsuitable_source_types`:
  哪类 source 不适合套这个框架。
- `one_sentence_abstraction`:
  用一句话抽象这篇样本的写法，不要写成内容摘要。

## 9. 最终提炼

- `stable_hook_pattern`:
- `stable_section_flow`:
- `stable_evidence_mix`:
- `stable_language_pattern`:
- `anti_ai_notes`:
  如果之后拿这篇做风格学习，哪些表面结构不要原样抄，否则会出现模板味。
- `use_for_framework_summary`: `Y/N`

---

## 填写原则

- 先写“功能”，再写“内容”。不要把内容摘要误当结构拆解。
- 先区分“可复用”和“作者个人特色”，避免把人设误当框架。
- 所有判断尽量能回指到具体句子、段落或证据，不写空泛结论。
- 如果某篇样本强依赖作者身份或独家资源，必须在 `non_reusable_parts` 里明确标出。
- 风格学习要抓“语气、节奏、组织动作”，不要抓具体原句。
