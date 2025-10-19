# Browser UI Standardization Specification

This document defines the standard look, feel, and behavior for all interactive browser UIs in podx.

## Scope

**6 Browser Classes:**
- EpisodeBrowser (fetch) - RSS feed browsing
- TranscribeBrowser (transcribe) - Episode transcription selection
- AlignBrowser (align) - Transcript alignment selection
- DiarizeBrowser (diarize) - Aligned transcript diarization selection
- TranscodeBrowser (transcode) - Audio transcoding selection
- DeepcastBrowser (deepcast) - Deepcast analysis selection

**4 Functional Selectors:**
- select_episode_interactive (run) - Multi-status pipeline view
- select_fidelity_interactive (run) - Fidelity level selection
- run_interactive_export (export) - Multi-step: show → episode → source
- _interactive_table_flow (notion) - Analysis upload selection

---

## 1. Architecture Standard

### **Browser Class Structure**

All browser classes MUST follow this pattern:

```python
class SomeBrowser:
    """Interactive browser for selecting {items} to {action}."""

    def __init__(self, items: List[Dict[str, Any]], items_per_page: int = 10):
        self.items = items
        self.items_per_page = items_per_page
        self.console = make_console() if RICH_AVAILABLE else None
        self.current_page = 0
        self.total_pages = max(1, (len(items) + items_per_page - 1) // items_per_page)

    def display_page(self) -> None:
        """Display current page with table and navigation options."""
        # Table rendering logic here
        pass

    def get_user_input(self) -> Optional[Dict[str, Any]]:
        """Get user input and return selected item or None for quit."""
        # Input handling logic here
        pass

    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop. Returns selected item or None."""
        if not self.console:
            return None

        while True:
            self.console.clear()
            self.display_page()
            result = self.get_user_input()

            # {} signals page change, keep looping
            if result == {}:
                continue
            # None signals quit
            if result is None:
                return None
            # Otherwise return selected item
            return result
```

**Rationale:** Separation of concerns makes testing easier and UI logic more maintainable.

---

## 2. Column Layout Standards

### **Standard 5-Column Layout** (Transcribe/Align/Diarize/Transcode)

```python
fixed_widths = {
    "num": 4,      # Episode number
    "status": 24,  # Status indicators (✓/○ + info)
    "show": 20,    # Show name
    "date": 12,    # Date (YYYY-MM-DD)
}
# Title column: dynamic, fills remaining space
title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)
```

**Column Order:** `#, Status, Show, Date, Title`

### **Episode Browser (Fetch)** - Special Case

```python
fixed_widths = {
    "num": 4,       # Episode number
    "date": 12,     # Date with status indicator
    "duration": 8,  # Duration (HH:MM:SS)
}
# Title column: dynamic
title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)
```

**Column Order:** `#, Date, Duration, Title`
**Rationale:** RSS feeds don't have Show column (single show), Status integrated into Date column.

### **Deepcast Browser** - Special Case

```python
fixed_widths = {
    "num": 4,
    "asr": 12,     # ASR model
    "ai": 15,      # AI model
    "type": 24,    # Deepcast type
    "show": 20,
    "date": 12,
}
# Title column: dynamic
title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)
```

**Column Order:** `#, ASR Model, AI Model, Type, Show, Date, Title`
**Rationale:** Deepcast needs to show model configurations.

---

## 3. Status Indicator Standards

### **Format Pattern**

Always use: `"✓ {info}"` or `"○ {info}"`

### **By Browser Type**

| Browser | Completed Format | Pending Format |
|---------|-----------------|----------------|
| **Episode** | `"✓ "` (in date col) | `"  "` (spaces) |
| **Transcribe** | `"✓ {model1, model2}"` | `"○ New"` |
| **Align** | `"✓ {asr_model}"` | `"○ {asr_model}"` |
| **Diarize** | `"✓ {asr_model}"` | `"○ {asr_model}"` |
| **Transcode** | `"✓ Done"` | `"○ New"` |
| **Deepcast** | N/A (no status col) | N/A |

**Style:** Status column always uses `style="magenta"` for consistency.

---

## 4. Table Styling Standards

### **Required Imports**

```python
from ..ui_styles import (
    TABLE_BORDER_STYLE,
    TABLE_HEADER_STYLE,
    TABLE_NUM_STYLE,
    TABLE_SHOW_STYLE,
    TABLE_DATE_STYLE,
    TABLE_TITLE_COL_STYLE,
    make_console,
)
```

### **Table Configuration**

```python
table = Table(
    show_header=True,
    header_style=TABLE_HEADER_STYLE,
    border_style=TABLE_BORDER_STYLE,
    title=title,  # See Title Standards below
    expand=False,
)
```

**NEVER** use hard-coded styles like `"bold magenta"` - always use constants.

### **Column Definitions**

```python
table.add_column("#",
    style=TABLE_NUM_STYLE,
    width=fixed_widths["num"],
    justify="right",
    no_wrap=True)

table.add_column("Status",
    style="magenta",  # Standard for status column
    width=fixed_widths["status"],
    no_wrap=True,
    overflow="ellipsis")

table.add_column("Show",
    style=TABLE_SHOW_STYLE,
    width=fixed_widths["show"],
    no_wrap=True,
    overflow="ellipsis")

table.add_column("Date",
    style=TABLE_DATE_STYLE,
    width=fixed_widths["date"],
    no_wrap=True)

table.add_column("Title",
    style=TABLE_TITLE_COL_STYLE,
    width=title_width,
    no_wrap=True,
    overflow="ellipsis")
```

