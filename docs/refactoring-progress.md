# 智能 DOCX 排版系统重构进度

> 基于 [intelligent-docx-formatting-architecture.md](intelligent-docx-formatting-architecture.md) 架构文档的分阶段重构进度追踪。
> 最后更新：2026-05-08

---

## 总览

| 阶段 | 状态 | 描述 | 预估工期 |
|------|:----:|------|:--------:|
| Phase 1 | **已完成** | 修复核心输出质量 | 1-2天 |
| Phase 2 | **已完成** | 多分节支持 + 样式注册 | 2-3天 |
| Phase 3 | **已完成** | 封面引擎 + 目录 + Keep-Together | 2-3天 |
| Phase 4 | **已完成** | 排版计划 + 图表引擎 | 2-3天 |
| Phase 5 | **已完成** | 渲染验证 + 自动修复 | 2-3天 |
| Phase 6 | **已完成** | 规则抽取 + 用户确认 | 2-3天 |
| Phase 7 | **已完成** | 可观测性 + 打磨 | 1-2天 |

---

## Phase 1：修复核心输出质量

**状态：已完成**

输出的 .docx 在 Word 中视觉效果正确。

### 1a. 真实图片嵌入 ✓

**改动文件：** `engine/src/xml_utils.rs`, `engine/src/assembler.rs`

- `xml_utils.rs` 新增 `drawing_inline_xml(r_id, width_emu, height_emu, description)` — 生成完整的 `<w:drawing><wp:inline>` OOXML 结构（含 `<a:blipFill>`, `<wp:extent>`, `<wp:docPr>`, `<a:xfrm>`）
- `xml_utils.rs` 新增 `drawing_paragraph_xml()` — 包装为带对齐的 `<w:p>` 段落
- `assembler.rs` CaptionFigure 分支：文字占位符替换为真实 `<w:drawing>` 嵌入，根据图片实际尺寸计算显示大小（限制在页面内容宽度内，保持宽高比，无尺寸信息时默认 4:3）
- `assembler.rs` 新增 `content_width_cm` 和 `max_img_width_emu` 预计算逻辑

### 1b. 使用 w:pStyle 样式引用 ✓

**改动文件：** `engine/src/xml_utils.rs`, `engine/src/assembler.rs`

- `xml_utils.rs` 新增 `paragraph_xml_with_style(text, style_id, style, template_body)` — 使用 `<w:pStyle>` 引用命名样式，仅对与 body 默认不同的属性写内联覆盖（alignment、spacing、indent、bold/italic）
- `assembler.rs` 新增 `style_for_type()` 和 `style_id_for_type()` — 映射 ParagraphType → 样式对象和 style_id
- 所有段落生成从 `paragraph_xml()` 切换为 `paragraph_xml_with_style()`
- `document_xml()` 新增 `xmlns:a` 和 `xmlns:pic` 命名空间声明

### 1c. 解析 numbering.xml ✓

**改动文件：** `engine/src/models.rs`, `engine/src/parser.rs`

- `models.rs` 新增 `NumberingLevel { level, format, text, alignment }` 和 `NumberingDef { num_id, abstract_num_id, levels }`
- `parser.rs` 新增 `parse_numbering_xml(archive)` — 解析 `<w:abstractNum>` 和 `<w:num>` 元素，提取级别格式/文本/对齐
- `ExtractedDocument` 新增 `numbering: Vec<NumberingDef>`（默认空 vec，向后兼容）

---

## Phase 2：多分节支持 + 样式注册

**状态：已完成**

支持封面、摘要、目录、正文、附录等独立分节，各自有独立的页码和页眉页脚。

### 2a. SectionPolicy 模型 ✓

**改动文件：** `engine/src/models.rs`

- 新增 `SectionPolicy` 结构体（name, start_type, page_number_format, page_number_start, header_text, footer_policy, suppress_page_number）带 `Default` 实现
- 新增 `SectionDef` 结构体（section_index, policy, start_paragraph_index, end_paragraph_index）
- `ExtractedDocument` 新增 `detected_sections: Vec<SectionDef>`
- `TemplateConfig` 新增 `sections: Vec<SectionPolicy>`（默认空 vec）

### 2b. 多分节 Assembler ✓

**改动文件：** `engine/src/xml_utils.rs`, `engine/src/assembler.rs`

