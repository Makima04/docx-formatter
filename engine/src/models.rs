/// Shared data models — the contract between Rust engine and Python layer.
///
/// These structs are serialized to JSON and passed across the PyO3 boundary.
/// Python deserializes them into Pydantic models for the API layer.
use serde::{Deserialize, Serialize};

// ── Paragraph types ─────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ParagraphType {
    Heading1,
    Heading2,
    Heading3,
    Body,
    BodyIndent,
    CaptionFigure,
    CaptionTable,
    Reference,
    Quote,
    Abstract,
    Keywords,
    Code,
    ListItem,
    Toc,
    Unknown,
}

impl ParagraphType {
    pub fn from_str(s: &str) -> Self {
        match s {
            "heading1" => Self::Heading1,
            "heading2" => Self::Heading2,
            "heading3" => Self::Heading3,
            "body" => Self::Body,
            "body_indent" => Self::BodyIndent,
            "caption_figure" => Self::CaptionFigure,
            "caption_table" => Self::CaptionTable,
            "reference" => Self::Reference,
            "quote" => Self::Quote,
            "abstract" => Self::Abstract,
            "keywords" => Self::Keywords,
            "code" => Self::Code,
            "list_item" => Self::ListItem,
            "toc" => Self::Toc,
            _ => Self::Unknown,
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Heading1 => "heading1",
            Self::Heading2 => "heading2",
            Self::Heading3 => "heading3",
            Self::Body => "body",
            Self::BodyIndent => "body_indent",
            Self::CaptionFigure => "caption_figure",
            Self::CaptionTable => "caption_table",
            Self::Reference => "reference",
            Self::Quote => "quote",
            Self::Abstract => "abstract",
            Self::Keywords => "keywords",
            Self::Code => "code",
            Self::ListItem => "list_item",
            Self::Toc => "toc",
            Self::Unknown => "unknown",
        }
    }
}

