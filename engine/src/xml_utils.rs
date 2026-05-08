/// Low-level OOXML XML building helpers.
///
/// All functions return XML fragment strings that can be inserted into
/// the docx structure. This module owns ALL raw XML generation.
use crate::models::*;

const XML_HEADER: &str = r#"<?xml version="1.0" encoding="UTF-8" standalone="yes"?>"#;
const W_NS: &str = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
const R_NS: &str = "http://schemas.openxmlformats.org/officeDocument/2006/relationships";
const WP_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing";
const A_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/main";
const PIC_NS: &str = "http://schemas.openxmlformats.org/drawingml/2006/picture";
const MC_NS: &str = "http://schemas.openxmlformats.org/markup-compatibility/2006";

fn cm_to_emu(cm: f64) -> i64 { (cm * 360000.0).round() as i64 }
fn pt_to_half_points(pt: f64) -> i64 { (pt * 2.0).round() as i64 }
fn pt_to_twips(pt: f64) -> i64 { (pt * 20.0).round() as i64 }
fn pt_to_eighths(pt: f64) -> i64 { (pt * 8.0).round() as i64 }

pub fn content_types_xml(images: &[ExtractedImage]) -> String {
    let mut overrides = String::new();
    for img in images {
        // Use the content_type from the original document
        let part_name = img.media_path.strip_prefix("word/").unwrap_or(&img.media_path);
        overrides.push_str(&format!(
            r#"    <Override PartName="/word/{part_name}" ContentType="{ct}"/>"#,
            ct = img.content_type
        ));
        overrides.push('\n');
    }
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
    <Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>
    <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
    <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
{overrides}</Types>"#)
}