- `xml_utils.rs` 新增 `section_properties_from_policy(policy, page, footer_rid)` — 根据 `SectionPolicy` 生成 `<w:sectPr>`，包含 `<w:type>` (nextPage/oddPage/evenPage/continuous)、`<w:pgNumType>` (fmt + start)、footer 引用
- `xml_utils.rs` 新增 `inject_section_break(para_xml, sect_pr_xml)` — 将 `<w:sectPr>` 注入段落的 `<w:pPr>` 中（支持有 pPr 的段落、bare `<w:p/>`、以及 fallback 模式）
- `assembler.rs` 段落收集改为 `Vec<String>`，在分节边界处（非最后分节的 end_paragraph_index）调用 `inject_section_break()` 注入中间 `<w:sectPr>`
- 多分节检测条件：`detected_sections` 和 `template.sections` 均非空时启用

### 2c. 扩展 ParagraphType ✓

**改动文件：** `engine/src/models.rs`, `engine/src/assembler.rs`, `python/app/models.py`, `python/app/core/classifier.py`

- `models.rs` ParagraphType 枚举新增 `Cover`, `Appendix`, `Formula` 三个变体，`from_str`/`as_str` 同步更新
- `assembler.rs` `style_for_type()` — Cover/Appendix 映射到 heading1 样式，Formula 映射到 body 样式
- `assembler.rs` `style_id_for_type()` — Cover/Appendix → "Heading1"，Formula → "Normal"
- `python/app/models.py` — Python `ParagraphType` 枚举同步新增 `COVER`, `APPENDIX`, `FORMULA`
- `python/app/core/classifier.py`:
  - `CONTENT_ROLE_PATS` 新增 `appendix`（`^附录\s*[A-Z\d]`）、`formula`（`^\(\d+[-.]\d+\)`）、`cover`（毕业论文/大学/指导教师/学号等模式）
  - LLM prompt 和 `valid_types` 集合同步更新

### 2d. Python 样式注册器 ✓

**新建文件：** `python/app/core/style_registry.py`

- `StyleRegistry` 类 — 映射语义角色到 OpenXML style_id 和格式属性
- `ROLE_TO_STYLE_ID` 常量 — 17 个角色的固定 style_id 映射（与 engine/assembler.rs 一致）
- `_FALLBACK_CHAIN` — 缺失角色的降级链（如 cover → heading1 → body）
- `from_style_map(style_map)` — 从 `TemplateAnalyzer` 的分析结果构建
- `from_template_config(tpl_dict)` — 从 Rust 的 `TemplateConfig` JSON 构建
- `get_style_id(role)` / `get_style(role)` / `has_role(role)` / `registered_roles()` / `missing_roles()`

---

## Phase 3：封面引擎 + 目录 + Keep-Together

**状态：已完成**

防止标题/图表跨页断裂、插入自动更新目录、生成页眉、智能检测和提取封面字段。

### 3a. Keep-Together（防跨页断裂）✓

**改动文件：** `engine/src/xml_utils.rs`, `engine/src/assembler.rs`

- `style_def_xml()` — 新增 `keep_next: bool` 参数，为 heading/caption 样式输出 `<w:keepNext/>`
- `styles_xml_from_template()` — `style_entries` 类型扩展为 `&[(&str, &str, &ParagraphStyle, bool)]`，Heading1-3 和 CaptionFigure/CaptionTable 传 `true`
- `drawing_paragraph_xml()` — `<w:pPr>` 内添加 `<w:keepNext/>`（图片段落始终与图题保持同页）
- `paragraph_xml_with_style()` — 新增 `keep_lines: bool` 参数，为 true 时添加 `<w:keepLines/>`（图题段落不被拆分）
- `assembler.rs` CaptionFigure 分支传 `keep_lines=true`，其余分支传 `false`

### 3b. 页眉生成 ✓

**改动文件：** `engine/src/xml_utils.rs`, `engine/src/assembler.rs`

- `xml_utils.rs` 新增 `header_xml(text: &str)` — 生成 `<w:hdr>` 文档（居中、18pt、SimSun），结构与 `footer_xml()` 对称
- `xml_utils.rs` 新增 `header_rels_xml()` — 引用 `../styles.xml` 的关系文件
- `content_types_xml()` — 新增 `/word/header1.xml` 的 Override 条目
- `document_rels_xml()` — 新增 `rIdHeader1` → `header1.xml` 关系
- `section_properties_xml()` — 条件性地添加 `<w:headerReference>`（当 `page.header_text.is_some()`）
- `section_properties_from_policy()` — 新增 `header_rid: Option<&str>` 参数
- `assembler.rs` — 条件性地写入 header1.xml 和 header1.xml.rels

