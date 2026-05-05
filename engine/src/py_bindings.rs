/// PyO3 bindings — exposes Rust parse/assemble to Python as native extension.
use pyo3::prelude::*;

use crate::models::*;
use crate::parser;
use crate::assembler;

#[pyfunction]
fn parse_docx(path: String) -> PyResult<String> {
    let doc = parser::parse_docx(&path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;
    serde_json::to_string(&doc)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON error: {e}")))
}

#[pyfunction]
fn assemble_docx(doc_json: String, template_json: String, output_path: String) -> PyResult<String> {
    let doc: ExtractedDocument = serde_json::from_str(&doc_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid doc JSON: {e}")))?;
    let template: TemplateConfig = serde_json::from_str(&template_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid template JSON: {e}")))?;

    assembler::assemble_docx(&doc, &template, &output_path)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(e))?;

    Ok(output_path)
}

#[pyfunction]
fn update_classifications(doc_json: String, updates_json: String) -> PyResult<String> {
    let mut doc: ExtractedDocument = serde_json::from_str(&doc_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid doc JSON: {e}")))?;

    #[derive(serde::Deserialize)]
    struct ClassUpdate {
        index: usize,
        #[serde(rename = "type")]
        ptype: String,
        confidence: f64,
    }

    let updates: Vec<ClassUpdate> = serde_json::from_str(&updates_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid updates JSON: {e}")))?;

    for update in updates {
        if update.index < doc.paragraphs.len() {
            doc.paragraphs[update.index].paragraph_type = ParagraphType::from_str(&update.ptype);
            doc.paragraphs[update.index].confidence = update.confidence;
        }
    }

    serde_json::to_string(&doc)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON error: {e}")))
}

#[pyfunction]
fn default_template_json() -> PyResult<String> {
    let template = TemplateConfig::default();
    serde_json::to_string(&template)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON error: {e}")))
}

#[pyfunction]
fn set_image_blobs(doc_json: String, blobs_json: String) -> PyResult<String> {
    let mut doc: ExtractedDocument = serde_json::from_str(&doc_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid doc JSON: {e}")))?;

    #[derive(serde::Deserialize)]
    struct ImageBlob {
        index: usize,
        blob_base64: String,
    }

    let blobs: Vec<ImageBlob> = serde_json::from_str(&blobs_json)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(format!("Invalid blobs JSON: {e}")))?;

    for b in blobs {
        if b.index < doc.images.len() {
            use base64::Engine;
            if let Ok(bytes) = base64::engine::general_purpose::STANDARD.decode(&b.blob_base64) {
                doc.images[b.index].blob = Some(bytes);
            }
        }
    }

    serde_json::to_string(&doc)
        .map_err(|e| pyo3::exceptions::PyRuntimeError::new_err(format!("JSON error: {e}")))
}

#[pymodule]
fn docx_fmt_core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(parse_docx, m)?)?;
    m.add_function(wrap_pyfunction!(assemble_docx, m)?)?;
    m.add_function(wrap_pyfunction!(update_classifications, m)?)?;
    m.add_function(wrap_pyfunction!(default_template_json, m)?)?;
    m.add_function(wrap_pyfunction!(set_image_blobs, m)?)?;
    Ok(())
}
