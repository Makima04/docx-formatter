/// Docx assembler — builds the final .docx zip package.
///
/// Takes a classified ExtractedDocument + TemplateConfig, generates all XML
/// in Rust, and writes the zip directly. No intermediate files, constant memory.
use std::io::Write;
use zip::write::FileOptions;
use zip::CompressionMethod;

use crate::models::*;
use crate::xml_utils;

pub fn assemble_docx(
    extracted: &ExtractedDocument,
    template: &TemplateConfig,
    output_path: &str,
) -> Result<(), String> {
    let file = std::fs::File::create(output_path)
        .map_err(|e| format!("Cannot create output file: {e}"))?;
    let mut zip = zip::ZipWriter::new(file);
    let options = FileOptions::default().compression_method(CompressionMethod::Stored);

    zip.start_file("[Content_Types].xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::content_types_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("_rels/.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::root_rels_xml().as_bytes()).map_err(|e| e.to_string())?;

    let image_rids: Vec<String> = extracted.images.iter()
        .map(|i| format!("rId{}", 100 + i.index))
        .collect();
    zip.start_file("word/_rels/document.xml.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::document_rels_xml(&image_rids).as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/styles.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::styles_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/settings.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::settings_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/numbering.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::numbering_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/footer1.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::footer_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("word/_rels/footer1.xml.rels", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::footer_rels_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("docProps/core.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::core_xml().as_bytes()).map_err(|e| e.to_string())?;

    zip.start_file("docProps/app.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(xml_utils::app_xml().as_bytes()).map_err(|e| e.to_string())?;

    // ── Build document.xml content ──
    let mut para_xml = String::new();
    let mut image_idx = 0usize;

    for para in &extracted.paragraphs {
        let text = para.text.trim();
        if text.is_empty() {
            para_xml.push_str("<w:p/>");
            continue;
        }

        let style = style_for_type(&para.paragraph_type, template);

        match para.paragraph_type {
            ParagraphType::CaptionFigure => {
                if image_idx < extracted.images.len() {
                    let img = &extracted.images[image_idx];
                    let img_style = ParagraphStyle {
                        font_name: "SimSun".to_string(),
                        font_size_pt: 10.0,
                        alignment: "center".to_string(),
                        ..Default::default()
                    };
                    para_xml.push_str(&xml_utils::paragraph_xml(
                        &format!("[图片: {}]", img.media_path),
                        &img_style,
                    ));
                    image_idx += 1;
                }
                para_xml.push_str(&xml_utils::paragraph_xml(text, style));
            }
            _ => {
                para_xml.push_str(&xml_utils::paragraph_xml(text, style));
            }
        }
    }

    let mut table_xml = String::new();
    for table in &extracted.tables {
        let cap_style = &template.caption_table;
        table_xml.push_str(&xml_utils::three_line_table_xml(table, &template.table, cap_style));
    }

    let section_xml = xml_utils::section_properties_xml(&template.page);
    let doc_xml = xml_utils::document_xml(&template.page, &para_xml, &table_xml, &section_xml);

    zip.start_file("word/document.xml", options).map_err(|e| e.to_string())?;
    zip.write_all(doc_xml.as_bytes()).map_err(|e| e.to_string())?;

    for img in &extracted.images {
        if let Some(ref blob) = img.blob {
            let media_name = format!("word/{}", img.media_path);
            zip.start_file(media_name, options).map_err(|e| e.to_string())?;
            zip.write_all(blob).map_err(|e| e.to_string())?;
        }
    }

    zip.finish().map_err(|e| format!("Failed to finalize zip: {e}"))?;
    Ok(())
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
    }
}
