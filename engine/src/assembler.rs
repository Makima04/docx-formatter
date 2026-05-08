/// Docx assembler — builds the final .docx zip package.
///
/// Takes a classified ExtractedDocument + TemplateConfig + optional LayoutPlan,
/// generates all XML in Rust, and writes the zip directly.
use std::collections::BTreeMap;
use std::collections::HashMap;
use std::io::Write;
use zip::write::FileOptions;
use zip::CompressionMethod;

use crate::models::*;
use crate::xml_utils;

pub fn assemble_docx(
    extracted: &ExtractedDocument,
    template: &TemplateConfig,
    output_path: &str,
    layout_plan: Option<&LayoutPlan>,
) -> Result<(), String> {
    let file = std::fs::File::create(output_path)
        .map_err(|e| format!("Cannot create output file: {e}"))?;
    let mut zip = zip::ZipWriter::new(file);
    let options = FileOptions::default().compression_method(CompressionMethod::Stored);

    zip.start_file("[Content_Types].xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::content_types_xml(&extracted.images).as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("_rels/.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::root_rels_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/_rels/document.xml.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::document_rels_xml(&extracted.images).as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/styles.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::styles_xml_from_template(template).as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/settings.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::settings_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/numbering.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::numbering_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/footer1.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::footer_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/_rels/footer1.xml.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::footer_rels_xml().as_bytes()).map_err(|e| e.to_string())?;

    // Always write header1.xml — rels and content_types always reference it.
    // Use empty string as fallback to avoid broken references.
    let header_text = template.page.header_text.as_deref().unwrap_or("");
    zip.start_file("word/header1.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::header_xml(header_text).as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/_rels/header1.xml.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::header_rels_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("docProps/core.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::core_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("docProps/app.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::app_xml().as_bytes()).map_err(|e| e.to_string())?;

    // ── Build layout lookup maps ──
    let figure_plan_map: HashMap<usize, &FigurePlan> = layout_plan
        .map(|lp| lp.figure_plans.iter().map(|fp| (fp.image_index, fp)).collect())
        .unwrap_or_default();
    let formula_plan_map: HashMap<usize, &FormulaPlan> = layout_plan
        .map(|lp| lp.formula_plans.iter().map(|fp| (fp.para_index, fp)).collect())
        .unwrap_or_default();
    let table_plan_map: HashMap<usize, &TablePlan> = layout_plan
        .map(|lp| lp.table_plans.iter().map(|tp| (tp.table_index, tp)).collect())
        .unwrap_or_default();
    let mut tables_after: BTreeMap<usize, Vec<&TablePlacement>> = BTreeMap::new();
    if let Some(lp) = layout_plan {
        for tp in &lp.table_placements {
            tables_after.entry(tp.after_para_index).or_default().push(tp);
        }
    }

    // ── Phase 1: Build paragraph parts ──
    let mut para_parts: Vec<String> = Vec::with_capacity(extracted.paragraphs.len());
    let mut image_idx = 0usize;

    // Pre-compute max image width from page and template figure style (fallback)
    let content_width_cm = template.page.page_width_cm
        - template.page.margin_left_cm
        - template.page.margin_right_cm;
    let max_img_width_cm = template.figure.max_width_cm.min(content_width_cm);
    let max_img_width_emu = (max_img_width_cm * 360000.0).round() as i64;
    // Tab stop for formula numbering (right tab at content width)
    let tab_stop_twips = (content_width_cm * 1440.0 / 2.54).round() as i64;

    for (para_idx, para) in extracted.paragraphs.iter().enumerate() {
        let text = para.text.trim();
        if text.is_empty() {
            para_parts.push("<w:p/>".to_string());
            continue;
        }

        let style = style_for_type(&para.paragraph_type, template);
        let style_id = style_id_for_type(&para.paragraph_type);

        match para.paragraph_type {
            ParagraphType::CaptionFigure => {
                // Use FigurePlan if available, else fallback to inline calculation
                let (disp_w, disp_h) = if let Some(fp) = figure_plan_map.get(&image_idx) {
                    (fp.width_emu, fp.height_emu)
                } else {
                    // Fallback: same as Phase 1 logic
                    match extracted.images.get(image_idx) {
                        Some(img) => match (img.width_px, img.height_px) {
                            (Some(w), Some(h)) if w > 0 && h > 0 => {
                                let aspect = h as f64 / w as f64;
                                (max_img_width_emu, (max_img_width_emu as f64 * aspect).round() as i64)
                            }
                            _ => (max_img_width_emu, (max_img_width_emu as f64 * 0.75).round() as i64),
                        },
                        None => (max_img_width_emu, (max_img_width_emu as f64 * 0.75).round() as i64),
                    }
                };

                if image_idx < extracted.images.len() {
                    let img = &extracted.images[image_idx];
                    let rid = format!("rId{}", 100 + img.index);
                    let desc = img.caption.as_deref().unwrap_or(&img.media_path);
                    para_parts.push(xml_utils::drawing_paragraph_xml(
                        &rid, disp_w, disp_h, desc, &template.figure.align,
                    ));
                    image_idx += 1;
                }
                para_parts.push(xml_utils::paragraph_xml_with_style(text, style_id, style, &template.body, true));
            }
            ParagraphType::CaptionTable => {
                if layout_plan.is_some() {
                    // With LayoutPlan, tables are interleaved at correct positions.
                    // Skip the caption paragraph text here — the table XML will be
                    // inserted after this paragraph by the interleaving phase below.
                    // Actually, we KEEP the caption paragraph in the stream.
                    // The TablePlacement.include_caption=false means the table XML
                    // won't duplicate it. We just render it as a normal paragraph.
                    para_parts.push(xml_utils::paragraph_xml_with_style(text, style_id, style, &template.body, false));
                } else {
                    // No LayoutPlan: caption stays in paragraph stream,
                    // table XML appended at end (which includes its own caption).
                    // We still render the caption paragraph — but tables at end
                    // will also render theirs. This is the legacy behavior.
                    para_parts.push(xml_utils::paragraph_xml_with_style(text, style_id, style, &template.body, false));
                }
            }
            ParagraphType::Formula => {
                if let Some(fp) = formula_plan_map.get(&para_idx) {
                    let number_text = format!("({}-{})", fp.chapter, fp.number);
                    // Strip trailing formula number pattern from text if present
                    let formula_text = strip_formula_number(text);
                    para_parts.push(xml_utils::formula_paragraph_xml(
                        formula_text, &number_text, tab_stop_twips, &template.body,
                    ));
                } else {
                    // No plan: render as normal paragraph
                    para_parts.push(xml_utils::paragraph_xml_with_style(text, style_id, style, &template.body, false));
                }
            }
            _ => {
                para_parts.push(xml_utils::paragraph_xml_with_style(text, style_id, style, &template.body, false));
            }
        }
    }

    // ── TOC insertion ──
    if let Some(ref toc_settings) = template.toc {
        if toc_settings.enabled {
            let toc_insert_idx = extracted.paragraphs.iter().position(|p| {
                p.paragraph_type == ParagraphType::Heading1
            });
            if let Some(idx) = toc_insert_idx {
                let levels = toc_settings.levels.min(9).max(1);
                let toc_title = xml_utils::toc_title_paragraph_xml(&toc_settings.title);
                let toc_field = if levels != 3 {
                    let parts = vec![
                        r#"<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>"#.to_string(),
                        r#"<w:r><w:fldChar w:fldCharType="begin"/></w:r>"#.to_string(),
                        format!(r#"<w:r><w:instrText xml:space="preserve"> TOC \o "1-{levels}" \h \z \u </w:instrText></w:r>"#),
                        r#"<w:r><w:fldChar w:fldCharType="separate"/></w:r>"#.to_string(),
                        r#"<w:r><w:t>（请在 Word 中右键更新目录）</w:t></w:r>"#.to_string(),
                        r#"<w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>"#.to_string(),
                    ];
                    parts.join("\n")
                } else {
                    xml_utils::toc_field_xml()
                };
                para_parts.insert(idx, toc_field);
                para_parts.insert(idx, toc_title);
            }
        }
    }

    // ── Multi-section support ──
    let multi_section = !extracted.detected_sections.is_empty() && !template.sections.is_empty();
    if multi_section {
        let total_sections = extracted.detected_sections.len();
        for (sec_idx, section) in extracted.detected_sections.iter().enumerate() {
            if sec_idx >= total_sections - 1 {
                break;
            }
            let end_para = section.end_paragraph_index;
            if end_para < para_parts.len() {
                let policy = if sec_idx < template.sections.len() {
                    &template.sections[sec_idx]
                } else {
                    &SectionPolicy::default()
                };
                let sect_pr = xml_utils::section_properties_from_policy(
                    policy,
                    &template.page,
                    "rIdFooter1",
                    Some("rIdHeader1"),
                );
                let old = para_parts[end_para].clone();
                para_parts[end_para] = xml_utils::inject_section_break(&old, &sect_pr);
            }
        }
    }

    // ── Phase 2: Build final body with table interleaving ──
    let body_xml = if layout_plan.is_some() && !tables_after.is_empty() {
        // Interleave tables at their planned positions
        let mut body_parts: Vec<String> = Vec::with_capacity(para_parts.len() + extracted.tables.len());
        for (i, para_xml) in para_parts.into_iter().enumerate() {
            body_parts.push(para_xml);
            if let Some(placements) = tables_after.get(&i) {
                for placement in placements {
                    if placement.table_index < extracted.tables.len() {
                        let table = &extracted.tables[placement.table_index];
                        let cap_style = &template.caption_table;
                        let col_widths = table_plan_map
                            .get(&placement.table_index)
                            .map(|tp| tp.col_widths_twips.as_slice())
                            .unwrap_or(&[4000]);
                        body_parts.push(xml_utils::three_line_table_xml(
                            table, &template.table, cap_style, col_widths, placement.include_caption,
                        ));
                    }
                }
            }
        }
        body_parts.join("\n")
    } else {
        // No LayoutPlan: legacy behavior — paragraphs first, then all tables at end
        let mut parts: Vec<String> = Vec::with_capacity(para_parts.len() + extracted.tables.len());
        let para_xml = para_parts.join("\n");
        parts.push(para_xml);
        for table in &extracted.tables {
            let cap_style = &template.caption_table;
            let col_count = table.col_count.max(1);
            let col_width = 8500 / col_count as i64;
            let col_widths: Vec<i64> = vec![col_width; col_count];
            parts.push(xml_utils::three_line_table_xml(
                table, &template.table, cap_style, &col_widths, true,
            ));
        }
        parts.join("\n")
    };

    let section_xml = xml_utils::section_properties_xml(&template.page);
    let doc_xml = xml_utils::document_xml(&template.page, &body_xml, &section_xml);

    zip.start_file("word/document.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(doc_xml.as_bytes()).map_err(|e| e.to_string())?;

    for img in &extracted.images {
        if let Some(ref blob) = img.blob {
            // media_path already includes "word/" prefix from the parser
            zip.start_file(&img.media_path, options).map_err(|e| e.to_string())?;
            zip.write_all(blob).map_err(|e| e.to_string())?;
        }
    }

    zip.finish().map_err(|e| format!("Failed to finalize zip: {e}"))?;
    Ok(())
}

/// Strip trailing formula number pattern like (1-1), (2.3), （1-1） from text.
fn strip_formula_number(text: &str) -> &str {
    let trimmed = text.trim_end();
    // Check for patterns: (N-M), (N.M), （N-M）, （N.M）
    if let Some(rest) = trimmed.strip_suffix(')') {
        if let Some(pos) = rest.rfind('(') {
            let inside = &rest[pos + 1..];
            if inside.chars().all(|c| c.is_ascii_digit() || c == '-' || c == '.') {
                return rest[..pos].trim_end();
            }
        }
    }
    if let Some(rest) = trimmed.strip_suffix('）') {
        if let Some(pos) = rest.rfind('（') {
            let inside = &rest[pos + 3..]; // '（' is 3 bytes in UTF-8
            if inside.chars().all(|c| c.is_ascii_digit() || c == '-' || c == '.') {
                return rest[..pos].trim_end();
            }
        }
    }
    trimmed
}

fn style_for_type<'a>(ptype: &ParagraphType, template: &'a TemplateConfig) -> &'a ParagraphStyle {
    match ptype {
        ParagraphType::Heading1 => &template.heading1,
        ParagraphType::Heading2 => &template.heading2,
        ParagraphType::Heading3 => &template.heading3,
        ParagraphType::Body | ParagraphType::Unknown => &template.body,
        ParagraphType::BodyIndent => &template.body_indent,
        ParagraphType::CaptionFigure => &template.caption_figure,
        ParagraphType::CaptionTable => &template.caption_table,
        ParagraphType::Reference => &template.reference,
        ParagraphType::Abstract => &template.abstract_style,
        ParagraphType::Keywords => &template.keywords,
        ParagraphType::Quote => &template.quote,
        ParagraphType::ListItem => &template.list_item,
        ParagraphType::Toc => &template.body,
        ParagraphType::Code => &template.body,
        ParagraphType::Cover => &template.heading1,
        ParagraphType::Appendix => &template.heading1,
        ParagraphType::Formula => &template.body,
    }
}

fn style_id_for_type(ptype: &ParagraphType) -> &'static str {
    match ptype {
        ParagraphType::Heading1 => "Heading1",
        ParagraphType::Heading2 => "Heading2",
        ParagraphType::Heading3 => "Heading3",
        ParagraphType::Body | ParagraphType::Unknown => "Normal",
        ParagraphType::BodyIndent => "BodyIndent",
        ParagraphType::CaptionFigure => "CaptionFigure",
        ParagraphType::CaptionTable => "CaptionTable",
        ParagraphType::Reference => "Reference",
        ParagraphType::Abstract => "Abstract",
        ParagraphType::Keywords => "Keywords",
        ParagraphType::Quote => "Quote",
        ParagraphType::ListItem => "ListItem",
        ParagraphType::Toc => "Normal",
        ParagraphType::Code => "Normal",
        ParagraphType::Cover => "Heading1",
        ParagraphType::Appendix => "Heading1",
        ParagraphType::Formula => "Normal",
    }
}
