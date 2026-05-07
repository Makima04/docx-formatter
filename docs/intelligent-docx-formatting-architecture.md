# 智能 DOCX 排版系统架构设计

## 1. 文档目的

本文档定义网页端智能 DOCX 排版系统的核心架构、成功率边界、兼容策略、规则体系、模块划分、执行流程和 MVP 范围。

本系统的目标不是实现一个网页端 Word，而是实现一个面向模板、规范和真实渲染结果的自动排版引擎。用户上传模板文件和待排版文档，或补充自然语言要求后，系统自动理解模板、识别正文结构、生成符合模板规则的 `.docx`，并通过渲染验证和自动修复尽量达到可直接提交的结果。

核心原则：

```text
LLM 负责理解、归纳、解释和低置信度判断。
Rust/Python 程序负责 OpenXML 操作、规则执行、渲染验证和自动修复。
最终是否成功以 Microsoft Word 中可打开且样式符合模板规则为准。
```

## 2. 成功率定义

本项目中的“99% 成功率”定义为：

```text
输出的 docx 文件可以被 Microsoft Word 正常打开。
文档样式、结构、页码、封面、目录、图表、公式等符合模板中的全部可执行规则。
最多 1% 的结果需要用户手动修改。
需要用户手动修改时，系统必须明确指出修改位置、问题原因和建议改法。
```

成功率不是指“文件生成成功”，而是指“用户拿到的 Word 文档基本可直接提交”。

问题分级：

```text
P0 文件级错误
- docx 无法打开。
- Word 提示文件损坏。
- 内容丢失。
- 图片、表格、公式等关键对象缺失。

P1 结构级错误
- 封面缺失或封面字段错误。
- 目录缺失或目录页码错误。
- 页码格式错误。
- 摘要、目录、正文分节错误。
- 正文起始页或章节起始页不满足奇数页要求。
- 标题层级或编号错误。

P2 版面级错误
- 图和图名分页。
- 表格超宽。
- 表格跨页但没有续表。
- 正文中出现异常大段空白。
- 标题孤立在页尾。
- 图片被裁切或比例异常。

P3 样式级错误
- 字体、字号、行距、段距、缩进不符合模板。
- 三线表线型不符合模板。
- 关键词标点或数量不符合要求。
- 公式编号或说明格式不符合要求。

P4 内容规范和主观质量问题
- 关键词顺序是否符合外延从大到小。
- 变量斜体和单位正体存在疑似问题。
- 引用图表是否应重新绘制。
- 图表是否足够紧凑。
```

验收策略：

```text
P0、P1 必须自动解决或阻断导出。
P2 应尽量自动解决，无法解决时必须指出具体页码和对象。
P3 应自动修复，少数不确定项进入用户确认。
P4 允许以检查报告和建议形式呈现。
```

## 3. 兼容策略

目标兼容顺序：

```text
第一优先级：Microsoft Word。
第二优先级：WPS Office。
```

系统生成的 `.docx` 必须优先保证在 Microsoft Word 中表现正确。WPS 作为次兼容目标，需要尽量避免使用 WPS 渲染差异较大的复杂特性。

兼容策略：

```text
OpenXML 写入以 Word 行为为准。
复杂字段、目录、页码、分节、页眉页脚优先使用 Word 标准结构。
表格宽度、图片尺寸、浮动对象尽量使用稳定写法。
减少依赖不同软件解释差异较大的自动布局行为。
```

验证策略：

```text
主验证：Microsoft Word 渲染结果，或与 Word 高一致性的转换服务。
辅助验证：WPS 打开和导出检查。
基础验证：LibreOffice 转 PDF 可作为自动化 CI 的低成本检查，但不能作为唯一最终标准。
```

高风险兼容项：

```text
复杂浮动图片。
文本框。
多栏混排。
嵌入对象。
复杂域代码。
手动调整过的页眉页脚。
WPS 对 section break、页码字段和表格自动宽度的解释差异。
```

## 4. 总体架构

```text
用户输入
  -> 模板分析
  -> 内容语义解析
  -> 规则抽取
  -> 样式注册与映射
  -> 排版计划生成
  -> DOCX 写入
  -> 渲染验证
  -> 自动修复
  -> 用户确认
  -> 导出
```

核心模块：

