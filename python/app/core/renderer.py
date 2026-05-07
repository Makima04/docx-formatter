"""PDF renderer — LibreOffice headless conversion + pdfplumber layout extraction."""

from __future__ import annotations
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class PDFRenderer:
    def __init__(self, libreoffice_path: str = "libreoffice", dpi: int = 150):
        self.lo_path = libreoffice_path
        self.dpi = dpi

    def is_available(self) -> bool:
        return shutil.which(self.lo_path) is not None

    def render_to_pdf(self, docx_path: str, output_dir: str) -> Optional[str]:
        """Convert .docx to PDF via LibreOffice headless. Returns PDF path or None."""
        if not self.is_available():
            logger.warning("LibreOffice not available, skipping PDF rendering")
            return None
        try:
            subprocess.run(
                [self.lo_path, "--headless", "--convert-to", "pdf",
                 "--outdir", output_dir, docx_path],
                check=True, capture_output=True, timeout=120,
            )
            pdf_name = Path(docx_path).stem + ".pdf"
            pdf_path = Path(output_dir) / pdf_name
            return str(pdf_path) if pdf_path.exists() else None
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.error(f"PDF rendering failed: {e}")
            return None

    def extract_layout(self, pdf_path: str) -> dict:
        """Extract layout coordinates from PDF using pdfplumber.

        Returns dict with structure:
        { pages: [{ width, height, texts: [{x0,y0,x1,y1,text}], tables: [{bbox, rows}], images: [{bbox}] }] }
        """
        import pdfplumber
        pages_data = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                texts = []
                for char in (page.chars or []):
                    texts.append({
                        "x0": char["x0"], "y0": char["top"],
                        "x1": char["x1"], "y1": char["bottom"],
                        "text": char["text"],
                        "size": char.get("size", 0),
                        "fontname": char.get("fontname", ""),
                    })
                tables = []
                for table in (page.find_tables() or []):
                    tables.append({
                        "bbox": list(table.bbox),
                        "rows": table.extract(),
                    })
                images = []
                for img in (page.images or []):
                    images.append({
                        "x0": img["x0"], "y0": img["top"],
                        "x1": img["x1"], "y1": img["bottom"],
                    })
                pages_data.append({
                    "width": page.width,
                    "height": page.height,
                    "texts": texts,
                    "tables": tables,
                    "images": images,
                })
        return {"pages": pages_data}