pub fn root_rels_xml() -> String {
    format!(r#"{XML_HEADER}
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
    <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
    <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>"#)
}

pub fn document_rels_xml(images: &[ExtractedImage]) -> String {
    let mut entries = vec![
        format!(r#"    <Relationship Id="rId1" Type="{R_NS}/styles" Target="styles.xml"/>"#),
        format!(r#"    <Relationship Id="rId2" Type="{R_NS}/numbering" Target="numbering.xml"/>"#),
        format!(r#"    <Relationship Id="rId3" Type="{R_NS}/settings" Target="settings.xml"/>"#),
        format!(r#"    <Relationship Id="rIdFooter1" Type="{R_NS}/footer" Target="footer1.xml"/>"#),
        format!(r#"    <Relationship Id="rIdHeader1" Type="{R_NS}/header" Target="header1.xml"/>"#),
    ];
    for img in images {
        let rid = format!("rId{}", 100 + img.index);
        // Strip "word/" prefix from media_path — the rels Target is relative to word/
        let target = img.media_path.strip_prefix("word/").unwrap_or(&img.media_path);
        entries.push(format!(
            r#"    <Relationship Id="{rid}" Type="{R_NS}/image" Target="{target}"/>"#
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

/// Generate styles.xml from TemplateConfig — defines named styles matching
/// the paragraph types so output docx has proper style definitions.
pub fn styles_xml_from_template(template: &TemplateConfig) -> String {
    let mut xml = format!(r#"{XML_HEADER}
<w:styles xmlns:w="{W_NS}">"#);

    // Normal (body) as default
    xml.push_str(&style_def_xml("Normal", "Normal", &template.body, true, None, false));

    // Named heading and paragraph styles — last bool = keep_next
    let style_entries: &[(&str, &str, &ParagraphStyle, bool)] = &[
        ("Heading1", "heading 1", &template.heading1, true),
        ("Heading2", "heading 2", &template.heading2, true),
        ("Heading3", "heading 3", &template.heading3, true),
        ("BodyIndent", "body indent", &template.body_indent, false),
        ("Abstract", "abstract", &template.abstract_style, false),
        ("Keywords", "keywords", &template.keywords, false),
        ("CaptionFigure", "caption figure", &template.caption_figure, true),
        ("CaptionTable", "caption table", &template.caption_table, true),
        ("Reference", "reference", &template.reference, false),
        ("Quote", "quote", &template.quote, false),
        ("ListItem", "list item", &template.list_item, false),
    ];

    for &(style_id, style_name, style, keep_next) in style_entries {
        xml.push_str(&style_def_xml(style_id, style_name, style, false, Some("Normal"), keep_next));
    }

    xml.push_str("\n</w:styles>");
    xml
}

fn style_def_xml(
    style_id: &str,
    style_name: &str,
    style: &ParagraphStyle,
    is_default: bool,
    based_on: Option<&str>,
    keep_next: bool,
) -> String {
    let default_attr = if is_default { r#" w:default="1""# } else { "" };
    let based_on_xml = based_on
        .map(|b| format!(r#"    <w:basedOn w:val="{b}"/>"#))
        .unwrap_or_default();

    let font_east = &style.font_name;
    let font_ascii = if style.font_name.contains("Sim") { "Times New Roman" } else { &style.font_name };
    let sz = pt_to_half_points(style.font_size_pt);
    let b = if style.bold { r#"<w:b/><w:bCs/>"# } else { "" };
    let i = if style.italic { "<w:i/>" } else { "" };

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

    // For non-default styles with 0 indent, explicitly set firstLine="0"
    // to prevent inheriting Normal's indent via basedOn.
    let indent_xml = if style.first_line_indent_chars > 0.0 {
        let twips = (style.first_line_indent_chars * style.font_size_pt * 20.0) as i64;
        format!(r#"<w:ind w:firstLine="{twips}"/>"#)
    } else if style.hanging_indent_chars > 0.0 {
        let twips = (style.hanging_indent_chars * style.font_size_pt * 20.0) as i64;
        format!(r#"<w:ind w:left="{twips}" w:hanging="{twips}"/>"#)
    } else if !is_default && based_on.is_some() {
        r#"<w:ind w:firstLine="0"/>"#.to_string()
    } else {
        String::new()
    };

    let keep_next_xml = if keep_next { "<w:keepNext/>" } else { "" };
    let page_break_before_xml = if style.page_break_before { "<w:pageBreakBefore/>" } else { "" };

    format!(
        r#"
<w:style w:type="paragraph" w:styleId="{style_id}"{default_attr}>
    <w:name w:val="{style_name}"/>
{based_on_xml}    <w:pPr>
        {keep_next_xml}
        {page_break_before_xml}
        <w:jc w:val="{align}"/>
        <w:spacing {spacing}/>
        {indent_xml}
    </w:pPr>
    <w:rPr>
        <w:rFonts w:ascii="{font_ascii}" w:eastAsia="{font_east}" w:hAnsi="{font_ascii}"/>
        <w:sz w:val="{sz}"/>
        <w:szCs w:val="{sz}"/>
        {b}
        {i}
    </w:rPr>
</w:style>"#
    )
}

pub fn settings_xml() -> String {
    format!(r#"{XML_HEADER}
<w:settings xmlns:w="{W_NS}">
    <w:defaultTabStop w:val="420"/>
    <w:compat>
        <w:compatSetting w:name="compatibilityMode" w:uri="http://schemas.microsoft.com/office/word" w:val="15"/>
    </w:compat>
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

/// Build section properties from a SectionPolicy.
/// Used for non-final sections (embedded in paragraph pPr) and can also
/// serve as the final body-level sectPr.
pub fn section_properties_from_policy(
    policy: &SectionPolicy,
    page: &PageStyle,
    footer_rid: &str,
    header_rid: Option<&str>,
) -> String {
    let w = cm_to_emu(page.page_width_cm);
    let h = cm_to_emu(page.page_height_cm);
    let mt = cm_to_emu(page.margin_top_cm);
    let mb = cm_to_emu(page.margin_bottom_cm);
    let ml = cm_to_emu(page.margin_left_cm);
    let mr = cm_to_emu(page.margin_right_cm);
    let hd = cm_to_emu(page.header_distance_cm);
    let fd = cm_to_emu(page.footer_distance_cm);

    let type_xml = match policy.start_type.as_str() {
        "next_page" => r#"<w:type w:val="nextPage"/>"#,
        "odd_page" => r#"<w:type w:val="oddPage"/>"#,
        "even_page" => r#"<w:type w:val="evenPage"/>"#,
        "continuous" => r#"<w:type w:val="continuous"/>"#,
        _ => "",
    };

    let fmt = match policy.page_number_format.as_str() {
        "roman_lower" => "lowerRoman",
        "roman_upper" => "upperRoman",
        "decimal" => "decimal",
        "none" => "none",
        _ => "decimal",
    };

    let mut pg_num_parts = vec![format!(r#"w:fmt="{fmt}""#)];
    if let Some(start) = policy.page_number_start {
        pg_num_parts.push(format!(r#"w:start="{start}""#));
    }
    let pg_num = format!(r#"<w:pgNumType {}/>"#, pg_num_parts.join(" "));

    let footer_ref = if policy.suppress_page_number || policy.footer_policy == "none" {
        String::new()
    } else {
        format!(r#"<w:footerReference w:type="default" w:id="{footer_rid}"/>"#)
    };

    let header_ref = match header_rid {
        Some(rid) if policy.header_text.is_some() => {
            format!(r#"<w:headerReference w:type="default" w:id="{rid}"/>"#)
        }
        _ => String::new(),
    };

    format!(
        r#"<w:sectPr>
    {type_xml}
    <w:pgSz w:w="{w}" w:h="{h}"/>
    <w:pgMar w:top="{mt}" w:right="{mr}" w:bottom="{mb}" w:left="{ml}" w:header="{hd}" w:footer="{fd}" w:gutter="0"/>
    {pg_num}
    {header_ref}
    {footer_ref}
</w:sectPr>"#
    )
}

/// Inject a <w:sectPr> into a paragraph's <w:pPr>.
/// Used at section boundaries: the last paragraph of a non-final section
/// carries the next section's properties in its pPr.
pub fn inject_section_break(para_xml: &str, sect_pr_xml: &str) -> String {
    // For paragraphs with pPr: insert sect_pr before </w:pPr>
    if let Some(pos) = para_xml.find("</w:pPr>") {
        let mut result = String::with_capacity(para_xml.len() + sect_pr_xml.len() + 10);
        result.push_str(&para_xml[..pos]);
        result.push_str(sect_pr_xml);
        result.push_str(&para_xml[pos..]);
        return result;
    }
    // For bare <w:p/> (empty paragraph): wrap with pPr containing sect_pr
    if para_xml.trim() == "<w:p/>" {
        return format!("<w:p><w:pPr>{}</w:pPr></w:p>", sect_pr_xml);
    }
    // Fallback: append after the opening <w:p> tag
    para_xml.replacen("<w:p>", &format!("<w:p><w:pPr>{}</w:pPr>", sect_pr_xml), 1)
}

/// Build the complete word/document.xml
pub fn document_xml(_page: &PageStyle, body_xml: &str, section_xml: &str) -> String {
    format!(
        r#"{XML_HEADER}
<w:document xmlns:w="{W_NS}" xmlns:r="{R_NS}" xmlns:mc="{MC_NS}" xmlns:wp="{WP_NS}" xmlns:a="{A_NS}" xmlns:pic="{PIC_NS}" mc:Ignorable="wp a pic">
<w:body>
{body_xml}
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

    let header_ref = if page.header_text.is_some() {
        format!(r#"<w:headerReference w:type="default" w:id="rIdHeader1"/>"#)
    } else {
        String::new()
    };

    format!(
        r#"<w:sectPr>
    <w:pgSz w:w="{w}" w:h="{h}"/>
    <w:pgMar w:top="{mt}" w:right="{mr}" w:bottom="{mb}" w:left="{ml}" w:header="{hd}" w:footer="{fd}" w:gutter="0"/>
    {pg_num}
    {header_ref}
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

/// Build a <w:p> element that references a named style via w:pStyle.
/// Only emits inline overrides for properties that differ from the style definition.
/// When keep_lines is true, adds <w:keepLines/> to keep multi-line content together.
pub fn paragraph_xml_with_style(text: &str, style_id: &str, style: &ParagraphStyle, template_body: &ParagraphStyle, keep_lines: bool) -> String {
    let escaped_text = escape_xml(text);

    // Always include pPr with style reference
    let mut ppr_parts = format!(r#"<w:pStyle w:val="{style_id}"/>"#);

    if keep_lines {
        ppr_parts.push_str("<w:keepLines/>");
    }

    // Only add inline overrides for properties that differ from body default
    // (since styles inherit from Normal which is based on body)
    if style.alignment != template_body.alignment {
        let align = match style.alignment.as_str() {
            "center" => "center",
            "right" => "right",
            "justify" => "both",
            _ => "left",
        };
        ppr_parts.push_str(&format!(r#"<w:jc w:val="{align}"/>"#));
    }

    // Only add spacing if different from body defaults
    let needs_spacing = (style.space_before_pt - template_body.space_before_pt).abs() > 0.5
        || (style.space_after_pt - template_body.space_after_pt).abs() > 0.5
        || style.line_spacing_multiple != template_body.line_spacing_multiple
        || style.line_spacing_pt != template_body.line_spacing_pt;
    if needs_spacing {
        let mut sp = Vec::new();
        sp.push(format!("w:before=\"{}\"", pt_to_twips(style.space_before_pt)));
        sp.push(format!("w:after=\"{}\"", pt_to_twips(style.space_after_pt)));
        if let Some(multiple) = style.line_spacing_multiple {
            let line_val = (multiple * 240.0).round() as i64;
            sp.push(format!("w:line=\"{line_val}\""));
            sp.push("w:lineRule=\"auto\"".to_string());
        } else if let Some(exact_pt) = style.line_spacing_pt {
            let line_val = pt_to_twips(exact_pt);
            sp.push(format!("w:line=\"{line_val}\""));
            sp.push("w:lineRule=\"exact\"".to_string());
        }
        ppr_parts.push_str(&format!(r#"<w:spacing {}/>"#, sp.join(" ")));
    }

    // Only add indent if style has non-zero indent
    if style.first_line_indent_chars > 0.0 {
        let twips = (style.first_line_indent_chars * style.font_size_pt * 20.0) as i64;
        ppr_parts.push_str(&format!(r#"<w:ind w:firstLine="{twips}"/>"#));
    } else if style.hanging_indent_chars > 0.0 {
        let twips = (style.hanging_indent_chars * style.font_size_pt * 20.0) as i64;
        ppr_parts.push_str(&format!(r#"<w:ind w:left="{twips}" w:hanging="{twips}"/>"#));
    }

    // Run properties: only add inline rPr if bold/italic differs from style definition
    // The style definition already has font/size/bold/italic, so we only need overrides
    let mut rpr_parts = String::new();
    if style.bold != template_body.bold || style.italic != template_body.italic {
        let b = if style.bold { r#"<w:b/><w:bCs/>"# } else { "" };
        let i = if style.italic { "<w:i/>" } else { "" };
        rpr_parts = format!("<w:rPr>{b}{i}</w:rPr>");
    }

    format!(
        r#"<w:p>
    <w:pPr>{ppr_parts}</w:pPr>
    <w:r>{rpr_parts}<w:t xml:space="preserve">{escaped_text}</w:t></w:r>
</w:p>"#
    )
}

/// Build a complete table with three-line borders.
/// When `include_caption` is false, the caption paragraph is skipped
/// (the caller has it in the paragraph stream already).
pub fn three_line_table_xml(
    table: &ExtractedTable,
    table_style: &TableStyle,
    caption_style: &ParagraphStyle,
    col_widths_twips: &[i64],
    include_caption: bool,
) -> String {
    let mut xml = String::new();

    if include_caption {
        if let Some(ref caption) = table.caption {
            xml.push_str(&paragraph_xml(caption, caption_style));
        }
    }

    if table.rows.is_empty() { return xml; }

    let col_count = table.col_count.max(1);

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

    for ci in 0..col_count {
        let cw = if ci < col_widths_twips.len() { col_widths_twips[ci] } else { col_widths_twips.last().copied().unwrap_or(4000) };
        xml.push_str(&format!(r#"<w:gridCol w:w="{}"/>"#, cw));
    }
    xml.push_str("</w:tblGrid>\n");

    for (row_idx, row) in table.rows.iter().enumerate() {
        xml.push_str("<w:tr>\n");
        xml.push_str("    <w:trPr><w:cantSplit/></w:trPr>\n");

        for (ci, cell_text) in row.iter().enumerate() {
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
            let cell_w = if ci < col_widths_twips.len() { col_widths_twips[ci] } else { col_widths_twips.last().copied().unwrap_or(4000) };

            xml.push_str(&format!(
                r#"    <w:tc>
        <w:tcPr>
            <w:tcW w:w="{cell_w}" w:type="dxa"/>
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

/// Header with configurable text
pub fn header_xml(text: &str) -> String {
    let escaped = escape_xml(text);
    format!(
        r#"{XML_HEADER}
<w:hdr xmlns:w="{W_NS}">
    <w:p>
        <w:pPr><w:jc w:val="center"/></w:pPr>
        <w:r>
            <w:rPr><w:sz w:val="18"/><w:rFonts w:ascii="Times New Roman" w:hAnsi="Times New Roman"/></w:rPr>
            <w:t xml:space="preserve">{escaped}</w:t>
        </w:r>
    </w:p>
</w:hdr>"#
    )
}

pub fn header_rels_xml() -> String {
    format!(
        r#"{XML_HEADER}
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="{R_NS}/styles" Target="../styles.xml"/>
</Relationships>"#
    )
}

/// TOC title paragraph — centered, bold, SimHei 16pt
pub fn toc_title_paragraph_xml(title: &str) -> String {
    let escaped = escape_xml(title);
    let sz = pt_to_half_points(16.0);
    format!(
        r#"<w:p>
    <w:pPr>
        <w:keepNext/>
        <w:jc w:val="center"/>
        <w:spacing w:before="240" w:after="240"/>
    </w:pPr>
    <w:r>
        <w:rPr>
            <w:rFonts w:ascii="Times New Roman" w:eastAsia="SimHei" w:hAnsi="Times New Roman"/>
            <w:b/><w:bCs/>
            <w:sz w:val="{sz}"/>
            <w:szCs w:val="{sz}"/>
        </w:rPr>
        <w:t xml:space="preserve">{escaped}</w:t>
    </w:r>
</w:p>"#
    )
}

/// TOC field code paragraph — generates a Word-standard TOC field
/// that Word will auto-update on open or right-click "Update Field"
pub fn toc_field_xml() -> String {
    format!(
        r#"<w:p>
    <w:pPr><w:pStyle w:val="Normal"/></w:pPr>
    <w:r><w:fldChar w:fldCharType="begin"/></w:r>
    <w:r><w:instrText xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText></w:r>
    <w:r><w:fldChar w:fldCharType="separate"/></w:r>
    <w:r><w:t>（请在 Word 中右键更新目录）</w:t></w:r>
    <w:r><w:fldChar w:fldCharType="end"/></w:r>
</w:p>"#
    )
}

/// Build a formula paragraph with centered formula text and right-aligned number.
/// Uses a right tab stop at `tab_stop_twips` to position the number at the right margin.
pub fn formula_paragraph_xml(
    formula_text: &str,
    number_text: &str,
    tab_stop_twips: i64,
    body_style: &ParagraphStyle,
) -> String {
    let escaped_formula = escape_xml(formula_text);
    let escaped_number = escape_xml(number_text);
    let sz = pt_to_half_points(body_style.font_size_pt);
    let font_east = &body_style.font_name;
    let font_ascii = if body_style.font_name.contains("Sim") { "Times New Roman" } else { &body_style.font_name };

    // Spacing: 6pt before and after for compact formula layout
    let spacing = format!("w:before=\"120\" w:after=\"120\"");

    format!(
        r#"<w:p>
    <w:pPr>
        <w:jc w:val="center"/>
        <w:tabs><w:tab w:val="right" w:pos="{tab_stop_twips}"/></w:tabs>
        <w:spacing {spacing}/>
    </w:pPr>
    <w:r>
        <w:rPr><w:rFonts w:ascii="{font_ascii}" w:eastAsia="{font_east}" w:hAnsi="{font_ascii}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>
        <w:t xml:space="preserve">{escaped_formula}</w:t>
    </w:r>
    <w:r>
        <w:rPr><w:rFonts w:ascii="{font_ascii}" w:eastAsia="{font_east}" w:hAnsi="{font_ascii}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>
        <w:tab/>
    </w:r>
    <w:r>
        <w:rPr><w:rFonts w:ascii="{font_ascii}" w:eastAsia="{font_east}" w:hAnsi="{font_ascii}"/><w:sz w:val="{sz}"/><w:szCs w:val="{sz}"/></w:rPr>
        <w:t xml:space="preserve">{escaped_number}</w:t>
    </w:r>
</w:p>"#
    )
}

fn escape_xml(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
        .replace('\'', "&apos;")
}

/// Build an inline drawing element for embedding an image in a paragraph.
/// Uses the standard OOXML structure: w:drawing > wp:inline > a:graphic > a:graphicData > pic:pic
pub fn drawing_inline_xml(r_id: &str, width_emu: i64, height_emu: i64, description: &str) -> String {
    let desc = escape_xml(description);
    // Extract numeric portion of r_id for docPr id (must be unique integer)
    let r_id_num: u64 = r_id.chars()
        .filter(|c| c.is_ascii_digit())
        .collect::<String>()
        .parse()
        .unwrap_or(0);
    format!(
        r#"<w:drawing>
    <wp:inline distT="0" distB="0" distL="0" distR="0">
        <wp:extent cx="{width_emu}" cy="{height_emu}"/>
        <wp:docPr id="{r_id_num}" name="{desc}"/>
        <a:graphic>
            <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                <pic:pic>
                    <pic:nvPicPr>
                        <pic:cNvPr id="0" name="{desc}"/>
                        <pic:cNvPicPr/>
                    </pic:nvPicPr>
                    <pic:blipFill>
                        <a:blip r:embed="{r_id}"/>
                        <a:stretch><a:fillRect/></a:stretch>
                    </pic:blipFill>
                    <pic:spPr>
                        <a:xfrm>
                            <a:off x="0" y="0"/>
                            <a:ext cx="{width_emu}" cy="{height_emu}"/>
                        </a:xfrm>
                        <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                    </pic:spPr>
                </pic:pic>
            </a:graphicData>
        </a:graphic>
    </wp:inline>
</w:drawing>"#,
    )
}

/// Build a paragraph containing an inline drawing (image) with alignment and keepNext.
pub fn drawing_paragraph_xml(r_id: &str, width_emu: i64, height_emu: i64, description: &str, align: &str) -> String {
    let drawing = drawing_inline_xml(r_id, width_emu, height_emu, description);
    format!(
        r#"<w:p>
    <w:pPr><w:keepNext/><w:jc w:val="{align}"/></w:pPr>
    <w:r>
        {drawing}
    </w:r>
</w:p>"#
    )
}