### 3c. 目录生成（TOC）✓

**改动文件：** `engine/src/models.rs`, `engine/src/xml_utils.rs`, `engine/src/assembler.rs`

- `models.rs` 新增 `TocSettings { enabled, title, levels }` 结构体（默认: enabled=true, title="目录", levels=3）
- `TemplateConfig` 新增 `toc: Option<TocSettings>` 字段（Option 保持向后兼容）
- `xml_utils.rs` 新增 `toc_title_paragraph_xml(title)` — 居中加粗 SimHei 16pt 标题段落（含 keepNext）
- `xml_utils.rs` 新增 `toc_field_xml()` — TOC 字段代码（`TOC \o "1-3" \h \z \u`）
- `assembler.rs` — 在首个非 Cover 的 Heading1 段落前插入 TOC 标题 + TOC 字段
- 支持动态 levels：当 levels != 3 时动态生成 `\o "1-N"` 字段代码

### 3d. 封面引擎（Python 侧）✓

**新建文件：** `python/app/core/cover_engine.py`

- `CoverResult` 数据类 — `has_cover`, `cover_start`, `cover_end`, `fields`
- `_FIELD_PATTERNS` — 7 种字段模式：author, student_id, college, major, advisor, school, date
- `_detect_cover_block(paragraphs)` — 策略1: 连续 cover 类型段落（允许空段落间隔）; 策略2: 首个非 cover Heading1 之前的所有段落
- `_extract_cover_fields(paragraphs, start, end)` — 提取 title（首个 >=14pt 居中文本）和其他字段
- `process_cover(doc)` — 主入口，被动检测+提取（不注入/重建封面）

### 3e. 模板分析器更新 ✓

**改动文件：** `python/app/core/template_analyzer.py`

- `CONTENT_ROLE_PATTERNS` 新增 `cover` 模式（毕业论文/本科毕业设计/大学名称）
- `_generate_template_config()` 新增 `toc` 字段

### 3f. 流水线集成 ✓

**改动文件：** `python/app/core/pipeline.py`

- 导入 `cover_engine.process_cover`
- 在图片 blob 提取（progress 55）后、组装（progress 70）前插入封面分析步骤

---

## Phase 4：排版计划 + 图表引擎

**状态：已完成**

在组装前引入结构化排版计划，正确处理表格位置、列宽、公式编号，将 StyleRegistry 接入流水线。

### 4a. LayoutPlan 模型 ✓

**改动文件：** `engine/src/models.rs`, `python/app/models.py`

- Rust 新增 5 个结构体：`TablePlacement`, `TablePlan`, `FigurePlan`, `FormulaPlan`, `LayoutPlan`
- `LayoutPlan { table_placements, table_plans, figure_plans, formula_plans }`
- `TablePlacement { table_index, after_para_index, include_caption }` — 控制表格插入位置
- `TablePlan { table_index, col_widths_twips, three_line }` — 每列独立宽度
- `FigurePlan { image_index, caption_para_index, width_emu, height_emu }` — 预计算图片尺寸
- `FormulaPlan { para_index, chapter, number }` — 章节内公式编号
- Python `models.py` 同步添加镜像 Pydantic 模型

### 4b. 排版计划器 ✓

**新建文件：** `python/app/core/layout_planner.py`

- `LayoutPlanner(doc, template, registry)` — 从文档数据 + 模板配置生成排版计划
- **表格位置规划** — 匹配 CaptionTable 段落与表格，生成 `TablePlacement`（无标题表格追加到文档末尾）
- **表格列宽计算** — 从页面尺寸（`page_width - margin_left - margin_right`）× 567 twips/cm 计算，均匀分配并处理余数
- **图片尺寸规划** — 复用 max-width + aspect ratio 逻辑，生成 FigurePlan
- **公式编号规划** — 按 Heading1 分章，章内公式递增编号

### 4c. xml_utils.rs 更新 ✓

**改动文件：** `engine/src/xml_utils.rs`