---

## 5. Title Standards

### **Format Pattern**

```
🎙️ {Context} (Page {current}/{total})
```

### **By Browser**

| Browser | Title |
|---------|-------|
| **Episode** | `🎙️ {show_name} - Episodes (Page {p}/{t})` |
| **Transcribe** | `🎙️ Episodes Available for Transcription (Page {p}/{t})` |
| **Align** | `🎙️ Episodes Available for Alignment (Page {p}/{t})` |
| **Diarize** | `🎙️ Episodes Available for Diarization (Page {p}/{t})` |
| **Transcode** | `🎙️ Episodes Available for Transcoding (Page {p}/{t})` |
| **Deepcast** | `🎙️ Episodes Available for Deepcast Analysis (Page {p}/{t})` |

**Note:** Shortened from "Transcription Alignment" → "Alignment" for brevity.

---

## 6. Navigation Options Standards

### **Panel Configuration**

```python
options = []
options.append(f"[cyan]1-{len(self.items)}[/cyan]: Select episode to {action}")

if self.current_page < self.total_pages - 1:
    options.append("[yellow]N[/yellow]: Next page")

if self.current_page > 0:
    options.append("[yellow]P[/yellow]: Previous page")

options.append("[red]Q[/red]: Quit")

options_text = " • ".join(options)
panel = Panel(
    options_text,
    title="Options",
    border_style="blue",
    padding=(0, 1)
)
console.print(panel)
```

### **Action Verbs by Browser**

| Browser | Action Verb |
|---------|-------------|
| **Episode** | "download" |
| **Transcribe** | "transcribe" |
| **Align** | "align" |
| **Diarize** | "diarize" |
| **Transcode** | "transcode" |
| **Deepcast** | "analyze" |

---

## 7. Input Handling Standards

### **Prompt**

```python
user_input = input("\n👉 Your choice: ").strip().upper()
```

Always use the 👉 emoji for consistency.

### **Quit Handling**

```python
if user_input in ["Q", "QUIT", "EXIT"]:
    console.print("👋 Goodbye!")
    return None
```

### **Navigation Handling**

```python
# Next page
if user_input == "N" and self.current_page < self.total_pages - 1:
    self.current_page += 1
    return {}  # Signal page change

# Previous page
if user_input == "P" and self.current_page > 0:
    self.current_page -= 1
    return {}  # Signal page change
```

### **Selection Handling**

```python
try:
    episode_num = int(user_input)
    if 1 <= episode_num <= len(self.items):
        selected = self.items[episode_num - 1]
        console.print(f"✅ Selected: [green]{selected.get('title', 'item')}[/green]")
        return selected
    else:
        console.print(f"[red]❌ Invalid choice. Please select 1-{len(self.items)}[/red]")
        return {}  # Stay on same page
except ValueError:
    console.print("[red]❌ Invalid input. Please enter a number.[/red]")
    return {}  # Stay on same page
```

**Always show confirmation** when item is selected.
**Always stay on current page** after invalid input (return `{}`).

---

## 8. Error Message Standards

### **Invalid Number**

```python
console.print(f"[red]❌ Invalid choice. Please select 1-{len(self.items)}[/red]")
```

### **Invalid Input (Not a Number)**

```python
console.print("[red]❌ Invalid input. Please enter a number.[/red]")
```

### **No Items Found**

```python
console.print(f"[red]No {item_type} found in {scan_dir}[/red]")
```

**Always** wrap error messages in `[red]...[/red]` and use ❌ emoji.

---

## 9. Borders Allowance Standard

```python
borders_allowance = 16
```

This accounts for table borders, padding, and column separators.

**Standard formula:**
```python
title_width = max(30, term_width - sum(fixed_widths.values()) - borders_allowance)
```

---

## 10. Date Formatting Standard

```python
def format_date(date_str: str) -> str:
    """Format date to YYYY-MM-DD."""
    if not date_str:
        return "Unknown"

    try:
        from dateutil import parser as dtparse
        parsed = dtparse.parse(date_str)
        return parsed.strftime("%Y-%m-%d")
    except Exception:
        # Fallback: use first 10 chars
        return date_str[:10] if len(date_str) >= 10 else date_str
```

Always format dates as **YYYY-MM-DD** (10 characters).

---

## 11. Implementation Checklist

For each browser standardization:

- [ ] Architecture: Separate `display_page()` and `get_user_input()` methods
- [ ] Columns: Use standard widths from Section 2
- [ ] Status: Follow pattern from Section 3
- [ ] Styling: Import constants, no hard-coded styles (Section 4)
- [ ] Title: Follow format from Section 5
- [ ] Navigation: Use standard panel from Section 6
- [ ] Input: Use standard prompt and handling (Section 7)
- [ ] Errors: Use standard messages (Section 8)
- [ ] Borders: Use `borders_allowance = 16`
- [ ] Dates: Format as YYYY-MM-DD

---

## 12. Testing Requirements

After standardization, each browser must:

1. Display correctly on terminals 80-200 columns wide
2. Handle pagination (N/P keys)
3. Validate selection bounds (1-N)
4. Show confirmation message on selection
5. Handle quit gracefully (Q key)
6. Show consistent error messages
7. Preserve all functional behavior

---

## Version

**Version:** 1.0
**Date:** 2025-01-18
**Status:** Draft → In Implementation
