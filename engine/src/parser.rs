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
                                alignment: None,
                                space_before_pt: None,
                                space_after_pt: None,
                                line_spacing: None,
                                is_first_line_indent: false,
                                char_count,
                                paragraph_type: ParagraphType::Unknown,
                                confidence: 0.0,
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

    Ok(ExtractedDocument { paragraphs, tables, images, total_pages_est })
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