// ── Extracted data structures ───────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedParagraph {
    pub index: usize,
    pub text: String,
    pub font_size_pt: Option<f64>,
    pub font_name: Option<String>,
    pub bold: bool,
    pub italic: bool,
    pub alignment: Option<String>,
    pub space_before_pt: Option<f64>,
    pub space_after_pt: Option<f64>,
    pub line_spacing: Option<f64>,
    pub is_first_line_indent: bool,
    pub char_count: usize,
    pub paragraph_type: ParagraphType,
    pub confidence: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedTable {
    pub index: usize,
    pub rows: Vec<Vec<String>>,
    pub row_count: usize,
    pub col_count: usize,
    pub has_merged_cells: bool,
    pub caption: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedImage {
    pub index: usize,
    pub media_path: String,
    pub content_type: String,
    pub width_px: Option<u32>,
    pub height_px: Option<u32>,
    pub caption: Option<String>,
    #[serde(skip)]
    pub blob: Option<Vec<u8>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedDocument {
    pub paragraphs: Vec<ExtractedParagraph>,
    pub tables: Vec<ExtractedTable>,
    pub images: Vec<ExtractedImage>,
    pub total_pages_est: usize,
}

// ── Template configuration ──────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParagraphStyle {
    pub font_name: String,
    pub font_size_pt: f64,
    pub bold: bool,
    pub italic: bool,
    pub alignment: String,
    pub first_line_indent_chars: f64,
    pub hanging_indent_chars: f64,
    pub space_before_pt: f64,
    pub space_after_pt: f64,
    pub line_spacing_pt: Option<f64>,
    pub line_spacing_multiple: Option<f64>,
    pub line_spacing_rule: String,
}

impl Default for ParagraphStyle {
    fn default() -> Self {
        Self {
            font_name: "SimSun".to_string(),
            font_size_pt: 12.0,
            bold: false,
            italic: false,
            alignment: "justify".to_string(),
            first_line_indent_chars: 0.0,
            hanging_indent_chars: 0.0,
            space_before_pt: 0.0,
            space_after_pt: 0.0,
            line_spacing_pt: None,
            line_spacing_multiple: Some(1.5),
            line_spacing_rule: "multiple".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PageStyle {
    pub page_width_cm: f64,
    pub page_height_cm: f64,
    pub margin_top_cm: f64,
    pub margin_bottom_cm: f64,
    pub margin_left_cm: f64,
    pub margin_right_cm: f64,
    pub header_distance_cm: f64,
    pub footer_distance_cm: f64,
    pub page_number_format: String,
    pub page_number_start: i32,
    pub header_text: Option<String>,
    pub footer_text: Option<String>,
}

impl Default for PageStyle {
    fn default() -> Self {
        Self {
            page_width_cm: 21.0,
            page_height_cm: 29.7,
            margin_top_cm: 2.54,
            margin_bottom_cm: 2.54,
            margin_left_cm: 3.17,
            margin_right_cm: 3.17,
            header_distance_cm: 1.5,
            footer_distance_cm: 1.75,
            page_number_format: "decimal".to_string(),
            page_number_start: 1,
            header_text: None,
            footer_text: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TableStyle {
    pub top_rule_width_pt: f64,
    pub mid_rule_width_pt: f64,
    pub bottom_rule_width_pt: f64,
    pub header_font_name: String,
    pub header_font_size_pt: f64,
    pub header_bold: bool,
    pub cell_font_name: String,
    pub cell_font_size_pt: f64,
    pub cell_align: String,
    pub caption_position: String,
    pub caption_font_name: String,
    pub caption_font_size_pt: f64,
}

impl Default for TableStyle {
    fn default() -> Self {
        Self {
            top_rule_width_pt: 1.5,
            mid_rule_width_pt: 0.75,
            bottom_rule_width_pt: 1.5,
            header_font_name: "SimHei".to_string(),
            header_font_size_pt: 10.5,
            header_bold: true,
            cell_font_name: "SimSun".to_string(),
            cell_font_size_pt: 10.5,
            cell_align: "center".to_string(),
            caption_position: "above".to_string(),
            caption_font_name: "SimHei".to_string(),
            caption_font_size_pt: 10.5,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FigureStyle {
    pub max_width_cm: f64,
    pub align: String,
    pub caption_position: String,
    pub caption_font_name: String,
    pub caption_font_size_pt: f64,
}

impl Default for FigureStyle {
    fn default() -> Self {
        Self {
            max_width_cm: 15.0,
            align: "center".to_string(),
            caption_position: "below".to_string(),
            caption_font_name: "SimHei".to_string(),
            caption_font_size_pt: 10.5,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReferenceStyle {
    pub font_name: String,
    pub font_size_pt: f64,
    pub hanging_indent_chars: f64,
    pub spacing_between: f64,
}

impl Default for ReferenceStyle {
    fn default() -> Self {
        Self {
            font_name: "SimSun".to_string(),
            font_size_pt: 10.5,
            hanging_indent_chars: 2.0,
            spacing_between: 3.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TemplateConfig {
    pub name: String,
    pub description: String,
    pub page: PageStyle,
    pub heading1: ParagraphStyle,
    pub heading2: ParagraphStyle,
    pub heading3: ParagraphStyle,
    pub body: ParagraphStyle,
    pub body_indent: ParagraphStyle,
    pub abstract_style: ParagraphStyle,
    pub keywords: ParagraphStyle,
    pub caption_figure: ParagraphStyle,
    pub caption_table: ParagraphStyle,
    pub reference: ParagraphStyle,
    pub quote: ParagraphStyle,
    pub list_item: ParagraphStyle,
    pub table: TableStyle,
    pub figure: FigureStyle,
    pub references: ReferenceStyle,
}

impl Default for TemplateConfig {
    fn default() -> Self {
        Self {
            name: "default".to_string(),
            description: "默认学术论文格式".to_string(),
            page: PageStyle::default(),
            heading1: ParagraphStyle {
                font_name: "SimHei".to_string(),
                font_size_pt: 16.0,
                bold: true,
                alignment: "center".to_string(),
                space_before_pt: 24.0,
                space_after_pt: 18.0,
                line_spacing_multiple: Some(1.5),
                ..Default::default()
            },
            heading2: ParagraphStyle {
                font_name: "SimHei".to_string(),
                font_size_pt: 14.0,
                bold: true,
                alignment: "left".to_string(),
                space_before_pt: 12.0,
                space_after_pt: 6.0,
                line_spacing_multiple: Some(1.5),
                ..Default::default()
            },
            heading3: ParagraphStyle {
                font_name: "SimHei".to_string(),
                font_size_pt: 12.0,
                bold: true,
                alignment: "left".to_string(),
                space_before_pt: 6.0,
                space_after_pt: 6.0,
                line_spacing_multiple: Some(1.5),
                ..Default::default()
            },
            body: ParagraphStyle {
                font_name: "SimSun".to_string(),
                font_size_pt: 12.0,
                alignment: "justify".to_string(),
                first_line_indent_chars: 2.0,
                line_spacing_multiple: Some(1.5),
                ..Default::default()
            },
            body_indent: ParagraphStyle::default(),
            abstract_style: ParagraphStyle {
                font_name: "SimSun".to_string(),
                font_size_pt: 10.5,
                alignment: "justify".to_string(),
                first_line_indent_chars: 2.0,
                line_spacing_multiple: Some(1.25),
                ..Default::default()
            },
            keywords: ParagraphStyle {
                font_name: "SimHei".to_string(),
                font_size_pt: 10.5,
                alignment: "left".to_string(),
                ..Default::default()
            },
            caption_figure: ParagraphStyle {
                font_name: "SimHei".to_string(),
                font_size_pt: 10.5,
                alignment: "center".to_string(),
                space_before_pt: 6.0,
                space_after_pt: 6.0,
                ..Default::default()
            },
            caption_table: ParagraphStyle {
                font_name: "SimHei".to_string(),
                font_size_pt: 10.5,
                alignment: "center".to_string(),
                space_before_pt: 6.0,
                space_after_pt: 6.0,
                ..Default::default()
            },
            reference: ParagraphStyle {
                font_name: "SimSun".to_string(),
                font_size_pt: 10.5,
                alignment: "justify".to_string(),
                hanging_indent_chars: 2.0,
                ..Default::default()
            },
            quote: ParagraphStyle {
                font_name: "KaiTi".to_string(),
                font_size_pt: 10.5,
                alignment: "justify".to_string(),
                first_line_indent_chars: 2.0,
                ..Default::default()
            },
            list_item: ParagraphStyle {
                font_name: "SimSun".to_string(),
                font_size_pt: 12.0,
                alignment: "left".to_string(),
                ..Default::default()
            },
            table: TableStyle::default(),
            figure: FigureStyle::default(),
            references: ReferenceStyle::default(),
        }
    }
}
