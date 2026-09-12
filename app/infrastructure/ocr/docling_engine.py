"""
Concrete implementation of OCREngineInterface, backed by IBM Docling.
Optimized with an ultra-fast native parser for digital PDFs (~0.8s) and a
lazy-loaded, ONNX-accelerated OCR fallback for scanned documents and images.
"""

import logging
from typing import Optional

from app.domain.interfaces.ocr_engine import OCREngineInterface
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.pipeline.native_pdf_pipeline import NativePdfPipeline

logger = logging.getLogger(__name__)


class DoclingEngine(OCREngineInterface):
    def __init__(self) -> None:
        # Fast model-free converter for digital PDFs (completes in < 1 second)
        self._native_converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_cls=NativePdfPipeline)
            }
        )
        self._ocr_converter: Optional[DocumentConverter] = None

    @property
    def ocr_converter(self) -> DocumentConverter:
        """Lazy-loaded full OCR converter for scanned PDFs and image files."""
        if self._ocr_converter is None:
            opts = PdfPipelineOptions()
            opts.do_ocr = True
            opts.table_structure_options.mode = TableFormerMode.FAST
            opts.ocr_options.scale = 2.0
            opts.accelerator_options.num_threads = 4

            self._ocr_converter = DocumentConverter(
                format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=opts)}
            )
        return self._ocr_converter

    def extract(self, file_path: str) -> str:
        file_lower = file_path.lower()
        if file_lower.endswith(".pdf"):
            try:
                # Fast path: Native text extraction without heavy deep-learning overhead
                result = self._native_converter.convert(file_path)
                md = result.document.export_to_markdown()
                if md and len(md.strip()) >= 50:
                    logger.info(
                        "Fast native extraction succeeded for %s (%d chars)",
                        file_path,
                        len(md),
                    )
                    return md
                logger.info(
                    "Native extraction produced little text (%d chars). Falling back to OCR pipeline...",
                    len(md) if md else 0,
                )
            except Exception as exc:
                logger.warning(
                    "Native extraction failed for %s (%s). Falling back to OCR pipeline...",
                    file_path,
                    exc,
                )

        # Fallback path for scanned PDFs or images
        result = self.ocr_converter.convert(file_path)
        return result.document.export_to_markdown()