- `three_line_table_xml()` — 新增 `col_widths_twips: &[i64]` 和 `include_caption: bool` 参数，列宽改为每列独立（不再硬编码 `8500 / col_count`），单元格宽度同步更新
- 新增 `formula_paragraph_xml(formula_text, number_text, tab_stop_twips, body_style)` — 居中公式 + 右制表位 + 编号的 OOXML 段落
- `document_xml()` — 从 4 参数 `(page, paragraphs_xml, tables_xml, section_xml)` 简化为 3 参数 `(page, body_xml, section_xml)`

### 4d. assembler.rs 重构 ✓

**改动文件：** `engine/src/assembler.rs`

- `assemble_docx()` 新增第 4 个参数 `layout_plan: Option<&LayoutPlan>`（`None` 时回退到旧逻辑）
- 构建查找表：`figure_plan_map`, `formula_plan_map`, `table_plan_map`, `tables_after`（BTreeMap 保证顺序）
- **CaptionFigure** 分支：优先使用 FigurePlan 的预计算尺寸
- **Formula** 分支：使用 FormulaPlan 调用 `formula_paragraph_xml()` 生成居中公式+编号；新增 `strip_formula_number()` 去除文本尾部的编号模式
- **三阶段 body 构建**：Phase 1 段落循环 → Phase 2 TOC + section breaks → Phase 3 表格交错插入
- 无 LayoutPlan 时保持旧逻辑（表格追加到末尾，硬编码列宽）

### 4e. py_bindings.rs 更新 ✓

**改动文件：** `engine/src/py_bindings.rs`

- 新增 `assemble_docx_with_plan(doc_json, template_json, output_path, plan_json)` — 解析 plan_json 为 `LayoutPlan`，调用 `assemble_docx(..., Some(&plan))`
- 保留原有 `assemble_docx()` 3 参数接口不变（内部传 `None` plan）

### 4f. 流水线集成 ✓

**改动文件：** `python/app/core/pipeline.py`

- 新增导入 `LayoutPlanner`, `StyleRegistry`
- 在封面分析（progress 60）后、组装（progress 70）前插入排版计划步骤（progress 65）：
  ```python
  registry = StyleRegistry.from_template_config(tpl_dict)
  planner = LayoutPlanner(doc, tpl_dict, registry)
  layout_plan = planner.plan()
  ```
- 组装调用切换为 `docx_fmt_core.assemble_docx_with_plan()`

---

## Phase 5：渲染验证 + 自动修复

**状态：已完成**

渲染 .docx 为 PDF，验证排版质量，自动修复布局问题（最多 3 轮）。

### 5a. 数据模型 ✓

**改动文件：** `python/app/models.py`

- 新增 `SeverityLevel` 枚举：P0_CORRUPT, P1_STRUCTURAL, P2_LAYOUT, P3_STYLE, P4_CONVENTION
- 新增 `ValidationIssue` 模型：issue_id, severity, message, page_number, para_index, target_type, auto_fixable
- 新增 `ValidationReport` 模型：passed, issues, metrics, rendered_pages
- 新增 `RepairAction` 模型：action_type, target_index, parameters, risk_level
- `TaskStatus` 新增 `RENDERING`, `VALIDATING`, `REPAIRING`（在 ASSEMBLING 和 COMPLETED 之间）
- `TaskInfo` 新增 `validation_report: Optional[dict]`, `formatting_trace: Optional[dict]`

### 5b. 配置 ✓

**改动文件：** `python/app/config.py`

- 新增 `libreoffice_path: str = "libreoffice"` — LibreOffice 可执行文件路径
- 新增 `enable_pdf_validation: bool = True` — 是否启用 PDF 验证
- 新增 `max_repair_iterations: int = 3` — 最大修复轮数
- 新增 `pdf_dpi: int = 150` — PDF 渲染 DPI

### 5c. PDF 渲染器 ✓

**新建文件：** `python/app/core/renderer.py`

- `PDFRenderer(libreoffice_path, dpi)` — LibreOffice headless 转 PDF
- `is_available()` — 检查 LibreOffice 是否可用
- `render_to_pdf(docx_path, output_dir)` — subprocess 调用 LibreOffice，返回 PDF 路径或 None
- `extract_layout(pdf_path)` — pdfplumber 提取页面坐标：文本位置 (x0,y0,x1,y1)、表格 bbox、图片 bbox
- 错误处理：LibreOffice 不可用时返回 None，pipeline 跳过验证（graceful degradation）

