/// Streaming docx parser — reads .docx with constant memory.
///
/// Strategy: open the zip, read document.xml as a stream of XML events,
/// extract paragraphs/tables inline without building a full DOM tree.
/// Images are read from zip entries by reference (lazy — only path + content_type
/// are extracted; blob is loaded on demand by the assembler).
use std::io::{Read, Cursor};
use std::collections::HashMap;
use quick_xml::events::Event;
use quick_xml::Reader;
use zip::ZipArchive;

use crate::models::*;

/// Resolved style properties from styles.xml
#[derive(Debug, Clone, Default)]
struct StyleDef {
    based_on: Option<String>,
    font_name: Option<String>,
    font_size_pt: Option<f64>,
    bold: Option<bool>,
    italic: Option<bool>,
    alignment: Option<String>,
    space_before_pt: Option<f64>,
    space_after_pt: Option<f64>,
    line_spacing: Option<f64>,
    first_line_indent: bool,
}

fn get_attr(e: &quick_xml::events::BytesStart, key: &[u8]) -> Option<String> {
    for attr in e.attributes().flatten() {
        if attr.key.as_ref() == key {
            return Some(String::from_utf8_lossy(&attr.value).to_string());
        }
    }
    None
}

/// Parse a .docx file into an ExtractedDocument.
/// Memory: only keeps the current paragraph + the output vectors.
pub fn parse_docx(path: &str) -> Result<ExtractedDocument, String> {
    let file = std::fs::File::open(path).map_err(|e| format!("Cannot open file: {e}"))?;
    let mut archive = ZipArchive::new(file).map_err(|e| format!("Invalid zip: {e}"))?;

    let xml_bytes = {
        let mut doc_file = archive.by_name("word/document.xml")
            .map_err(|e| format!("No document.xml: {e}"))?;
        let mut buf = Vec::new();
        doc_file.read_to_end(&mut buf).map_err(|e| format!("Read error: {e}"))?;
        buf
    };

    let styles = parse_styles_xml(&mut archive);
    let numbering = parse_numbering_xml(&mut archive);

    let image_rels = read_image_rels(&mut archive);
    let media_types = read_media_types(&mut archive);

    let mut reader = Reader::from_reader(Cursor::new(&xml_bytes));
    reader.config_mut().trim_text(true);

    let mut paragraphs: Vec<ExtractedParagraph> = Vec::new();
    let mut tables: Vec<ExtractedTable> = Vec::new();

    let mut in_paragraph = false;
    let mut in_run = false;
    let mut in_table = false;
    let mut current_text = String::new();
    let mut current_bold = false;
    let mut current_font_size_pt: Option<f64> = None;
    let mut current_font_name: Option<String> = None;
    let mut current_italic = false;
    let mut current_pstyle: Option<String> = None;
    let mut current_alignment: Option<String> = None;
    let mut current_space_before: Option<f64> = None;
    let mut current_space_after: Option<f64> = None;
    let mut current_line_spacing: Option<f64> = None;
    let mut current_first_line_indent: bool = false;
    let mut in_ppr = false; // inside w:pPr

    let mut current_table_rows: Vec<Vec<String>> = Vec::new();
    let mut current_row_cells: Vec<String> = Vec::new();
    let mut in_cell = false;
    let mut cell_text = String::new();

    let mut run_font_size: Option<f64> = None;
    let mut run_font_name: Option<String> = None;
    let mut run_bold = false;
    let mut run_italic = false;

    let mut buf = Vec::new();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                match tag.as_str() {
                    "w:p" => {
                        in_paragraph = true;
                        current_text.clear();
                        current_bold = false;
                        current_font_size_pt = None;
                        current_font_name = None;
                        current_italic = false;
                        current_pstyle = None;
                        current_alignment = None;
                        current_space_before = None;
                        current_space_after = None;
                        current_line_spacing = None;
                        current_first_line_indent = false;
                        in_ppr = false;
                    }
                    "w:pPr" => { in_ppr = true; }
                    "w:pStyle" if in_ppr => {
                        current_pstyle = get_attr(e, b"w:val");
                    }
                    "w:jc" if in_ppr => {
                        if let Some(val) = get_attr(e, b"w:val") {
                            current_alignment = Some(match val.as_str() {
                                "both" | "distribute" => "justify".to_string(),
                                other => other.to_string(),
                            });
                        }
                    }
                    "w:spacing" if in_ppr => {
                        // before/after in twips (1/20 pt), line in 240ths of a line
                        if let Some(val) = get_attr(e, b"w:before") {
                            if let Ok(twips) = val.parse::<f64>() {
                                current_space_before = Some(twips / 20.0);
                            }
                        }
                        if let Some(val) = get_attr(e, b"w:after") {
                            if let Ok(twips) = val.parse::<f64>() {
                                current_space_after = Some(twips / 20.0);
                            }
                        }
                        if let Some(val) = get_attr(e, b"w:line") {
                            if let Ok(raw) = val.parse::<f64>() {
                                // lineRule="auto" → 240 = 1.0 line spacing
                                let rule = get_attr(e, b"w:lineRule");
                                if rule.as_deref() != Some("exact") && rule.as_deref() != Some("atLeast") {
                                    current_line_spacing = Some(raw / 240.0);
                                } else {
                                    // exact/atLeast → line value is in twips
                                    current_line_spacing = Some(raw / 20.0);
                                }
                            }
                        }
                    }
                    "w:ind" if in_ppr => {
                        if let Some(val) = get_attr(e, b"w:firstLine") {
                            if let Ok(v) = val.parse::<f64>() {
                                if v > 0.0 {
                                    current_first_line_indent = true;
                                }
                            }
                        } else if let Some(val) = get_attr(e, b"w:firstLineChars") {
                            if let Ok(v) = val.parse::<f64>() {
                                if v > 0.0 {
                                    current_first_line_indent = true;
                                }
                            }
                        }
                    }
                    "w:r" => {
                        in_run = true;
                        run_font_size = None;
                        run_font_name = None;
                        run_bold = false;
                        run_italic = false;
                    }
                    "w:b" => { run_bold = true; }
                    "w:i" => { run_italic = true; }
                    "w:sz" if in_run => {
                        if let Some(val) = get_attr(e, b"w:val") {
                            if let Ok(half_points) = val.parse::<f64>() {
                                run_font_size = Some(half_points / 2.0);
                            }
                        }
                    }
                    "w:rFonts" if in_run => {
                        if let Some(val) = get_attr(e, b"w:eastAsia") {
                            run_font_name = Some(val.to_string());
                        } else if let Some(val) = get_attr(e, b"w:ascii") {
                            run_font_name = Some(val.to_string());
                        }
                    }
                    "w:tbl" => { in_table = true; current_table_rows.clear(); }
                    "w:tr" if in_table => { current_row_cells.clear(); }
                    "w:tc" if in_table => { in_cell = true; cell_text.clear(); }
                    _ => {}
                }
            }
            Ok(Event::Text(ref e)) => {
                let text = e.unescape().unwrap_or_default().to_string();
                if in_cell && in_table {
                    cell_text.push_str(&text);
                } else if in_paragraph && in_run {
                    current_text.push_str(&text);
                }
            }
            Ok(Event::End(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                match tag.as_str() {
                    "w:p" => {
                        if in_paragraph {
                            let text = current_text.trim().to_string();
                            let char_count = text.chars().count();
                            paragraphs.push(ExtractedParagraph {
                                index: paragraphs.len(),
                                text,
                                font_size_pt: current_font_size_pt.or(run_font_size),
                                font_name: current_font_name.clone().or(run_font_name.clone()),
                                bold: current_bold || run_bold,
                                italic: current_italic || run_italic,
                                alignment: current_alignment.take(),
                                space_before_pt: current_space_before,
                                space_after_pt: current_space_after,
                                line_spacing: current_line_spacing,
                                is_first_line_indent: current_first_line_indent,
                                char_count,
                                paragraph_type: ParagraphType::Unknown,
                                confidence: 0.0,
                                paragraph_style_name: current_pstyle.take(),
                            });
                            in_paragraph = false;
                        }
                    }
                    "w:r" => {
                        if in_paragraph {
                            if current_font_size_pt.is_none() && run_font_size.is_some() {
                                current_font_size_pt = run_font_size;
                            }
                            if current_font_name.is_none() && run_font_name.is_some() {
                                current_font_name = run_font_name.clone();
                            }
                            if run_bold { current_bold = true; }
                            if run_italic { current_italic = true; }
                        }
                        in_run = false;
                    }
                    "w:pPr" => { in_ppr = false; }
                    "w:tc" => {
                        if in_cell {
                            current_row_cells.push(cell_text.trim().to_string());
                            in_cell = false;
                        }
                    }
                    "w:tr" => {
                        if in_table {
                            current_table_rows.push(current_row_cells.clone());
                            current_row_cells.clear();
                        }
                    }
                    "w:tbl" => {
                        if in_table {
                            let rows = current_table_rows.clone();
                            let row_count = rows.len();
                            let col_count = rows.first().map(|r| r.len()).unwrap_or(0);
                            tables.push(ExtractedTable {
                                index: tables.len(),
                                rows,
                                row_count,
                                col_count,
                                has_merged_cells: false,
                                caption: None,
                            });
                            current_table_rows.clear();
                            in_table = false;
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Err(e) => return Err(format!("XML parse error: {e}")),
            _ => {}
        }
        buf.clear();
    }

    // Resolve paragraph formatting from styles.xml where direct formatting is absent
    for para in paragraphs.iter_mut() {
        if let Some(ref style_name) = para.paragraph_style_name {
            if let Some(style_def) = resolve_style(&styles, style_name) {
                if para.font_size_pt.is_none() {
                    para.font_size_pt = style_def.font_size_pt;
                }
                if para.font_name.is_none() {
                    para.font_name = style_def.font_name.clone();
                }
                if !para.bold {
                    para.bold = style_def.bold.unwrap_or(false);
                }
                if !para.italic {
                    para.italic = style_def.italic.unwrap_or(false);
                }
                if para.alignment.is_none() {
                    para.alignment = style_def.alignment.clone();
                }
                if para.space_before_pt.is_none() {
                    para.space_before_pt = style_def.space_before_pt;
                }
                if para.space_after_pt.is_none() {
                    para.space_after_pt = style_def.space_after_pt;
                }
                if para.line_spacing.is_none() {
                    para.line_spacing = style_def.line_spacing;
                }
                if !para.is_first_line_indent {
                    para.is_first_line_indent = style_def.first_line_indent;
                }
            }
        }
    }

    let mut images: Vec<ExtractedImage> = Vec::new();
    for (i, (_rel_id, target)) in image_rels.iter().enumerate() {
        let media_path = format!("word/{}", target);
        let content_type = media_types.get(target)
            .cloned()
            .unwrap_or_else(|| "application/octet-stream".to_string());
        images.push(ExtractedImage {
            index: i,
            media_path,
            content_type,
            width_px: None,
            height_px: None,
            caption: None,
            blob: None,
        });
    }

    link_captions(&mut paragraphs, &mut tables, &mut images);

    let total_chars: usize = paragraphs.iter().map(|p| p.char_count).sum();
    let total_pages_est = std::cmp::max(1, total_chars / (30 * 35));

    Ok(ExtractedDocument { paragraphs, tables, images, numbering, detected_sections: Vec::new(), total_pages_est })
}

/// Parse word/styles.xml into a map of styleId → StyleDef.
/// Walks basedOn chains so each StyleDef has fully resolved properties.
fn parse_styles_xml(archive: &mut ZipArchive<std::fs::File>) -> HashMap<String, StyleDef> {
    let xml = match read_zip_entry(archive, "word/styles.xml") {
        Some(b) => b,
        None => return HashMap::new(),
    };

    let mut reader = Reader::from_reader(Cursor::new(&xml));
    let mut buf = Vec::new();

    let mut raw_styles: HashMap<String, StyleDef> = HashMap::new();
    let mut current_id: Option<String> = None;
    let mut current_def = StyleDef::default();
    let mut in_rpr = false;
    let mut in_ppr = false;

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                match tag.as_str() {
                    "w:style" => {
                        let stype = get_attr(e, b"w:type").unwrap_or_default();
                        if stype == "paragraph" || stype == "" {
                            current_id = get_attr(e, b"w:styleId");
                            current_def = StyleDef::default();
                            in_rpr = false;
                            in_ppr = false;
                        } else {
                            current_id = None; // skip non-paragraph styles
                        }
                    }
                    "w:basedOn" if current_id.is_some() => {
                        current_def.based_on = get_attr(e, b"w:val");
                    }
                    "w:rPr" if current_id.is_some() => { in_rpr = true; }
                    "w:pPr" if current_id.is_some() => { in_ppr = true; }
                    "w:rFonts" if in_rpr => {
                        if let Some(val) = get_attr(e, b"w:eastAsia") {
                            current_def.font_name = Some(val);
                        } else if let Some(val) = get_attr(e, b"w:ascii") {
                            current_def.font_name = Some(val);
                        }
                    }
                    "w:sz" if in_rpr => {
                        if let Some(val) = get_attr(e, b"w:val") {
                            if let Ok(hp) = val.parse::<f64>() {
                                current_def.font_size_pt = Some(hp / 2.0);
                            }
                        }
                    }
                    "w:b" if in_rpr => {
                        // w:b can be an Empty element (self-closing) with w:val="0" to turn off bold
                        let val = get_attr(e, b"w:val");
                        current_def.bold = Some(val.as_deref() != Some("0") && val.as_deref() != Some("false"));
                    }
                    "w:i" if in_rpr => {
                        let val = get_attr(e, b"w:val");
                        current_def.italic = Some(val.as_deref() != Some("0") && val.as_deref() != Some("false"));
                    }
                    "w:jc" if in_ppr => {
                        if let Some(val) = get_attr(e, b"w:val") {
                            current_def.alignment = Some(match val.as_str() {
                                "both" | "distribute" => "justify".to_string(),
                                other => other.to_string(),
                            });
                        }
                    }
                    "w:spacing" if in_ppr => {
                        if let Some(val) = get_attr(e, b"w:before") {
                            if let Ok(twips) = val.parse::<f64>() {
                                current_def.space_before_pt = Some(twips / 20.0);
                            }
                        }
                        if let Some(val) = get_attr(e, b"w:after") {
                            if let Ok(twips) = val.parse::<f64>() {
                                current_def.space_after_pt = Some(twips / 20.0);
                            }
                        }
                        if let Some(val) = get_attr(e, b"w:line") {
                            if let Ok(raw) = val.parse::<f64>() {
                                let rule = get_attr(e, b"w:lineRule");
                                if rule.as_deref() != Some("exact") && rule.as_deref() != Some("atLeast") {
                                    current_def.line_spacing = Some(raw / 240.0);
                                } else {
                                    current_def.line_spacing = Some(raw / 20.0);
                                }
                            }
                        }
                    }
                    "w:ind" if in_ppr => {
                        if let Some(val) = get_attr(e, b"w:firstLine") {
                            if let Ok(v) = val.parse::<f64>() {
                                if v > 0.0 { current_def.first_line_indent = true; }
                            }
                        } else if let Some(val) = get_attr(e, b"w:firstLineChars") {
                            if let Ok(v) = val.parse::<f64>() {
                                if v > 0.0 { current_def.first_line_indent = true; }
                            }
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::End(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                match tag.as_str() {
                    "w:rPr" => { in_rpr = false; }
                    "w:pPr" => { in_ppr = false; }
                    "w:style" => {
                        if let Some(id) = current_id.take() {
                            raw_styles.insert(id, current_def.clone());
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            _ => {}
        }
        buf.clear();
    }

    // Resolve basedOn chains (max depth 10 to avoid cycles)
    let mut resolved: HashMap<String, StyleDef> = HashMap::new();
    for (id, def) in &raw_styles {
        let mut eff = def.clone();
        let mut seen = std::collections::HashSet::new();
        seen.insert(id.clone());
        while let Some(ref parent_id) = eff.based_on.clone() {
            if seen.contains(parent_id) { break; } // cycle protection
            seen.insert(parent_id.clone());
            if let Some(parent) = raw_styles.get(parent_id) {
                if eff.font_name.is_none() { eff.font_name = parent.font_name.clone(); }
                if eff.font_size_pt.is_none() { eff.font_size_pt = parent.font_size_pt; }
                if eff.bold.is_none() { eff.bold = parent.bold; }
                if eff.italic.is_none() { eff.italic = parent.italic; }
                if eff.alignment.is_none() { eff.alignment = parent.alignment.clone(); }
                if eff.space_before_pt.is_none() { eff.space_before_pt = parent.space_before_pt; }
                if eff.space_after_pt.is_none() { eff.space_after_pt = parent.space_after_pt; }
                if eff.line_spacing.is_none() { eff.line_spacing = parent.line_spacing; }
                if !eff.first_line_indent { eff.first_line_indent = parent.first_line_indent; }
                eff.based_on = parent.based_on.clone();
            } else {
                break;
            }
        }
        resolved.insert(id.clone(), eff);
    }

    resolved
}

fn resolve_style<'a>(styles: &'a HashMap<String, StyleDef>, style_name: &str) -> Option<&'a StyleDef> {
    styles.get(style_name)
}

/// Parse word/numbering.xml into a list of NumberingDef.
/// Reads w:abstractNum and w:num elements to extract numbering definitions.
fn parse_numbering_xml(archive: &mut ZipArchive<std::fs::File>) -> Vec<NumberingDef> {
    let mut defs = Vec::new();
    let xml = match read_zip_entry(archive, "word/numbering.xml") {
        Some(b) => b,
        None => return defs,
    };

    // Track abstract numbering definitions: abstractNumId → Vec<NumberingLevel>
    let mut abstract_nums: HashMap<u32, Vec<NumberingLevel>> = HashMap::new();

    let mut reader = Reader::from_reader(Cursor::new(&xml));
    let mut buf = Vec::new();
    let mut current_abstract_id: Option<u32> = None;
    let mut current_levels: Vec<NumberingLevel> = Vec::new();
    let mut in_abstract_num = false;
    let mut in_num = false;
    let mut current_num_id: Option<u32> = None;
    let mut current_abstract_ref: Option<u32> = None;
    let mut in_lvl = false;
    let mut current_lvl_ilvl: u32 = 0;
    let mut current_lvl_format: String = String::new();
    let mut current_lvl_text: String = String::new();
    let mut current_lvl_align: String = "left".to_string();

    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Start(ref e)) | Ok(Event::Empty(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();

                match tag.as_str() {
                    "w:abstractNum" => {
                        if let Some(id) = get_attr(e, b"w:abstractNumId") {
                            current_abstract_id = id.parse().ok();
                            current_levels.clear();
                            in_abstract_num = true;
                        }
                    }
                    "w:num" => {
                        if let Some(id) = get_attr(e, b"w:numId") {
                            current_num_id = id.parse().ok();
                            current_abstract_ref = None;
                            in_num = true;
                        }
                    }
                    "w:abstractNumId" => {
                        // Inside w:num, this references the abstract num
                        if in_num {
                            if let Some(val) = get_attr(e, b"w:val") {
                                current_abstract_ref = val.parse().ok();
                            }
                        }
                    }
                    "w:lvl" => {
                        if let Some(ilvl) = get_attr(e, b"w:ilvl") {
                            current_lvl_ilvl = ilvl.parse().unwrap_or(0);
                            current_lvl_format.clear();
                            current_lvl_text.clear();
                            current_lvl_align = "left".to_string();
                            in_lvl = true;
                        }
                    }
                    "w:numFmt" => {
                        if in_lvl {
                            if let Some(val) = get_attr(e, b"w:val") {
                                current_lvl_format = val;
                            }
                        }
                    }
                    "w:lvlText" => {
                        if in_lvl {
                            if let Some(val) = get_attr(e, b"w:val") {
                                current_lvl_text = val;
                            }
                        }
                    }
                    "w:jc" => {
                        if in_lvl {
                            if let Some(val) = get_attr(e, b"w:val") {
                                current_lvl_align = match val.as_str() {
                                    "center" => "center".to_string(),
                                    "right" => "right".to_string(),
                                    _ => "left".to_string(),
                                };
                            }
                        }
                    }
                    _ => {}
                }
            }
            Ok(Event::End(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                match tag.as_str() {
                    "w:lvl" => {
                        if in_lvl && in_abstract_num {
                            current_levels.push(NumberingLevel {
                                level: current_lvl_ilvl,
                                format: current_lvl_format.clone(),
                                text: current_lvl_text.clone(),
                                alignment: current_lvl_align.clone(),
                            });
                        }
                        in_lvl = false;
                    }
                    "w:abstractNum" => {
                        if let Some(id) = current_abstract_id.take() {
                            abstract_nums.insert(id, std::mem::take(&mut current_levels));
                        }
                        in_abstract_num = false;
                    }
                    "w:num" => {
                        if let (Some(num_id), Some(abs_id)) = (current_num_id.take(), current_abstract_ref.take()) {
                            let levels = abstract_nums.get(&abs_id).cloned().unwrap_or_default();
                            defs.push(NumberingDef {
                                num_id,
                                abstract_num_id: abs_id,
                                levels,
                            });
                        }
                        in_num = false;
                    }
                    _ => {}
                }
            }
            Ok(Event::Eof) => break,
            Err(_) => break,
            _ => {}
        }
        buf.clear();
    }

    defs
}

fn read_image_rels(archive: &mut ZipArchive<std::fs::File>) -> Vec<(String, String)> {
    let mut rels = Vec::new();
    let xml = match read_zip_entry(archive, "word/_rels/document.xml.rels") {
        Some(b) => b,
        None => return rels,
    };
    let mut reader = Reader::from_reader(Cursor::new(&xml));
    let mut buf = Vec::new();
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Empty(ref e)) | Ok(Event::Start(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                if tag.ends_with("Relationship") || tag == "Relationship" {
                    let id = get_attr(e, b"Id").unwrap_or_default();
                    let target = get_attr(e, b"Target").unwrap_or_default();
                    let rel_type = get_attr(e, b"Type").unwrap_or_default();
                    if rel_type.contains("image") {
                        rels.push((id, target));
                    }
                }
            }
            Ok(Event::Eof) => break,
            _ => {}
        }
        buf.clear();
    }
    rels
}

fn read_media_types(archive: &mut ZipArchive<std::fs::File>) -> HashMap<String, String> {
    let mut types = HashMap::new();
    let xml = match read_zip_entry(archive, "[Content_Types].xml") {
        Some(b) => b,
        None => return types,
    };
    let mut reader = Reader::from_reader(Cursor::new(&xml));
    let mut buf = Vec::new();
    loop {
        match reader.read_event_into(&mut buf) {
            Ok(Event::Empty(ref e)) => {
                let tag = String::from_utf8_lossy(e.name().as_ref()).to_string();
                if tag == "Override" {
                    let part = get_attr(e, b"PartName").unwrap_or_default();
                    let ct = get_attr(e, b"ContentType").unwrap_or_default();
                    if part.contains("media/") {
                        let name = part.trim_start_matches('/').to_string();
                        types.insert(name, ct);
                    }
                } else if tag == "Default" {
                    let ext = get_attr(e, b"Extension").unwrap_or_default();
                    let ct = get_attr(e, b"ContentType").unwrap_or_default();
                    types.insert(ext, ct);
                }
            }
            Ok(Event::Eof) => break,
            _ => {}
        }
        buf.clear();
    }
    types
}

fn read_zip_entry(archive: &mut ZipArchive<std::fs::File>, name: &str) -> Option<Vec<u8>> {
    let mut f = archive.by_name(name).ok()?;
    let mut buf = Vec::new();
    f.read_to_end(&mut buf).ok()?;
    Some(buf)
}

fn link_captions(
    paragraphs: &mut [ExtractedParagraph],
    tables: &mut [ExtractedTable],
    images: &mut [ExtractedImage],
) {
    for para in paragraphs.iter_mut() {
        let text = para.text.trim();
        if text.is_empty() { continue; }
        if text.starts_with("图 ") || text.starts_with("图\t") {
            for img in images.iter_mut() {
                if img.caption.is_none() {
                    img.caption = Some(text.to_string());
                    para.paragraph_type = ParagraphType::CaptionFigure;
                    para.confidence = 0.95;
                    break;
                }
            }
        }
        if text.starts_with("表 ") || text.starts_with("表\t") {
            for tbl in tables.iter_mut() {
                if tbl.caption.is_none() {
                    tbl.caption = Some(text.to_string());
                    para.paragraph_type = ParagraphType::CaptionTable;
                    para.confidence = 0.95;
                    break;
                }
            }
        }
    }
}