```text
Template Analyzer        模板分析器
Semantic Parser          内容语义解析器
Rule Extractor           规则抽取器
Style Registry           样式注册与派生器
Cover Engine             封面引擎
Section/Page Engine      分节与页码引擎
Figure/Table Engine      图表引擎
Formula/Symbol Engine    公式与符号引擎
Layout Planner           排版计划器
DOCX Writer              OpenXML 写入器
Render Validator         渲染验证器
Repair Engine            自动修复器
Confirmation Manager     用户确认管理器
```

端到端流程：

```text
1. 用户上传模板和待排版文档。
2. 系统解析模板，生成 TemplateProfile 和模板质量评级。
3. 系统解析用户内容，生成 SemanticDocument。
4. LLM 和规则程序共同抽取模板自然语言规则。
5. 系统将语义角色映射到模板样式，必要时派生并注册新样式。
6. 系统生成 LayoutPlan。
7. Rust 引擎写入 DOCX。
8. 系统渲染为 PDF 或页面图像进行验证。
9. 根据 ValidationReport 自动修复。
10. 对低置信度或冲突规则请求用户确认。
11. 输出最终 docx、验证报告和需要用户手动修改的位置说明。
```

## 5. 技术栈与职责划分

计划采用 Rust 结合 Python。

```text
Rust：负责高性能、确定性、可测试的文档底层处理。
Python：负责编排、LLM 调用、规则抽取、任务系统和 Web API。
```

Rust 侧职责：

```text
解析 docx ZIP 和 OpenXML。
读取 styles.xml、numbering.xml、document.xml、section properties。
构建低层 DocumentModel。
执行 OpenXML 写入。
注册样式、编号、分节、页码、页眉页脚。
处理表格、图片、公式等结构。
提供可复用的 deterministic engine。
```

Python 侧职责：

```text
FastAPI 服务。
任务队列和任务状态机。
模板分析流程编排。
LLM 调用和 JSON Schema 校验。
自然语言规则抽取。
置信度判断。
用户确认项生成。
PDF 渲染调用和验证报告汇总。
自动修复循环调度。
```

Rust 与 Python 通信方式：

```text
短期：PyO3 / maturin，将 Rust 引擎暴露为 Python 模块。
中期：Rust engine 提供稳定 API，Python 只传递结构化 JSON。
长期：如并发压力增加，可将 Rust engine 独立为服务。
```

边界原则：

```text
Python 不直接拼复杂 OpenXML。
Rust 不直接调用 LLM。
LLM 输出必须先进入 Python 的结构化规则层，再交给 Rust 执行。
```

## 6. 核心数据模型

```text
TemplateProfile
- id
- source_file_hash
- document_type
- quality_score
- page_settings
- style_map
- implicit_style_clusters
- cover_profile
- section_policies
- page_number_profile
- numbering_rules
- rule_set

SemanticDocument
- metadata
- blocks
- assets
- detected_cover
- detected_sections

RuleSet
- rules
- source_map
- confidence
- conflicts

LayoutPlan
- sections
- styles
- blocks
- breaks
- numbering
- table_plans
- figure_plans
- formula_plans
- validation_expectations

ValidationReport
- passed
- issues
- metrics
- rendered_pages

RepairPlan
- actions
- expected_effect
- risk_level
```

## 7. 模板分析与质量分级

模板分析器负责解析用户上传的 `.docx` 模板，生成 `TemplateProfile`。不要只读取文本，也不要只看样式名。`.docx` 是 ZIP 包，核心信息分布在多个 OpenXML 文件中。

需要解析：

```text
word/styles.xml          样式定义
word/numbering.xml       编号定义
word/document.xml        正文内容与段落结构
word/header*.xml         页眉
word/footer*.xml         页脚
word/settings.xml        文档设置
word/_rels/*.rels        图片、链接等关系
section properties       分节、纸张、页边距、页码
fields                   目录、页码、交叉引用等字段
```

模板分析必须同时识别三类信息：

```text
显式样式：模板中已经定义的 Heading 1、正文、标题、图题等样式。
隐式格式：虽然段落样式是 Normal，但通过字号、加粗、居中、位置等表现出特殊语义。
自然语言规则：模板中写明的格式说明、排版要求、论文规范等文字。
```

模板质量分级：