### 5d. 验证器 ✓

**新建文件：** `python/app/core/validator.py`

- `LayoutValidator.validate(layout_data, doc, template) -> ValidationReport`
- `_group_chars_into_lines()` — 将 pdfplumber 字符级数据合并为文本行
- 8 项检查：

| 检查 ID | 严重度 | 逻辑 |
|---|---|---|
| `cover_page_number` | P1 | 封面范围内页面底部有页码文本 |
| `heading_orphan` | P2 | Heading 出现在页面最后 15%（大字体或粗体启发式） |
| `large_blank_gap` | P2 | 页面内行间距 > 页面高度 40% |
| `table_overflow` | P2 | 表格 bbox 超出内容区域（页面宽度 - 边距） |
| `figure_caption_split` | P2 | 图片和图题段落估算在不同页面 |
| `chapter1_odd_page` | P1 | 第一个 Heading1 应在奇数页 |

### 5e. 修复引擎 ✓

**新建文件：** `python/app/core/repair_engine.py`

- `RepairEngine.generate_repairs(report, layout_plan, doc, template)` — 从 ValidationReport 生成 RepairAction 列表
- `RepairEngine.apply_repairs(actions, layout_plan, template)` — 深拷贝后应用修复，返回修改后的 (layout_plan, template)
- 6 种修复策略：

| 修复动作 | 策略 |
|---|---|
| `shrink_table_width` | 列宽缩放 90%（最小 1500 twips） |
| `shrink_figure` | 图片尺寸缩放 85%（最小 1cm） |
| `enable_keep_next` | 标题样式已内置 keepNext |
| `insert_odd_break` | sections[0].start_type = "oddPage" |
| `suppress_cover_page_number` | sections[0].suppress_page_number = True |
| `shrink_images_near_page` | 所有图片尺寸缩放 90% |

### 5f. 修复循环 ✓

**改动文件：** `python/app/core/pipeline.py`

- 集成 `PDFRenderer`, `LayoutValidator`, `RepairEngine` 到 pipeline
- 修复循环在首次组装（progress 70）后执行：

```
70%  — 首次组装
72%  — PDF 渲染 (RENDERING)
75%  — 验证 (VALIDATING)
78%  — 修复 + 重新组装 (REPAIRING) × 最多 3 轮
100% — 完成
```

- LibreOffice 不可用时跳过验证循环（graceful degradation）
- 每轮修复：生成 actions → apply_repairs → 重新序列化 → assemble_docx_with_plan

### 5g. 依赖与 Dockerfile ✓

**改动文件：** `python/requirements.txt`, `Dockerfile`

- `requirements.txt` 新增 `pdfplumber>=0.11.0`
- `Dockerfile` Stage 2 新增 `libreoffice-writer` + `libreoffice-core` 安装

---

## Phase 6：规则抽取 + 用户确认

**状态：已完成**

从模板自然语言文本中抽取格式规则；低置信度决策交由用户确认。

### 6a. 规则提取器 ✓

**新建文件：** `python/app/core/rule_extractor.py`

- `RuleExtractor(llm_client)` — LLM + 正则双重提取
- `extract_rules(template_description) -> list[FormatRule]`
- LLM 提取：发送结构化 prompt 到 OpenAI 兼容 API，解析 JSON 数组响应（支持 markdown code block 包裹）
- 正则 fallback：30+ 中英文模式匹配（字体大小、字体名、粗体、行距、对齐、缩进、段距、三线表、封面无页码等）
- 未知 target 自动标记为 `status="pending"`，不自动执行
- 合并逻辑：LLM + regex 结果按 (target, constraint) 去重

### 6b. 确认管理器 ✓

**新建文件：** `python/app/core/confirmation.py`

- `ConfirmationManager` — 生成和管理用户确认项
- `generate_confirmations(doc, report, rules, actions) -> list[ConfirmationItem]`
- 4 类确认来源：

| 来源 | 触发条件 |
|---|---|
| 分类置信度 | 0.65-0.85 → 自动建议；<0.65 → 必须确认 |
| 验证问题 | P0/P1 严重度 → 必须确认 |
| 待处理规则 | status="pending" 或 requires_user_confirmation |
| 高风险修复 | risk_level="high" 或操作类型为高风险 |

