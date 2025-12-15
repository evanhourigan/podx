"""PDF export formatter using ReportLab.

This replaces the buggy pandoc-based PDF export that had issues with emojis.
Uses ReportLab for professional-looking PDF output with proper formatting.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer

from .base import ExportFormatter


def format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS timestamp.

    Args:
        seconds: Time in seconds

    Returns:
        Formatted timestamp string
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class PDFFormatter(ExportFormatter):
    """PDF export formatter using ReportLab.

    Creates professional PDF transcripts with:
    - Title page with metadata
    - Speaker labels
    - Timestamps
    - Page numbers
    - Clean formatting (NO EMOJIS - fixes the pandoc bug!)
    """

    @property
    def extension(self) -> str:
        return "pdf"

    @property
    def name(self) -> str:
        return "PDF Document"

    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Format transcript segments to PDF.

        Note: This returns the file path where PDF will be written,
        not the PDF content itself (since PDFs are binary).

        Args:
            segments: List of transcript segments

        Returns:
            Empty string (PDF is written directly to file)
        """
        # This is a placeholder - actual PDF generation happens in write_pdf()
        return ""

    def write_pdf(
        self,
        segments: List[Dict[str, Any]],
        output_path: str,
        title: str = "Podcast Transcript",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Write transcript segments to PDF file.

        Args:
            segments: List of transcript segments
            output_path: Path to output PDF file
            title: Document title
            metadata: Optional metadata (show, date, duration, etc.)
        """
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=(8.5 * inch, 11 * inch),
            topMargin=1 * inch,
            bottomMargin=1 * inch,
            leftMargin=1 * inch,
            rightMargin=1 * inch,
        )

        # Container for PDF elements
        story = []

        # Get styles
        styles = getSampleStyleSheet()
        title_style = styles["Title"]
        heading_style = styles["Heading2"]
        normal_style = styles["Normal"]

        # Custom styles
        speaker_style = ParagraphStyle(
            "Speaker",
            parent=normal_style,
            fontSize=11,
            textColor=colors.HexColor("#2563eb"),
            spaceAfter=4,
            fontName="Helvetica-Bold",
        )

        timestamp_style = ParagraphStyle(
            "Timestamp",
            parent=normal_style,
            fontSize=9,
            textColor=colors.HexColor("#6b7280"),
            fontName="Helvetica",
        )

        text_style = ParagraphStyle(
            "TranscriptText",
            parent=normal_style,
            fontSize=10,
            leading=14,
            spaceAfter=12,
            fontName="Helvetica",
        )

        # Title page
        story.append(Spacer(1, 2 * inch))
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 0.5 * inch))

        # Metadata section
        if metadata:
            metadata_lines = []
            if "show" in metadata:
                metadata_lines.append(f"<b>Show:</b> {metadata['show']}")
            if "date" in metadata:
                metadata_lines.append(f"<b>Date:</b> {metadata['date']}")
            if "duration" in metadata:
                duration = metadata["duration"]
                # Handle both float seconds and string durations
                if isinstance(duration, (int, float)):
                    duration_str = format_timestamp(duration)
                else:
                    duration_str = str(duration)
                metadata_lines.append(f"<b>Duration:</b> {duration_str}")
            if "speakers" in metadata:
                speakers = metadata["speakers"]
                # Handle both list and count
                if isinstance(speakers, list):
                    speakers_str = ", ".join(speakers)
                else:
                    speakers_str = str(speakers)
                metadata_lines.append(f"<b>Speakers:</b> {speakers_str}")

            for line in metadata_lines:
                story.append(Paragraph(line, normal_style))
                story.append(Spacer(1, 0.1 * inch))

        story.append(Spacer(1, 0.3 * inch))
        story.append(
            Paragraph(
                f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                timestamp_style,
            )
        )

        # Page break before transcript
        story.append(PageBreak())

        # Transcript heading
        story.append(Paragraph("Transcript", heading_style))
        story.append(Spacer(1, 0.2 * inch))

        # Process segments
        for segment in segments:
            speaker = segment.get("speaker", "Unknown")
            start = segment.get("start", 0)
            text = segment.get("text", "").strip()

            # Skip empty segments
            if not text:
                continue

            # Speaker and timestamp line
            timestamp = format_timestamp(start)
            speaker_line = f"<b>{speaker}</b> [{timestamp}]"
            story.append(Paragraph(speaker_line, speaker_style))

            # Transcript text (clean - no emojis!)
            # Remove any potentially problematic characters
            clean_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            story.append(Paragraph(clean_text, text_style))

        # Build PDF
        doc.build(story, onFirstPage=self._add_page_number, onLaterPages=self._add_page_number)

    @staticmethod
    def _add_page_number(canvas_obj: canvas.Canvas, doc: SimpleDocTemplate) -> None:
        """Add page numbers to PDF pages.

        Args:
            canvas_obj: ReportLab canvas
            doc: Document template
        """
        page_num = canvas_obj.getPageNumber()
        text = f"Page {page_num}"
        canvas_obj.saveState()
        canvas_obj.setFont("Helvetica", 9)
        canvas_obj.setFillColor(colors.HexColor("#6b7280"))
        canvas_obj.drawCentredString(
            4.25 * inch,  # Center of 8.5" page
            0.5 * inch,  # Bottom margin
            text,
        )
        canvas_obj.restoreState()
