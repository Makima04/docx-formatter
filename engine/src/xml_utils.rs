/// Low-level OOXML XML building helpers.
///
/// All functions return XML fragment strings that can be inserted into
/// the docx structure. This module owns ALL raw XML generation.
use crate::models::*;

const XML_HEADER: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"#;
const W_NS: &str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const R_NS: &str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const WP_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing";

fn cm_to_emu(cm: f64) -> i64 { (cm * 360000.0).round() as i64 }
fn pt_to_half_points(pt: f64) -> i64 { (pt * 2.0).round() as i64 }
fn pt_to_twips(pt: f64) -> i64 { (pt * 20.0).round() as i64 }
fn pt_to_eighths(pt: f64) -> i64 { (pt * 8.0).round() as i64 }

pub fn content_types_xml() -> String {
    format!(r#"{XML_HEADER}
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Default Extension="png" ContentType="image/png"/>
    <Default Extension="jpg" ContentType="image/jpeg"/>
    <Default Extension="jpeg" ContentType="image/jpeg"/>
    <Default Extension="gif" ContentType="image/gif"/>
    <Default Extension="bmp" ContentType="image/bmp"/>
    <Default Extension="wmf" ContentType="image/x-wmf"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
    <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
    <Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
    <Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>
    <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
    <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>"#)
}

pub fn root_rels_xml() -> String {
    format!(r#"{XML_HEADER}
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"#)
}

pub fn document_rels_xml(image_rids: &[String]) -> String {
    let mut entries = vec![
        format!(r#"    <Relationship Id="rId1" Type="{R_NS}/styles" Target="styles.xml"/>"#),
        format!(r#"    <Relationship Id="rId2" Type="{R_NS}/numbering" Target="numbering.xml"/>"#),
        format!(r#"    <Relationship Id="rId3" Type="{R_NS}/settings" Target="settings.xml"/>"#),
        format!(r#"    <Relationship Id="rIdFooter1" Type="{R_NS}/footer" Target="footer1.xml"/>"#),
    ];
    for (i, _) in image_rids.iter().enumerate() {
        let rid = format!("rId{}", 100 + i);
        entries.push(format!(
            r#"    <Relationship Id="{rid}" Type="{R_NS}/image" Target="media/image{}.png" />"#,
            i + 1
        ));
    }
    format!(
        r#"{XML_HEADER}
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
{}
</Relationships>"#,
        entries.join("\n")
    )
}

pub fn styles_xml() -> String {
    format!(r#"{XML_HEADER}
<w:styles xmlns:w="{W_NS}">
    <w:style w:type="paragraph" w:default="1" w:styleId="Normal">
        <w:name w:val="Normal"/>
        <w:rPr>
            <w:rFonts w:ascii="SimSun" w:eastAsia="SimSun" w:hAnsi="SimSun"/>
            <w:sz w:val="24"/>
        </w:rPr>
    </w:style>
</w:styles>"#)
}

pub fn settings_xml() -> String {
    format!(r#"{XML_HEADER}
<w:settings xmlns:w="{W_NS}">
    <w:defaultTabStop w:val="420"/>
</w:settings>"#)
}

pub fn numbering_xml() -> String {
    format!(r#"{XML_HEADER}
<w:numbering xmlns:w="{W_NS}"/>"#)
}

pub fn core_xml() -> String {
    format!(r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
                   xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>Formatted Document</dc:title>
    <dc:creator>Docx Formatter</dc:creator>
</cp:coreProperties>"#)
}

pub fn app_xml() -> String {
    format!(r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties">
    <Application>Docx Formatter</Application>
</Properties>"#)
}

/// Build the complete word/document.xml
pub fn document_xml(page: &PageStyle, paragraphs_xml: &str, tables_xml: &str, section_xml: &str) -> String {
    format!(
        r#"{XML_HEADER}
<w:document xmlns:w="{W_NS}" xmlns:r="{R_NS}" xmlns:wp="{WP_NS}">
<w:body>
{paragraphs_xml}
{tables_xml}
{section_xml}
</w:body>
</w:document>"#
    )
}

/// Build section properties (page size, margins, page numbering)
pub fn section_properties_xml(page: &PageStyle) -> String {
    let w = cm_to_emu(page.page_width_cm);
    let h = cm_to_emu(page.page_height_cm);
    let mt = cm_to_emu(page.margin_top_cm);
    let mb = cm_to_emu(page.margin_bottom_cm);
    let ml = cm_to_emu(page.margin_left_cm);
    let mr = cm_to_emu(page.margin_right_cm);
    let hd = cm_to_emu(page.header_distance_cm);
    let fd = cm_to_emu(page.footer_distance_cm);

    let pg_num = format!(
        r#"<w:pgNumType w:fmt="{}" w:start="{}"/>"#,
        page.page_number_format, page.page_number_start
    );

    format!(
        r#"<w:sectPr>
    <w:pgSz w:w="{w}" w:h="{h}"/>
    <w:pgMar w:top="{mt}" w:right="{mr}" w:bottom="{mb}" w:left="{ml}" w:header="{hd}" w:footer="{fd}" w:gutter="0"/>
    {pg_num}
    <w:footerReference w:type="default" w:id="rIdFooter1"/>
</w:sectPr>"#
    )
}

/// Build a complete <w:p> element for a paragraph with style and text.
pub fn paragraph_xml(text: &str, style: &ParagraphStyle) -> String {
    let align = match style.alignment.as_str() {
        "center" => "center",
        "right" => "right",
        "justify" => "both",
        _ => "left",
    };

    let mut spacing_parts = Vec::new();
    spacing_parts.push(format!("w:before=\"{}\"", pt_to_twips(style.space_before_pt)));
    spacing_parts.push(format!("w:after=\"{}\"", pt_to_twips(style.space_after_pt)));

    if let Some(multiple) = style.line_spacing_multiple {
        let line_val = (multiple * 240.0).round() as i64;
        spacing_parts.push(format!("w:line=\"{line_val}\""));
        spacing_parts.push("w:lineRule=\"auto\"".to_string());
    } else if let Some(exact_pt) = style.line_spacing_pt {
        let line_val = pt_to_twips(exact_pt);
        spacing_parts.push(format!("w:line=\"{line_val}\""));
        spacing_parts.push("w:lineRule=\"exact\"".to_string());
    }
    let spacing = spacing_parts.join(" ");

    let indent_xml = if style.first_line_indent_chars > 0.0 {
        let twips = (style.first_line_indent_chars * style.font_size_pt * 20.0) as i64;
        format!(r#"<w:ind w:firstLine="{twips}"/>"#)
    } else if style.hanging_indent_chars > 0.0 {
        let twips = (style.hanging_indent_chars * style.font_size_pt * 20.0) as i64;
        format!(r#"<w:ind w:left="{twips}" w:hanging="{twips}"/>"#)
    } else {
        String::new()
    };

    let font_east = &style.font_name;
    let font_ascii = if style.font_name.contains("Sim") { "Times New Roman" } else { &style.font_name };
    let sz = pt_to_half_points(style.font_size_pt);
    let b = if style.bold { r#"<w:b/><w:bCs/>"# } else { "" };
    let i = if style.italic { "<w:i/>" } else { "" };
    let escaped_text = escape_xml(text);

    format!(
        r#"<w:p>
    <w:pPr>
        <w:jc w:val="{align}"/>
        <w:spacing {spacing}/>
        {indent_xml}
    </w:pPr>
    <w:r>
        <w:rPr>
            <w:rFonts w:ascii="{font_ascii}" w:eastAsia="{font_east}" w:hAnsi="{font_ascii}"/>
            <w:sz w:val="{sz}"/>
            <w:szCs w:val="{sz}"/>
            {b}
            {i}
        </w:rPr>
        <w:t xml:space="preserve">{escaped_text}</w:t>
    </w:r>
</w:p>"#
    )
}

/// Build a complete table with three-line borders.
pub fn three_line_table_xml(
    table: &ExtractedTable,
    table_style: &TableStyle,
    caption_style: &ParagraphStyle,
) -> String {
    let mut xml = String::new();

    if let Some(ref caption) = table.caption {
        xml.push_str(&paragraph_xml(caption, caption_style));
    }

    if table.rows.is_empty() { return xml; }

    let col_count = table.col_count.max(1);
    let col_width_twips = 8500 / col_count as i64;

    xml.push_str(&format!(
        r#"<w:tbl>
    <w:tblPr>
        <w:tblStyle w:val="TableGrid"/>
        <w:tblW w:w="0" w:type="auto"/>
        <w:jc w:val="center"/>
        <w:tblBorders>
            <w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            <w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            <w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            <w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            <w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>
            <w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>
        </w:tblBorders>
    </w:tblPr>
    <w:tblGrid>"#
    ));

    for _ in 0..col_count {
        xml.push_str(&format!(r#"<w:gridCol w:w="{}"/>"#, col_width_twips));
    }
    xml.push_str("</w:tblGrid>\n");

    for (row_idx, row) in table.rows.iter().enumerate() {
        xml.push_str("<w:tr>\n");
        xml.push_str("    <w:trPr><w:cantSplit/></w:trPr>\n");

        for cell_text in row.iter() {
            let top = if row_idx == 0 { border_xml("top", table_style.top_rule_width_pt) } else { border_xml("top", 0.0) };
            let bottom = if row_idx == 0 {
                border_xml("bottom", table_style.mid_rule_width_pt)
            } else if row_idx == table.rows.len() - 1 {
                border_xml("bottom", table_style.bottom_rule_width_pt)
            } else {
                border_xml("bottom", 0.0)
            };
            let left = border_xml("left", 0.0);
            let right = border_xml("right", 0.0);

            let (font_name, font_size_pt, bold) = if row_idx == 0 {
                (&table_style.header_font_name, table_style.header_font_size_pt, table_style.header_bold)
            } else {
                (&table_style.cell_font_name, table_style.cell_font_size_pt, false)
            };

            let align = match table_style.cell_align.as_str() {
                "center" => "center",
                "right" => "right",
                _ => "left",
            };
            let sz = pt_to_half_points(font_size_pt);
            let b = if bold { r#"<w:b/><w:bCs/>"# } else { "" };
            let escaped = escape_xml(cell_text);

            xml.push_str(&format!(
                r#"    <w:tc>
        <w:tcPr>
            <w:tcW w:w="{col_width_twips}" w:type="dxa"/>
            <w:tcBorders>{top}{left}{bottom}{right}</w:tcBorders>
            <w:vAlign w:val="center"/>
        </w:tcPr>
        <w:p>
            <w:pPr><w:jc w:val="{align}"/><w:spacing w:before="40" w:after="40"/></w:pPr>
            <w:r>
                <w:rPr>
                    <w:rFonts w:ascii="{font_name}" w:eastAsia="{font_name}" w:hAnsi="{font_name}"/>
                    <w:sz w:val="{sz}"/>
                    <w:szCs w:val="{sz}"/>
                    {b}
                </w:rPr>
                <w:t xml:space="preserve">{escaped}</w:t>
            </w:r>
        </w:p>
    </w:tc>"#
            ));
        }
        xml.push_str("</w:tr>\n");
    }
    xml.push_str("</w:tbl>\n");
    xml
}

fn border_xml(edge: &str, width_pt: f64) -> String {
    if width_pt <= 0.0 {
        return format!(r#"<w:{edge} w:val="none" w:sz="0" w:space="0" w:color="auto"/>"#);
    }
    let sz = pt_to_eighths(width_pt);
    format!(r#"<w:{edge} w:val="single" w:sz="{sz}" w:space="0" w:color="000000"/>"#)
}

/// Footer with page number field
pub fn footer_xml() -> String {
    format!(
        r#"{XML_HEADER}
<w:ftr xmlns:w="{W_NS}" xmlns:r="{R_NS}">
    <w:p>
        <w:pPr><w:jc w:val="center"/></w:pPr>
        <w:r>
            <w:rPr><w:sz w:val="18"/><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/></w:rPr>
            <w:fldChar w:fldCharType="begin"/>
        </w:r>
        <w:r>
            <w:rPr><w:sz w:val="18"/></w:rPr>
            <w:instrText xml:space="preserve"> PAGE </w:instrText>
        </w:r>
        <w:r>
            <w:rPr><w:sz w:val="18"/></w:rPr>
            <w:fldChar w:fldCharType="separate"/>
        </w:r>
        <w:r>
            <w:rPr><w:sz w:val="18"/></w:rPr>
            <w:t>1</w:t>
        </w:r>
        <w:r>
            <w:rPr><w:sz w:val="18"/></w:rPr>
            <w:fldChar w:fldCharType="end"/>
        </w:r>
    </w:p>
</w:ftr>"#
    )
}

pub fn footer_rels_xml() -> String {
    format!(
        r#"{XML_HEADER}
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="{R_NS}/styles" Target="../styles.xml"/>
</Relationships>"#
    )
}

fn escape_xml(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}