```text
A级模板：结构规范
- 样式体系完整。
- 标题、正文、图题、表题、参考文献等样式明确。
- 分节、页码、页眉页脚真实存在。
- 封面字段清晰。
- 图表、公式、目录等样例完整。

B级模板：局部规范
- 部分样式明确。
- 部分内容依赖直接格式。
- 分节和页码基本可识别。
- 缺少部分图表或公式样例。

C级模板：弱规范
- 大量段落使用 Normal 或正文样式。
- 主要依赖手动字号、加粗、居中、缩进。
- 自然语言规则多，但 OpenXML 结构不完整。
- 需要 LLM 和聚类反推大量隐式样式。

D级模板：高风险
- 文件结构混乱或损坏。
- 页面主要由图片、扫描件、文本框组成。
- 样式和实际显示严重不一致。
- 分节、页码、页眉页脚难以稳定复用。
```

处理策略：

```text
A级：默认自动执行，少量用户确认。
B级：自动执行为主，关键结构需确认。
C级：先生成模板画像和规则清单，让用户确认后执行。
D级：不承诺自动达到 99%，输出风险报告，建议用户更换模板或人工整理模板。
```

模板质量评分可由程序证据和 LLM 综合判断。程序提供样式数量、直接格式比例、section 数量、页码字段、图表样例、目录字段等证据；LLM 负责给出综合评级和原因。

## 8. 内容语义解析

用户输入不能被当作普通富文本处理，必须转成语义文档模型 `SemanticDocument`。

```text
SemanticDocument
- Cover
- AbstractZh
- AbstractEn
- KeywordsZh
- KeywordsEn
- TOC
- Chapter
- Section
- Paragraph
- List
- Figure
- FigureCaption
- Table
- TableCaption
- Formula
- FormulaExplanation
- Reference
- Appendix
```

语义模型的作用是让排版系统知道每一块内容的角色，而不是只知道它的字体和字号。

例如：

```text
“摘要” -> AbstractTitle
“关键词：大模型, 文档排版, OpenXML” -> Keywords
“图 2-1 系统架构” -> FigureCaption
“式中，R表示幅度；θ表示相位。” -> FormulaExplanation
```

只有内容被语义化之后，系统才能自动处理：

```text
标题层级和目录。
封面字段。
摘要和关键词。
图表编号。
公式编号。
参考文献格式。
分节页码。
图表和题注分页约束。
```

## 9. 规则体系

规则来源分为三类：

```text
1. 模板已有样式和 OpenXML 设置。
2. 模板里的隐式格式和排版样例。
3. 模板正文中的自然语言格式说明。
```

自然语言规则由 LLM 抽取成结构化规则，但执行和验证必须由确定性程序完成。

规则结构：

```text
Rule
- id
- source
- target
- constraint
- priority
- auto_fix
- validation_method
- requires_llm
- requires_user_confirmation
- repair_strategy
```

规则分类：

```text
样式规则：字体、字号、段距、缩进、标题、正文、图题、表题。
结构规则：封面、摘要、目录、章节、参考文献、附录。
版面规则：奇数页开始、页码格式、图表不分页、大段空白检测。
内容规范规则：关键词数量、英文标点、变量斜体、单位正体、公式说明。
```

自然语言规则示例：

```text
模板文字：关键词与摘要正文之间空一行。
规则：AbstractBody 和 Keywords 之间保留一个空行。

模板文字：英文关键词不能用中文标点，应使用英文逗号加一个空格分隔。
规则：EnglishKeywords separator == ", "。

模板文字：第一章应从奇数页开始。
规则：ChapterStart start_type == odd_page。

模板文字：图与图名不能分到两页。
规则：FigureGroup keep_together == true。
```

LLM 输出必须经过 JSON Schema 校验。无法映射到系统已知 target 或 action 的规则进入待确认或待开发状态，不能直接执行。

## 10. 样式注册、派生与隐式样式识别

如果模板有明确样式，系统应自动注册模板样式表，并建立语义角色到模板样式的映射。

```text
Title          -> 模板封面标题样式
Heading1       -> 模板一级标题样式
Heading2       -> 模板二级标题样式
Body           -> 正文样式
FigureCaption  -> 图题样式
TableCaption   -> 表题样式
Formula        -> 公式样式
Reference      -> 参考文献样式
```

如果模板样式不完整，系统可以自动派生样式，但派生样式应基于模板已有样式，而不是使用系统固定默认值。

例如：

