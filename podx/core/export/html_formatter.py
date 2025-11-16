"""HTML export formatter with interactive features.

Creates self-contained HTML files with:
- Full-text search
- Speaker highlighting
- Timestamp navigation
- Dark/light theme toggle
- Responsive design
"""

from typing import Any, Dict, List

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


class HTMLFormatter(ExportFormatter):
    """Interactive HTML export formatter.

    Creates a self-contained HTML file with JavaScript for:
    - Real-time search filtering
    - Speaker color coding
    - Timestamp-based navigation
    - Dark/light theme toggle
    - Copy-to-clipboard
    """

    @property
    def extension(self) -> str:
        return "html"

    @property
    def name(self) -> str:
        return "Interactive HTML"

    def format(self, segments: List[Dict[str, Any]]) -> str:
        """Format transcript segments to interactive HTML.

        Args:
            segments: List of transcript segments

        Returns:
            Complete HTML document as string
        """
        # Extract unique speakers for color coding
        speakers = list(set(seg.get("speaker", "Unknown") for seg in segments))
        speaker_colors = self._generate_speaker_colors(speakers)

        # Build HTML
        html_parts = []

        # HTML header
        html_parts.append(self._get_html_header())

        # CSS styles
        html_parts.append(self._get_css_styles(speaker_colors))

        # Body start
        html_parts.append("</head>\n<body>\n")

        # Header with controls
        html_parts.append(self._get_page_header())

        # Search bar
        html_parts.append(self._get_search_bar())

        # Speaker legend
        if speakers:
            html_parts.append(self._get_speaker_legend(speakers, speaker_colors))

        # Transcript content
        html_parts.append('<div class="transcript-container">\n')

        for i, segment in enumerate(segments):
            speaker = segment.get("speaker", "Unknown")
            start = segment.get("start", 0)
            text = segment.get("text", "").strip()

            if not text:
                continue

            timestamp = format_timestamp(start)
            speaker_class = self._speaker_to_class(speaker)

            html_parts.append(
                f'<div class="segment" data-speaker="{speaker}" data-timestamp="{start}">\n'
            )
            html_parts.append(
                f'  <div class="segment-header">\n'
                f'    <span class="speaker {speaker_class}">{self._html_escape(speaker)}</span>\n'
                f'    <span class="timestamp" data-seconds="{start}">{timestamp}</span>\n'
                f"  </div>\n"
            )
            html_parts.append(
                f'  <div class="segment-text">{self._html_escape(text)}</div>\n'
            )
            html_parts.append("</div>\n")

        html_parts.append("</div>\n")

        # JavaScript
        html_parts.append(self._get_javascript())

        # Close body and html
        html_parts.append("</body>\n</html>")

        return "".join(html_parts)

    @staticmethod
    def _html_escape(text: str) -> str:
        """Escape HTML special characters.

        Args:
            text: Text to escape

        Returns:
            Escaped text safe for HTML
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&#39;")
        )

    @staticmethod
    def _speaker_to_class(speaker: str) -> str:
        """Convert speaker name to CSS class name.

        Args:
            speaker: Speaker name

        Returns:
            Valid CSS class name
        """
        return "speaker-" + speaker.lower().replace(" ", "-").replace("_", "-")

    @staticmethod
    def _generate_speaker_colors(speakers: List[str]) -> Dict[str, str]:
        """Generate distinct colors for each speaker.

        Args:
            speakers: List of speaker names

        Returns:
            Dictionary mapping speaker names to hex colors
        """
        # Predefined color palette for better contrast
        colors = [
            "#3b82f6",  # Blue
            "#10b981",  # Green
            "#f59e0b",  # Amber
            "#ef4444",  # Red
            "#8b5cf6",  # Purple
            "#ec4899",  # Pink
            "#06b6d4",  # Cyan
            "#f97316",  # Orange
        ]

        speaker_colors = {}
        for i, speaker in enumerate(sorted(speakers)):
            speaker_colors[speaker] = colors[i % len(colors)]

        return speaker_colors

    @staticmethod
    def _get_html_header() -> str:
        """Get HTML document header."""
        return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Podcast Transcript</title>
"""

    @staticmethod
    def _get_css_styles(speaker_colors: Dict[str, str]) -> str:
        """Get CSS styles including speaker colors.

        Args:
            speaker_colors: Speaker name to color mapping

        Returns:
            Complete CSS styles as string
        """
        # Generate speaker-specific color styles
        speaker_styles = []
        for speaker, color in speaker_colors.items():
            class_name = HTMLFormatter._speaker_to_class(speaker)
            speaker_styles.append(f"    .{class_name} {{ color: {color}; }}")

        speaker_css = "\n".join(speaker_styles)

        return f"""  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}

    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      color: #1f2937;
      background: #f9fafb;
      padding: 20px;
      transition: background 0.3s, color 0.3s;
    }}

    body.dark-mode {{
      background: #111827;
      color: #f3f4f6;
    }}

    .container {{
      max-width: 900px;
      margin: 0 auto;
    }}

    header {{
      background: white;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      margin-bottom: 24px;
    }}

    body.dark-mode header {{
      background: #1f2937;
    }}

    h1 {{
      font-size: 28px;
      margin-bottom: 8px;
    }}

    .controls {{
      display: flex;
      gap: 16px;
      margin-top: 16px;
      flex-wrap: wrap;
    }}

    .search-container {{
      flex: 1;
      min-width: 250px;
    }}

    #search-box {{
      width: 100%;
      padding: 10px 16px;
      font-size: 14px;
      border: 1px solid #d1d5db;
      border-radius: 6px;
      outline: none;
      transition: border-color 0.2s;
    }}

    #search-box:focus {{
      border-color: #3b82f6;
    }}

    body.dark-mode #search-box {{
      background: #374151;
      border-color: #4b5563;
      color: #f3f4f6;
    }}

    .theme-toggle {{
      padding: 10px 20px;
      background: #3b82f6;
      color: white;
      border: none;
      border-radius: 6px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
      transition: background 0.2s;
    }}

    .theme-toggle:hover {{
      background: #2563eb;
    }}

    .speaker-legend {{
      background: white;
      padding: 16px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      margin-bottom: 24px;
    }}

    body.dark-mode .speaker-legend {{
      background: #1f2937;
    }}

    .legend-title {{
      font-weight: 600;
      margin-bottom: 12px;
      font-size: 14px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }}

    .legend-items {{
      display: flex;
      flex-wrap: wrap;
      gap: 16px;
    }}

    .legend-item {{
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    .color-dot {{
      width: 12px;
      height: 12px;
      border-radius: 50%;
    }}

    .transcript-container {{
      background: white;
      padding: 24px;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }}

    body.dark-mode .transcript-container {{
      background: #1f2937;
    }}

    .segment {{
      margin-bottom: 24px;
      padding-bottom: 24px;
      border-bottom: 1px solid #e5e7eb;
    }}

    body.dark-mode .segment {{
      border-bottom-color: #374151;
    }}

    .segment:last-child {{
      border-bottom: none;
    }}

    .segment.hidden {{
      display: none;
    }}

    .segment-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
    }}

    .speaker {{
      font-weight: 600;
      font-size: 16px;
    }}

{speaker_css}

    .timestamp {{
      font-size: 13px;
      color: #6b7280;
      font-family: "SF Mono", Monaco, monospace;
    }}

    body.dark-mode .timestamp {{
      color: #9ca3af;
    }}

    .segment-text {{
      color: #374151;
      line-height: 1.8;
    }}

    body.dark-mode .segment-text {{
      color: #d1d5db;
    }}

    .search-highlight {{
      background: #fef08a;
      padding: 2px 0;
    }}

    body.dark-mode .search-highlight {{
      background: #854d0e;
    }}

    @media (max-width: 640px) {{
      body {{
        padding: 12px;
      }}

      header {{
        padding: 16px;
      }}

      h1 {{
        font-size: 24px;
      }}

      .controls {{
        flex-direction: column;
      }}

      .transcript-container {{
        padding: 16px;
      }}
    }}
  </style>
"""

    @staticmethod
    def _get_page_header() -> str:
        """Get page header HTML."""
        return """  <div class="container">
    <header>
      <h1>Podcast Transcript</h1>
      <div class="controls">
        <div class="search-container">
          <input type="text" id="search-box" placeholder="Search transcript...">
        </div>
        <button class="theme-toggle" id="theme-toggle">Toggle Dark Mode</button>
      </div>
    </header>
"""

    @staticmethod
    def _get_search_bar() -> str:
        """Get search bar HTML (already in header)."""
        return ""

    @staticmethod
    def _get_speaker_legend(speakers: List[str], colors: Dict[str, str]) -> str:
        """Get speaker legend HTML.

        Args:
            speakers: List of speaker names
            colors: Speaker color mapping

        Returns:
            Speaker legend HTML
        """
        items = []
        for speaker in sorted(speakers):
            color = colors.get(speaker, "#6b7280")
            escaped_speaker = HTMLFormatter._html_escape(speaker)
            items.append(
                f'      <div class="legend-item">\n'
                f'        <div class="color-dot" style="background: {color};"></div>\n'
                f"        <span>{escaped_speaker}</span>\n"
                f"      </div>"
            )

        items_html = "\n".join(items)

        return f"""    <div class="speaker-legend">
      <div class="legend-title">Speakers</div>
      <div class="legend-items">
{items_html}
      </div>
    </div>
"""

    @staticmethod
    def _get_javascript() -> str:
        """Get JavaScript for interactivity."""
        return """  <script>
    // Dark mode toggle
    const themeToggle = document.getElementById('theme-toggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

    // Initialize theme
    if (localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') && prefersDark)) {
      document.body.classList.add('dark-mode');
    }

    themeToggle.addEventListener('click', () => {
      document.body.classList.toggle('dark-mode');
      localStorage.setItem(
        'theme',
        document.body.classList.contains('dark-mode') ? 'dark' : 'light'
      );
    });

    // Search functionality
    const searchBox = document.getElementById('search-box');
    const segments = document.querySelectorAll('.segment');

    searchBox.addEventListener('input', (e) => {
      const query = e.target.value.toLowerCase();

      segments.forEach(segment => {
        const text = segment.querySelector('.segment-text').textContent.toLowerCase();
        const speaker = segment.dataset.speaker.toLowerCase();

        if (query === '' || text.includes(query) || speaker.includes(query)) {
          segment.classList.remove('hidden');

          // Highlight matches
          if (query !== '') {
            const textEl = segment.querySelector('.segment-text');
            const originalText = textEl.textContent;
            const regex = new RegExp(`(${query})`, 'gi');
            textEl.innerHTML = originalText.replace(
              regex,
              '<span class="search-highlight">$1</span>'
            );
          } else {
            // Remove highlights
            const textEl = segment.querySelector('.segment-text');
            textEl.textContent = textEl.textContent;
          }
        } else {
          segment.classList.add('hidden');
        }
      });
    });

    // Timestamp click to copy
    document.querySelectorAll('.timestamp').forEach(ts => {
      ts.style.cursor = 'pointer';
      ts.title = 'Click to copy timestamp';
      ts.addEventListener('click', () => {
        navigator.clipboard.writeText(ts.textContent);
        const original = ts.textContent;
        ts.textContent = 'Copied!';
        setTimeout(() => {
          ts.textContent = original;
        }, 1000);
      });
    });
  </script>
"""
