#!/usr/bin/env python3
"""
Interactive episode browser for podcast discovery and selection.
Provides paginated episode listing with interactive selection.
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import click
import feedparser
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .cli_shared import print_json
from .fetch import find_feed_for_show


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to human readable format."""
    if not seconds:
        return "Unknown"
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    else:
        return f"{minutes}m"


def format_date(date_str: str) -> str:
    """Format date string to readable format."""
    try:
        # Parse various date formats
        for fmt in ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"]:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue
        
        # Fallback: just return first 10 chars if it looks like a date
        if len(date_str) >= 10:
            return date_str[:10]
        return date_str
    except Exception:
        return date_str


def truncate_text(text: str, max_length: int = 80) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


class EpisodeBrowser:
    """Interactive episode browser with pagination."""
    
    def __init__(self, show_name: str, rss_url: Optional[str] = None, episodes_per_page: int = 8):
        self.show_name = show_name
        self.rss_url = rss_url
        self.episodes_per_page = episodes_per_page
        self.console = Console()
        self.episodes: List[Dict[str, Any]] = []
        self.current_page = 0
        self.total_pages = 0
    
    def load_episodes(self) -> bool:
        """Load episodes from RSS feed."""
        try:
            # Find RSS feed if not provided
            if not self.rss_url:
                self.console.print(f"🔍 Finding RSS feed for: [cyan]{self.show_name}[/cyan]")
                feed_url = find_feed_for_show(self.show_name)
                if not feed_url:
                    self.console.print(f"❌ Could not find RSS feed for: {self.show_name}")
                    return False
                self.rss_url = feed_url
            
            # Parse RSS feed
            self.console.print(f"📡 Loading episodes from: [yellow]{self.rss_url}[/yellow]")
            feed = feedparser.parse(self.rss_url)
            
            if not feed.entries:
                self.console.print("❌ No episodes found in RSS feed")
                return False
            
            # Extract episode information
            self.episodes = []
            for entry in feed.entries:
                # Get audio URL from enclosures
                audio_url = None
                duration = None
                
                if hasattr(entry, 'enclosures') and entry.enclosures:
                    for enclosure in entry.enclosures:
                        if enclosure.type and 'audio' in enclosure.type:
                            audio_url = enclosure.href
                            # Try to get duration
                            if hasattr(enclosure, 'length'):
                                try:
                                    duration = int(enclosure.length)
                                except (ValueError, TypeError):
                                    pass
                            break
                
                # Extract duration from iTunes tags if not found
                if not duration and hasattr(entry, 'itunes_duration'):
                    try:
                        duration_str = entry.itunes_duration
                        # Parse HH:MM:SS or MM:SS format
                        parts = duration_str.split(':')
                        if len(parts) == 3:  # HH:MM:SS
                            duration = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        elif len(parts) == 2:  # MM:SS
                            duration = int(parts[0]) * 60 + int(parts[1])
                    except (ValueError, AttributeError):
                        pass
                
                episode = {
                    'title': entry.title,
                    'published': entry.published if hasattr(entry, 'published') else 'Unknown',
                    'description': entry.summary if hasattr(entry, 'summary') else '',
                    'audio_url': audio_url,
                    'duration': duration,
                    'link': entry.link if hasattr(entry, 'link') else '',
                }
                
                self.episodes.append(episode)
            
            # Calculate pagination
            self.total_pages = (len(self.episodes) + self.episodes_per_page - 1) // self.episodes_per_page
            
            self.console.print(f"✅ Loaded [green]{len(self.episodes)}[/green] episodes")
            return True
            
        except Exception as e:
            self.console.print(f"❌ Error loading episodes: {e}")
            return False
    
    def display_page(self) -> None:
        """Display current page of episodes."""
        start_idx = self.current_page * self.episodes_per_page
        end_idx = min(start_idx + self.episodes_per_page, len(self.episodes))
        page_episodes = self.episodes[start_idx:end_idx]
        
        # Create title
        title = f"🎙️ {self.show_name} - Episodes (Page {self.current_page + 1}/{self.total_pages})"
        
        # Create table
        table = Table(show_header=True, header_style="bold magenta", title=title)
        table.add_column("#", style="cyan", width=3, justify="right")
        table.add_column("Date", style="green", width=12)
        table.add_column("Duration", style="yellow", width=8, justify="right")
        table.add_column("Title", style="white")
        
        # Add episodes to table
        for i, episode in enumerate(page_episodes):
            episode_num = start_idx + i + 1
            date = format_date(episode['published'])
            duration = format_duration(episode['duration'])
            title = truncate_text(episode['title'], 60)
            
            table.add_row(
                str(episode_num),
                date,
                duration,
                title
            )
        
        self.console.print(table)
        
        # Show navigation options
        options = []
        options.append("[cyan]1-{max_num}[/cyan]: Select episode".format(max_num=len(self.episodes)))
        
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
        
        self.console.print(panel)
    
    def get_user_input(self) -> Optional[Dict[str, Any]]:
        """Get user input and return selected episode or None."""
        while True:
            try:
                user_input = input("\n👉 Your choice: ").strip().upper()
                
                if not user_input:
                    continue
                
                # Quit
                if user_input in ['Q', 'QUIT', 'EXIT']:
                    self.console.print("👋 Goodbye!")
                    return None
                
                # Next page
                if user_input == 'N' and self.current_page < self.total_pages - 1:
                    self.current_page += 1
                    return {}  # Empty dict signals page change
                
                # Previous page
                if user_input == 'P' and self.current_page > 0:
                    self.current_page -= 1
                    return {}  # Empty dict signals page change
                
                # Episode selection
                try:
                    episode_num = int(user_input)
                    if 1 <= episode_num <= len(self.episodes):
                        selected_episode = self.episodes[episode_num - 1]
                        self.console.print(f"✅ Selected episode {episode_num}: [green]{selected_episode['title']}[/green]")
                        return selected_episode
                    else:
                        self.console.print(f"❌ Invalid episode number. Please choose 1-{len(self.episodes)}")
                except ValueError:
                    pass
                
                # Invalid input
                self.console.print("❌ Invalid input. Please try again.")
                
            except (KeyboardInterrupt, EOFError):
                self.console.print("\n👋 Goodbye!")
                return None
    
    def browse(self) -> Optional[Dict[str, Any]]:
        """Main browsing loop."""
        if not self.load_episodes():
            return None
        
        while True:
            self.console.clear()
            self.display_page()
            
            result = self.get_user_input()
            
            # None means quit
            if result is None:
                return None
            
            # Empty dict means page change, continue loop
            if not result:
                continue
            
            # Non-empty dict means episode selected
            return result