- 高风险操作：replace_cover, split_large_table, insert_blank_page, modify_formula_content, modify_keyword_order
- `apply_confirmation(items, item_id, choice)` — 应用用户选择
- `pending_items(items)` — 返回未解决的确认项

### 6c. API 端点 ✓

**改动文件：** `python/app/api/main.py`

- `GET /api/tasks/{task_id}/confirmations` — 获取待确认项列表
- `POST /api/tasks/{task_id}/confirmations/{item_id}` — 提交用户选择

### 6d. 数据模型 ✓

**改动文件：** `python/app/models.py`

- 新增 `FormatRule` 模型：id, source, target, constraint, priority, auto_fix, validation_method, requires_user_confirmation, repair_strategy, status
- 新增 `ConfirmationItem` 模型：id, category, description, options, risk_level, auto_resolved, user_choice

---

## Phase 7：可观测性 + 打磨

**状态：已完成**

添加调试追踪能力，记录每个排版决策，生成用户/开发者报告。

### 7a. 格式化追踪 ✓

**新建文件：** `python/app/core/trace.py`

- `FormattingTrace(task_id)` — 记录流水线各阶段的决策
- `record(stage, data)` — 记录条目（含 UTC 时间戳）
- `to_dict()` / `to_json()` — 序列化输出
- `to_user_report()` — 用户视图：已自动修复项、需确认项、无法处理项
- `to_developer_report()` — 开发者视图：详细阶段数据
- 记录的阶段：parse, template_analysis, classification, cover_detection, layout_plan, assembly, validation, repair

### 7b. 流水线集成 ✓

**改动文件：** `python/app/core/pipeline.py`

- 每个 pipeline 阶段注入 `trace.record()` 调用
- 修复循环中记录每轮 validation 和 repair 数据
- 完成/失败时将 `trace.to_dict()` 存入 `TaskInfo.formatting_trace`

### 7c. 数据模型 ✓

**改动文件：** `python/app/models.py`

- 新增 `TraceEntry` 模型：stage, timestamp, data
- 新增 `FormattingTrace` 模型：task_id, entries
- `TaskInfo` 新增 `validation_report: Optional[dict]`, `formatting_trace: Optional[dict]`

---

## Rust-Python 契约变更

| 阶段 | 变更 | 向后兼容 |
|------|------|:--------:|
| 1 | `ExtractedDocument.numbering: Vec<NumberingDef>` | ✓ |
| 2 | `TemplateConfig.sections: Vec<SectionPolicy>` | ✓ |
| 2 | `ExtractedDocument.detected_sections: Vec<SectionDef>` | ✓ |
| 2 | ParagraphType 新增 Cover, Appendix, Formula | ✓ |
| 3 | `TemplateConfig.toc: Option<TocSettings>` | ✓ |
| 3 | `paragraph_xml_with_style()` 新增 `keep_lines` 参数 | ✓ |
| 3 | `section_properties_from_policy()` 新增 `header_rid` 参数 | ✓ |
| 4 | `assemble_docx()` 新增 `layout_plan: Option<&LayoutPlan>` 参数 | ✓ |
| 4 | 新增 `assemble_docx_with_plan()` Python 绑定 | ✓ |
| 4 | `three_line_table_xml()` 新增 `col_widths_twips` + `include_caption` 参数 | ✓ |
| 4 | `document_xml()` 从 4 参数改为 3 参数（body_xml） | ✓ |
| 4 | 新增 `formula_paragraph_xml()` | ✓ |
| 5 | `TaskStatus` 新增 RENDERING, VALIDATING, REPAIRING | ✓ |
| 6 | 新增 `/api/tasks/{id}/confirmations` 端点 | ✓ |
| 7 | `TaskInfo` 新增 `validation_report`, `formatting_trace` | ✓ |

所有变更是增量的，现有 API 和前端在每个阶段都能正常工作。

## 新建文件汇总

| 阶段 | 文件 | 状态 |
|------|------|:----:|
| 2 | `python/app/core/style_registry.py` | 已创建 |
| 3 | `python/app/core/cover_engine.py` | 已创建 |
| 4 | `python/app/core/layout_planner.py` | 已创建 |
| 5 | `python/app/core/renderer.py`, `validator.py`, `repair_engine.py` | 已创建 |
| 6 | `python/app/core/rule_extractor.py`, `confirmation.py` | 已创建 |
| 7 | `python/app/core/trace.py` | 已创建 |