```text
FigureCaption
- basedOn: Body
- fontSize: 五号
- alignment: center
- spacingBefore: 6pt
- spacingAfter: 6pt

TableCaption
- basedOn: Body
- fontSize: 五号
- alignment: center
- keepNext: true
```

样式注册需要写入或修改：

```text
word/styles.xml
word/numbering.xml
```

很多模板并不规范。常见情况是段落样式显示为正文或 Normal，但实际格式并不是正文。系统不能只看样式名，需要结合：

```text
样式名。
直接格式。
文本模式。
段落位置。
上下文关系。
样例聚类。
```

例如：

```text
居中 + 大字号 + 加粗 + 出现在首页
=> 封面标题。

“摘要”或“Abstract” + 居中 + 位于目录前
=> 摘要标题。

“图 1-1 ...” + 位于图片附近
=> 图题。

“表 2-1 ...” + 位于表格附近
=> 表题。
```

识别结果应进入 `implicit_style_clusters`，并可转化为可复用的派生样式。

## 11. 封面引擎

封面应作为独立页面组件处理，而不是普通第一页。

`CoverProfile` 应包含：

```text
CoverProfile
- page_count
- field_definitions
- layout_blocks
- fixed_text
- images
- page_settings
- header_footer_policy
- page_number_policy
```

常见封面字段：

```text
title
english_title
author
student_id
college
major
advisor
date
school
logo
confidential_level
```

封面引擎需要支持：

```text
识别模板是否包含封面。
判断用户输入是否已有封面。
判断用户封面是否符合模板。
从用户正文、文件名、自然语言描述或表单中提取封面字段。
字段缺失时提示用户补充。
字段冲突时让用户确认。
用模板封面重新生成标准封面。
```

处理策略：

```text
用户无封面
=> 自动添加模板封面。

用户有封面但格式不对
=> 提取字段内容，丢弃原封面版式，套用模板封面重建。

用户封面字段不完整
=> 自动填充可推断字段，其他字段进入待确认列表。

用户封面和正文字段冲突
=> 不能静默修复，必须提示用户确认。
```

插入封面时还必须处理：

```text
section break。
页码是否隐藏。
页眉页脚是否继承。
摘要、目录、正文页码是否重新计算。
目录页码是否更新。
后续章节奇偶页要求是否仍然满足。
```

## 12. 分节与页码引擎

分节和页码是论文、标书、报告排版的核心。

系统需要识别和生成：

```text
封面 section：无页码。
摘要 section：罗马数字或独立页码。
目录 section：罗马数字或继续摘要页码。
正文 section：阿拉伯数字，从 1 开始。
附录 section：可独立编号。
```

支持规则：

```text
首页不同。
奇偶页不同。
目录从奇数页开始。
第一章从奇数页开始。
章节新页开始。
正文页码从 1 开始。
封面不显示页码。
```

内部表示：

```text
SectionPolicy
- name
- start_type: next_page | odd_page | even_page | continuous
- page_number_format: none | roman_lower | roman_upper | decimal
- page_number_start
- header_policy
- footer_policy
- link_to_previous
```

只写 OpenXML 不够。最终必须通过渲染检查：

```text
目录是否真的在奇数页。
第一章是否真的在奇数页。
封面是否无页码。
摘要和目录页码是否为指定格式。
正文是否从 1 开始。
```

## 13. 图表引擎

图和表必须作为语义对象处理。

```text
FigureGroup
- image
- caption
- source_note
- numbering
- keep_together

TableGroup
- caption
- table
- continuation_label
- repeated_header
- numbering
- three_line_style
```

支持规则：

```text
图和图名不能分页。
表格尽量不分页。
表格跨页时添加“续表”。
跨页表格重复表头。
表格采用三线表。
图表分别编号。
图表按章编号：图 1-1、表 2-1。
图表中文字和题名使用五号字或模板指定字号。
```

表格跨页不能完全依赖 Word 自动处理。更稳定的方案是把一个逻辑表格拆成多个物理表格：

```text
第一页：表 1-1 实验参数。
第二页：右上方插入“续表”，重复表头，继续显示表格内容。
```

三线表规则：

```text
顶部粗线。
表头下方细线。
底部粗线。
隐藏大多数内部竖线。
根据模板要求保留必要横线。
```

## 14. 公式与符号引擎

公式应作为 `FormulaBlock` 处理。

```text
FormulaBlock
- formula
- number
- explanation
- chapter_index
- formula_index
```