@click.command()
@click.option(
    "--show",
    help="Podcast show name (iTunes search)"
)
@click.option(
    "--rss-url", 
    help="Direct RSS feed URL (alternative to --show)"
)
@click.option(
    "--episodes-per-page",
    default=8,
    type=int,
    help="Number of episodes per page [default: 8]"
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Save selected episode metadata to JSON file"
)
@click.option(
    "--process",
    is_flag=True,
    help="Automatically process selected episode with podx run"
)
@click.option(
    "--process-flags",
    default="--align --deepcast --extract-markdown",
    help="Flags to pass to podx run when --process is used"
)
def main(
    show: Optional[str],
    rss_url: Optional[str], 
    episodes_per_page: int,
    output: Optional[Path],
    process: bool,
    process_flags: str
):
    """
    Interactive episode browser for podcast discovery and selection.
    
    Browse episodes with pagination and select one for processing or metadata export.
    """
    
    # Validate arguments
    if not show and not rss_url:
        raise click.ClickException("Either --show or --rss-url must be provided")
    
    if episodes_per_page < 1 or episodes_per_page > 50:
        raise click.ClickException("Episodes per page must be between 1 and 50")
    
    # Create browser
    browser = EpisodeBrowser(
        show_name=show or "Podcast",
        rss_url=rss_url,
        episodes_per_page=episodes_per_page
    )
    
    # Browse episodes
    selected_episode = browser.browse()
    
    if not selected_episode:
        sys.exit(0)  # User quit
    
    # Create episode metadata in podx format
    episode_meta = {
        "show": show or "Podcast",
        "feed": browser.rss_url,
        "episode_title": selected_episode['title'],
        "episode_published": selected_episode['published'],
        "audio_url": selected_episode['audio_url'],
        "episode_link": selected_episode['link'],
        "episode_description": selected_episode['description'],
        "duration": selected_episode['duration']
    }
    
    # Save to file if requested
    if output:
        output.write_text(
            print_json(episode_meta, return_string=True),
            encoding="utf-8"
        )
        browser.console.print(f"💾 Episode metadata saved to: [cyan]{output}[/cyan]")
    
    # Process episode if requested
    if process:
        browser.console.print(f"\n🚀 Processing episode with: [yellow]podx run {process_flags}[/yellow]")
        
        # Extract date from published date for podx run
        episode_date = format_date(selected_episode['published'])
        
        # Build command
        import subprocess
        cmd = ["podx", "run"]
        
        if show:
            cmd.extend(["--show", show])
        elif rss_url:
            cmd.extend(["--rss-url", rss_url])
        
        cmd.extend(["--date", episode_date])
        cmd.extend(process_flags.split())
        
        browser.console.print(f"📋 Running: [cyan]{' '.join(cmd)}[/cyan]")
        
        try:
            result = subprocess.run(cmd, check=True)
            browser.console.print("✅ Episode processing completed successfully!")
        except subprocess.CalledProcessError as e:
            browser.console.print(f"❌ Episode processing failed with exit code {e.returncode}")
            sys.exit(e.returncode)
    else:
        # Just print the metadata
        print_json(episode_meta)


if __name__ == "__main__":
    main()
