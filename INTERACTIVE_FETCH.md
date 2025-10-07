# Interactive Fetch Mode

## Overview

The `--interactive` (or `-i`) flag for `podx-fetch` provides a browsing interface to visually select episodes before downloading them. This combines the episode discovery UI from `podx-browse` with the download functionality of `podx-fetch`.

## Why Use Interactive Mode?

**Before**: You had to either:

- Know the exact date of the episode you wanted
- Use `podx-browse` to find it, then manually copy the date to `podx-fetch`
- Browse on a website to find the episode date

**Now**: Browse and download in one command!

## Usage

### Basic Usage

```bash
# Interactive browse and download
podx-fetch --show "My Podcast" --interactive
```

### With RSS URL

If you already have the RSS feed URL:

```bash
podx-fetch --rss-url "https://feed.example.com/podcast.xml" --interactive
```

### With Custom Output

You can still specify custom output options:

```bash
# Custom output directory
podx-fetch --show "My Podcast" --interactive --outdir /custom/path

# Save metadata to specific file
podx-fetch --show "My Podcast" --interactive -o episode_meta.json
```

## How It Works

1. **Launch Browser**: The command displays a paginated list of episodes with:

   - Episode number
   - Publication date
   - Duration
   - Title

2. **Navigate**: Use the interactive commands:

   - `1-N`: Select episode by number
   - `N`: Next page
   - `P`: Previous page
   - `Q`: Quit

3. **Download**: After selection:
   - Audio is downloaded to `<SHOW>/<DATE>/` directory
   - Episode metadata is saved to `<SHOW>/<DATE>/episode-meta.json`
   - Success message is logged (metadata is NOT printed to stdout)

## Output

In interactive mode, the episode metadata is saved to a file in the episode directory:

**File Location**: `<SHOW>/<DATE>/episode-meta.json`

**File Contents**:

```json
{
  "show": "My Podcast",
  "feed": "https://feed.example.com/podcast.xml",
  "episode_title": "Episode Title",
  "episode_published": "2025-10-07T12:00:00Z",
  "audio_path": "My Podcast/2025-10-07/Episode Title.mp3"
}
```

**Note**: Unlike non-interactive mode, the metadata is **not** printed to stdout. This makes interactive mode suitable for manual use rather than piping to other commands.

## Benefits of Interactive Mode

Interactive mode combines visual episode discovery with automatic download and organization:

- **Visual Selection**: Browse episodes in a paginated table with dates, durations, and titles
- **Smart Directory Structure**: Automatically saves to `<SHOW>/<DATE>/` format
- **Self-Contained**: Downloads audio and saves metadata in one organized location
- **No Manual Date Lookup**: Select visually instead of hunting for episode dates
- **Full Metadata**: Saves complete episode information to `episode-meta.json` including show, title, publish date, and audio path

## Examples

### Example 1: Browse and Download

```bash
$ podx-fetch --show "Tech Podcast" --interactive

🔍 Finding RSS feed for: Tech Podcast
📡 Loading episodes from: https://...
✅ Loaded 150 episodes

┌─ Tech Podcast - Episodes (Page 1/19) ─┐
│ #   Date         Duration  Title       │
│ 1   2025-10-06   01:15:30  Episode 150 │
│ 2   2025-09-29   01:10:45  Episode 149 │
│ 3   2025-09-22   01:20:15  Episode 148 │
│ ...                                     │
└─────────────────────────────────────────┘

👉 Your choice: 2

✅ Selected episode 2: Episode 149
📥 Downloading audio...
💾 Episode metadata saved: Tech Podcast/2025-09-29/episode-meta.json

$ ls "Tech Podcast/2025-09-29/"
Episode 149.mp3
episode-meta.json
```

### Example 2: With Custom Directory

```bash
# Download to specific directory
podx-fetch --show "My Podcast" --interactive --outdir /media/podcasts/downloads
```

### Example 3: Continue Processing After Interactive Fetch

```bash
# First, fetch interactively
podx-fetch --show "My Podcast" --interactive

# Then process the downloaded episode
cat "My Podcast/2025-10-07/episode-meta.json" | podx-transcode | podx-transcribe
```

## Ignored Flags in Interactive Mode

When using `--interactive`, these flags are ignored:

- `--date`: Episode is selected from browser
- `--title-contains`: Episode is selected from browser

These flags still work:

- `--show` or `--rss-url`: Required to load feed
- `--outdir`: Override output directory
- `--output` / `-o`: Save metadata to specific file

## Dependencies

Interactive mode requires the `rich` library for the terminal UI:

```bash
pip install rich
```

If not installed, you'll get a helpful error message.

## Tips

1. **Pagination**: For podcasts with many episodes, use `N` and `P` to navigate pages efficiently

2. **Search by Date**: If you know roughly when an episode was published, navigate to that time period and select visually

3. **Quick Selection**: Episodes are numbered globally, so episode #42 is always #42 regardless of what page you're on

4. **Pipeline Ready**: The output is immediately usable in pipelines, unlike `podx-browse` which outputs a different format

5. **Directory Structure**: Episodes are automatically organized in `<SHOW>/<DATE>` format, making them easy to find later

## Troubleshooting

### "No podcasts found"

Make sure the show name is accurate. Try searching on iTunes Podcasts first to verify the exact name.

### "Interactive mode requires additional dependencies"

Install rich: `pip install rich`

### "No episodes found in RSS feed"

The RSS feed might be empty or malformed. Try with `--rss-url` pointing to a known working feed.

### Browser doesn't clear screen

This is a terminal compatibility issue. The browser works but may not clear between pages on some terminals.

## Related Commands

- **`podx-fetch`** (non-interactive): Requires `--date` or `--title-contains` to select episode
- **`podx run`**: Full pipeline orchestration from show name and date