支持规则：

```text
公式居中。
编号右对齐。
编号按章：(1-1)、(2-1)。
公式字号与正文一致。
公式末不加标点。
“式中，”说明段首空两格。
变量说明以分号结束。
公式附近不能出现大段空白。
```

常见实现方式：

```text
左列：空。
中列：公式，居中。
右列：编号，右对齐。
```

或者使用制表位实现视觉等效布局。

符号规范属于内容检查和半自动修复：

```text
物理量符号、变量符号 -> 斜体。
计量单位 km、KB、Hz、Pa -> 正体。
疑似错误 -> 生成检查报告，必要时用户确认。
```

这类规则不应承诺完全静默修复，因为一个字母可能是变量、缩写、参数名或普通英文。

## 15. 排版计划与 DOCX 写入

排版计划器接收：

```text
SemanticDocument
TemplateProfile
RuleSet
UserIntent
```

输出：

```text
LayoutPlan
- sections
- styles
- blocks
- breaks
- numbering
- table_widths
- image_sizes
- keep_rules
- generated_cover
- generated_toc
- captions
- formula_numbers
```

排版计划需要处理的约束：

```text
标题不能孤立在页尾。
图和图名必须同页。
表格不能超出页面宽度。
正文不能出现异常大段空白。
章节必须从新页或奇数页开始。
目录页码必须正确。
封面不能显示页码。
图表和公式按章编号。
关键词格式必须符合规则。
```

DOCX 写入层负责确定性地操作 OpenXML：

```text
创建和注册样式。
写入 section break。
设置页码格式。
设置页眉页脚。
生成目录字段。
生成编号系统。
插入或重建封面。
插入图表编号。
设置三线表。
设置 keepNext / keepLines。
设置表头重复。
设置图片尺寸。
设置公式编号布局。
```

原则：

```text
LLM 不直接写 OpenXML。
所有 OpenXML 操作必须由确定性代码完成。
每次写入后应能追踪来源规则，便于调试和回滚。
```

## 16. 渲染验证与自动修复

渲染验证是提高成功率的核心。生成 `.docx` 后，必须转成 PDF 或页面截图进行真实验证。

流程：

```text
生成 docx
  -> 使用 Word / WPS / LibreOffice 转 PDF
  -> 提取 PDF 页面结构和文本坐标
  -> 必要时生成页面截图
  -> 检测排版问题
  -> 输出 ValidationReport
```

检测项：

```text
封面是否存在。
封面是否无页码。
目录是否在正确位置。
第一章是否在奇数页。
页码格式是否正确。
图和图名是否同页。
表格是否超宽。
表格跨页是否有续表。
是否存在异常大段空白。
标题是否孤立在页尾。
图片是否被裁切。
表格是否为三线表。
公式编号是否正确。
关键词格式是否正确。
```

自动修复策略示例：

```text
表格超宽
1. 重新计算列宽。
2. 缩小表格字号。
3. 减小单元格边距。
4. 必要时设置横向页面。

图和图名分页
1. 缩小图片。
2. 设置图和图题为同一布局组。
3. 提前分页。
4. 移动图组。

第一章不在奇数页
1. 插入 oddPage section break。
2. 必要时补空白页。

正文出现大段空白
1. 放宽 keepTogether。
2. 缩小图片。
3. 调整表格位置。
4. 允许表格跨页并添加续表。
```

自动修复循环：

```text
LayoutPlan -> DOCX -> Render -> Validate -> Repair -> DOCX -> Render -> Validate
```

循环应设置最大次数，避免无法收敛：

```text
最多自动修复 3-5 轮。
无法自动修复的问题进入用户确认层。
```

## 17. 置信度、用户确认与规则冲突

置信度优先采用 LLM 判断，但必须结合程序证据和结构化校验。

每个关键判断都应输出：

```text
Decision
- value
- confidence
- source
- evidence
- requires_confirmation
```

推荐阈值：

```text
confidence >= 0.85
=> 自动执行。

0.65 <= confidence < 0.85
=> 自动给出建议，用户可确认或覆盖。

confidence < 0.65
=> 不自动执行，进入用户确认。
```

高风险操作即使置信度较高也需要确认：

```text
删除或替换用户封面。
重排大表格。
插入空白页。
拆分表格并添加续表。
修改公式内容。
修改关键词顺序。
```

模板、用户要求和系统规则可能冲突。系统不应自行静默选择，而应向用户提供清晰选项。

常见冲突：

```text
模板样式中正文为 1.5 倍行距，但自然语言说明要求固定 22 磅。
用户要求压缩页数，但模板要求章节从奇数页开始。
模板要求图表不能分页，但表格高度超过一页。
用户已有封面内容和正文标题不一致。
```

冲突处理流程：

```text
1. 检测冲突。
2. 展示冲突来源。
3. 给出推荐选项。
4. 用户选择优先级。
5. 将选择写入任务配置或模板记忆。
```

用户可选策略：

```text
严格遵循模板。
优先遵循用户要求。
优先保证可打印和页码正确。
优先减少页数。
手动选择每条冲突规则。
```

系统默认推荐：

```text
学校论文、标书、合同等强规范文档：严格遵循模板。
普通报告、简历、内部文档：优先遵循用户要求。
```

## 18. LLM 使用边界

模型使用云模型，安全与隐私展示暂不作为本阶段重点。

LLM 适合：

```text
理解用户自然语言排版要求。
识别文档类型。
从模板说明文字中抽取规则。
解释隐式样式的语义。
判断某段内容是标题、摘要、正文、图题、表题还是参考文献。
判断低置信度内容规范问题。
生成用户可读的修改说明。
```

LLM 不适合：

```text
直接拼 OpenXML。
直接决定所有字号、坐标和分页。
直接修复 docx XML。
作为最终排版正确性的唯一判断来源。
```

LLM 输出要求：

```text
必须使用结构化 JSON。
必须通过 JSON Schema 校验。
必须包含 confidence 和 evidence。
未知 target 或未知 action 不允许自动执行。
高风险规则必须进入用户确认。
```

## 19. 任务状态机与性能策略

排版任务可能包含多轮渲染和自动修复，必须异步执行。

任务状态：

```text
uploaded
analyzing_template
parsing_content
extracting_rules
waiting_user_confirmation
planning_layout
writing_docx
rendering
validating
repairing
completed
failed
```

性能策略：

```text
模板分析结果缓存。
同一模板的 TemplateProfile 复用。
渲染验证按需执行，关键阶段必须执行。
自动修复最多 3-5 轮。
大文件限制和超时控制。
批量任务分片处理。
渲染服务设置并发上限。
```

推荐缓存：

```text
模板原文件 hash -> TemplateProfile。
模板原文件 hash -> StyleMap。
模板原文件 hash + 用户确认 -> RuleSet。
docx 输出 hash -> PDF 渲染结果。
```

## 20. 可观测性与调试追踪

自动排版必须能解释“为什么这样排”。每个任务应生成 `FormattingTrace`。

```text
FormattingTrace
- template_findings
- semantic_classification_results
- extracted_rules
- style_mapping_decisions
- user_confirmations
- layout_plan
- applied_openxml_actions
- validation_reports
- repair_attempts
- unresolved_issues
```

对用户展示的版本应简洁：

```text
已自动修复：图表分页、页码格式、目录页码。
需要用户确认：封面导师字段缺失、表 2-1 是否允许拆页。
无法自动处理：变量斜体存在 3 处疑似问题，请检查。
```

对开发者展示的版本应包含：

```text
规则来源。
置信度。
OpenXML 修改位置。
修复前后页码和对象位置变化。
渲染验证指标。
失败原因。
```

## 21. Web 端交互流程

推荐交互流程：

```text
1. 上传模板。
2. 上传待排版文档或粘贴正文。
3. 系统分析模板，展示模板质量等级。
4. 系统识别封面、页码、目录、图表、公式规则。
5. 用户确认冲突项和低置信度项。
6. 系统生成排版计划。
7. 系统生成 docx 并渲染验证。
8. 系统自动修复。
9. 展示最终验证报告。
10. 用户下载 docx。
```

关键页面：

```text
模板分析页：展示模板质量、识别出的规则和风险。
封面确认页：展示识别出的封面字段和缺失字段。
规则确认页：展示冲突规则和低置信度规则。
排版进度页：展示当前任务阶段。
验证报告页：展示已修复问题和仍需用户处理的问题。
PDF 预览页：展示最终排版效果。
下载页：下载 docx 和问题报告。
```

用户不应看到复杂的 OpenXML 术语，而应看到可执行的说明：

```text
检测到正文第一章当前从第 8 页开始，但模板要求奇数页开始。是否插入空白页？
检测到表 2-1 跨页，是否允许添加“续表”并重复表头？
检测到英文关键词使用了中文分号，已改为英文逗号加空格。
```

## 22. 测试体系

该系统不能只依赖单元测试，需要构建真实模板样本库和渲染回归测试。

测试类型：

```text
OpenXML 单元测试。
模板解析快照测试。
样式映射测试。
自然语言规则抽取测试。
DOCX 有效性测试。
Word 打开兼容测试。
WPS 打开兼容测试。
PDF 渲染回归测试。
图表分页测试。
页码和分节测试。
封面字段识别测试。
自动修复循环测试。
```

样本库：

```text
学校论文模板。
公司报告模板。
标书模板。
合同模板。
含复杂封面的模板。
含摘要、目录、正文不同页码的模板。
含奇数页开始要求的模板。
含图表公式的模板。
大量手动格式的弱规范模板。
损坏或高风险模板。
```

核心验收用例：

```text
模板有封面，用户无封面 -> 自动生成封面。
用户封面格式错误 -> 提取字段并套模板重建。
摘要和目录使用罗马页码，正文从 1 开始 -> 页码正确。
第一章要求奇数页开始 -> 渲染后确认为奇数页。
表格跨页 -> 有续表和重复表头。
图和图名 -> 不分到两页。
英文关键词 -> 使用英文逗号加一个空格。
公式 -> 居中并按章编号。
```

## 23. 失败降级策略

系统无法完全自动处理时，必须输出可操作结果，而不是只报错。

失败类型：

```text
模板损坏。
模板质量为 D 级。
公式或表格是图片，无法结构化处理。
表格过大，无法在不破坏可读性的情况下放入页面。
封面字段缺失。
规则冲突需要用户判断。
渲染服务失败。
Word 和 WPS 结果不一致。
```

降级策略：

```text
能自动修复的继续自动修复。
不能自动修复但可定位的问题，输出具体页码、对象和建议改法。
需要用户选择的冲突，进入确认项。
高风险模板先输出模板质量报告。
无法验证 Word/WPS 时，标记验证不完整。
永远不静默丢失内容。
```

用户看到的结果应类似：

```text
排版已完成，但有 2 项需要手动确认：
1. 第 12 页表 2-1 高度超过一页，建议允许拆分并添加续表。
2. 封面缺少“指导教师”，请补充后重新生成。
```

## 24. MVP 路线

第一阶段：稳定核心

```text
上传 docx 模板。
上传 docx 待排版文档。
模板样式解析。
隐式样式识别。
模板质量评级。
封面识别、添加和重建。
标题层级识别。
目录生成。
基础分节页码。
Word 优先兼容。
基础 WPS 兼容检查。
DOCX 导出。
PDF 渲染验证。
问题报告。
```

第二阶段：专业排版

```text
奇数页开始。
三线表。
图表编号。
图表不分页。
续表。
公式编号。
关键词规则。
大段空白检测。
自动修复循环。
```

第三阶段：智能规范检查

```text
自然语言规则抽取。
变量斜体和单位正体。
引用图表检查。
关键词语义顺序。
模板学习。
历史修复记忆。
批量处理。
```

MVP 暂不承诺完全支持：

```text
扫描版模板。
复杂文本框排版。
高度复杂的浮动对象。
嵌入 Excel、Visio、OLE 对象。
所有学科符号规范的完全自动判断。
引用图是否重新绘制的自动判断。
任意复杂公式图片的结构化修复。
```

非目标：

```text
不做完整在线 Word 编辑器。
不做自由拖拽式页面设计工具。
不保证所有 D 级模板自动达到 99%。
不让 LLM 直接生成或修改 OpenXML。
```

## 25. 最终定位

这个软件的核心不是“在线 Word”，也不是“LLM 文档生成器”，而是：

```text
模板分析器
+ 语义文档模型
+ 规则抽取器
+ 样式注册器
+ 分节页码引擎
+ 图表公式引擎
+ DOCX OpenXML 写入器
+ Word 优先的渲染验证器
+ 自动修复器
+ LLM 辅助判断
```

要接近 99% 成功率，不能把“生成 docx 文件”当作终点，而要把“真实渲染后符合模板全部可执行规则”当作终点。
