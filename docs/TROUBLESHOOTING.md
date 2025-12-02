# 🔧 PodX Troubleshooting Guide

Having issues with PodX? This guide covers common problems and their solutions. Issues are organized by category for easy navigation.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Model Download Problems](#model-download-problems)
- [Audio Processing Errors](#audio-processing-errors)
- [Transcription Issues](#transcription-issues)
- [Diarization Problems](#diarization-problems)
- [API and LLM Issues](#api-and-llm-issues)
- [Performance Problems](#performance-problems)
- [Platform-Specific Issues](#platform-specific-issues)
- [Episode Fetching Issues](#episode-fetching-issues)
- [Export and Output Issues](#export-and-output-issues)
- [Debugging Techniques](#debugging-techniques)
- [Getting Help](#getting-help)

---

## Installation Issues

### "Command not found: podx"

**Problem**: After installation, running `podx` gives "command not found" error.

**Solutions**:

1. **Ensure installation completed successfully**:
   ```bash
   pip install -e ".[asr,whisperx,llm,notion]"
   ```

2. **Check if pip packages are in PATH**:
   ```bash
   # Find where pip installed the package
   pip show podx

   # Add pip bin directory to PATH (if needed)
   export PATH="$HOME/.local/bin:$PATH"  # Linux
   export PATH="$HOME/Library/Python/3.x/bin:$PATH"  # macOS
   ```

3. **Use python -m to run commands**:
   ```bash
   python -m podx.cli.run --help
   ```

4. **Verify Python version**:
   ```bash
   python --version  # Should be 3.9+
   ```

### "No module named 'podx'"

**Problem**: Python can't find the podx module.

**Solutions**:

1. **Install in editable mode** (for development):
   ```bash
   cd /path/to/podx
   pip install -e ".[asr,whisperx,llm,notion]"
   ```

2. **Check virtual environment**:
   ```bash
   # Make sure you're in the right venv
   which python
   pip list | grep podx
   ```

3. **Reinstall dependencies**:
   ```bash
   pip uninstall podx
   pip install -e ".[asr,whisperx,llm,notion]"
   ```

### "error: externally-managed-environment"

**Problem**: On some Linux distributions (Debian 12+, Ubuntu 23.04+), pip refuses to install packages.

**Solutions**:

1. **Use a virtual environment** (RECOMMENDED):
   ```bash
   python -m venv podx-env
   source podx-env/bin/activate  # Linux/macOS
   podx-env\Scripts\activate     # Windows
   pip install -e ".[asr,whisperx,llm,notion]"
   ```

2. **Use pipx** (for CLI tools):
   ```bash
   pipx install podx
   ```

3. **Use --break-system-packages** (NOT RECOMMENDED):
   ```bash
   pip install --break-system-packages -e ".[asr,whisperx,llm,notion]"
   ```

### "FFmpeg not found"

**Problem**: Audio processing fails with FFmpeg errors.

**Solutions**:

1. **Install FFmpeg**:
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install ffmpeg

   # Windows (Chocolatey)
   choco install ffmpeg

   # Or download from: https://ffmpeg.org/download.html
   ```

2. **Verify installation**:
   ```bash
   ffmpeg -version
   which ffmpeg
   ```

3. **Check PATH**:
   ```bash
   echo $PATH
   # FFmpeg directory should be in PATH
   ```

---

## Model Download Problems

### "Model download is very slow"

**Problem**: First run downloads 1-2GB of models and takes a long time.

**Solutions**:

1. **Use a smaller model** for initial testing:
   ```bash
   podx run --model base --show "My Podcast" --date 2024-10-15
   ```

2. **Pre-download models**:
   ```python
   from faster_whisper import WhisperModel

   # Download models in advance
   WhisperModel("base")
   WhisperModel("large-v3-turbo")
   ```

3. **Check network connection**:
   ```bash
   curl -I https://huggingface.co
   ```

4. **Use a local mirror** (if available):
   ```bash
   export HF_ENDPOINT=https://your-mirror.com
   ```

### "Model download failed" or "Connection timeout"

**Problem**: Model download interrupted or fails to connect.

**Solutions**:

1. **Retry with longer timeout**:
   ```bash
   export HF_HUB_DOWNLOAD_TIMEOUT=600  # 10 minutes
   podx run --show "My Podcast" --date 2024-10-15
   ```

2. **Check HuggingFace status**:
   - Visit: https://status.huggingface.co

3. **Clear cache and retry**:
   ```bash
   rm -rf ~/.cache/huggingface
   podx run --show "My Podcast" --date 2024-10-15
   ```

4. **Use proxy** (if behind firewall):
   ```bash
   export HTTP_PROXY=http://proxy.example.com:8080
   export HTTPS_PROXY=http://proxy.example.com:8080
   ```

### "No space left on device"

**Problem**: Insufficient disk space for model downloads.

**Solutions**:

1. **Check available space**:
   ```bash
   df -h ~/.cache/huggingface
   ```

2. **Clean up old models**:
   ```bash
   # Remove unused models from cache
   rm -rf ~/.cache/huggingface/hub/*

   # Keep only essential models
   # base: ~150MB, large-v3-turbo: ~1.5GB
   ```

3. **Use smaller models**:
   ```bash
   podx run --model base  # Much smaller
   ```

4. **Change cache location** (to larger disk):
   ```bash
   export HF_HOME=/path/to/larger/disk/huggingface
   ```

---

## Audio Processing Errors

### "Invalid audio format" or "Could not open file"

**Problem**: Audio file format not supported or corrupted.

**Solutions**:

1. **Check file integrity**:
   ```bash
   ffprobe audio.mp3
   ```

2. **Convert to supported format**:
   ```bash
   ffmpeg -i input.m4a -ar 16000 -ac 1 output.wav
   ```

3. **Re-download audio**:
   ```bash
   podx fetch --show "My Podcast" --date 2024-10-15 | tee fetch.json
   ```

4. **Skip transcoding** (if already in good format):
   ```bash
   podx run --show "My Podcast" --date 2024-10-15 --no-transcode
   ```

### "Audio file too large"

**Problem**: Processing very long episodes (5+ hours) causes issues.

**Solutions**:

1. **Split audio into chunks**:
   ```bash
   # Split into 1-hour segments
   ffmpeg -i long-audio.mp3 -f segment -segment_time 3600 -c copy segment_%03d.mp3

   # Process each segment
   for f in segment_*.mp3; do
     podx transcribe --input "$f"
   done
   ```

2. **Use batch processing**:
   ```python
   from podx.api import PodxClient

   client = PodxClient()
   result = client.transcribe(
       "long-audio.mp3",
       batch_size=16  # Smaller batches
   )
   ```

3. **Increase memory limits**:
   ```bash
   # For very large files
   ulimit -v unlimited
   ```

### "Transcoding failed" or "Normalization error"

**Problem**: Audio normalization step fails.

**Solutions**:

1. **Check FFmpeg logs**:
   ```bash
   podx transcode --input fetch.json --verbose
   ```

2. **Skip normalization** (use raw audio):
   ```bash
   podx run --no-transcode
   ```

3. **Manual normalization**:
   ```bash
   ffmpeg -i input.mp3 -ar 16000 -ac 1 -ab 192k normalized.wav
   podx transcribe --input normalized.wav
   ```

4. **Check audio codec**:
   ```bash
   ffprobe -v error -select_streams a:0 -show_entries stream=codec_name input.mp3
   ```

---

## Transcription Issues

### "Out of memory" during transcription

**Problem**: System runs out of RAM or VRAM during transcription.

**Solutions**:

1. **Use smaller model**:
   ```bash
   podx run --model base  # Uses ~1GB RAM vs ~4GB for large
   ```

2. **Force CPU mode** (if GPU RAM limited):
   ```bash
   podx transcribe --device cpu
   ```

3. **Reduce batch size**:
   ```python
   from podx.api import PodxClient

   client = PodxClient()
   result = client.transcribe(
       "episode.mp3",
       model="large-v3-turbo",
       batch_size=8  # Default is 16
   )
   ```

4. **Close other applications**:
   - Free up system memory before processing

5. **Use compute_type int8** (lower precision):
   ```python
   result = client.transcribe(
       "episode.mp3",
       compute_type="int8"  # Uses less memory than float16
   )
   ```

### "Transcription is very slow"

**Problem**: Processing takes much longer than expected.

**Solutions**:

1. **Use GPU acceleration** (if available):
   ```bash
   # Check if CUDA is available
   python -c "import torch; print(torch.cuda.is_available())"

   # Use GPU
   podx transcribe --device cuda
   ```

2. **Use faster model**:
   ```bash
   podx run --model base  # Faster but less accurate
   ```

3. **Check CPU usage**:
   ```bash
   top  # or htop
   # Ensure podx is using available cores
   ```

4. **Enable VAD filter** (skip silence):
   ```python
   result = client.transcribe(
       "episode.mp3",
       vad_filter=True  # Skip silent portions
   )
   ```

5. **Use faster-whisper optimizations**:
   ```python
   result = client.transcribe(
       "episode.mp3",
       compute_type="int8",
       beam_size=1  # Faster but less accurate
   )
   ```

### "Transcription is inaccurate" or "Wrong language detected"

**Problem**: Transcript has errors or wrong language.

**Solutions**:

1. **Use more accurate model**:
   ```bash
   podx run --model large-v3  # Most accurate
   ```

2. **Specify language explicitly**:
   ```bash
   podx transcribe --language en  # Force English
   ```

3. **Check audio quality**:
   ```bash
   ffprobe -v error -show_entries format=bit_rate -of default=noprint_wrappers=1 audio.mp3
   # Low bitrate (<64kbps) may cause poor transcription
   ```

4. **Use OpenAI Whisper API** (more accurate):
   ```bash
   export OPENAI_API_KEY="sk-..."
   podx run --asr-provider openai --show "My Podcast" --date 2024-10-15
   ```

5. **Improve audio preprocessing**:
   ```bash
   # Ensure proper normalization
   podx transcode --input fetch.json | podx transcribe
   ```

### "CUDA out of memory"

**Problem**: GPU runs out of memory during transcription.

**Solutions**:

1. **Use smaller model**:
   ```bash
   podx run --model base
   ```

2. **Use CPU instead**:
   ```bash
   podx transcribe --device cpu
   ```

3. **Reduce batch size**:
   ```python
   result = client.transcribe("audio.mp3", batch_size=4)
   ```

4. **Use int8 compute type**:
   ```python
   result = client.transcribe("audio.mp3", compute_type="int8")
   ```

5. **Clear GPU memory**:
   ```python
   import torch
   torch.cuda.empty_cache()
   ```

### "System freezes during diarization"

**Problem**: System becomes unresponsive during `podx diarize` due to high memory usage.

**Background**: PyAnnote speaker diarization can use 10-14GB+ of RAM, especially with `speaker-diarization-3.1`. The memory usage depends on audio length and the `embedding_batch_size` parameter.

**Solutions**:

1. **Automatic (v4.1.1+)**: PodX now automatically adjusts batch size based on available RAM:
   - `< 4 GB` available: batch_size=1
   - `4-8 GB`: batch_size=8
   - `8-12 GB`: batch_size=16
   - `≥ 12 GB`: batch_size=32 (default)

   Check output at start of diarization:
   ```
   Memory: 4.2 GB available / 16.0 GB total
   Using reduced batch size (8) for memory efficiency
   ```

2. **Close other applications** before diarizing to free up RAM.

3. **Split long audio files** - Processing 30-minute chunks uses less memory than 3-hour files.

4. **Use cloud transcription** - Consider `runpod:large-v3-turbo` to offload heavy processing:
   ```bash
   podx run --model runpod:large-v3-turbo
   ```

---

## Diarization Problems

### "Speaker labels are inaccurate"

**Problem**: Speaker diarization assigns wrong speakers to segments.

**Solutions**:

1. **Check audio quality**:
   - Diarization requires clear audio
   - Background noise reduces accuracy

2. **Adjust min_speakers/max_speakers**:
   ```python
   from podx.api import PodxClient

   client = PodxClient()
   result = client.diarize(
       "transcript.json",
       min_speakers=2,
       max_speakers=2  # If you know exact count
   )
   ```

3. **Use longer segments**:
   - Very short segments (<1s) are harder to diarize accurately

4. **Try WhisperX diarization**:
   ```bash
   # WhisperX has better diarization
   pip install -e ".[whisperx]"
   podx diarize --engine whisperx
   ```

5. **Manual correction**:
   - Edit the diarized JSON to fix specific errors
   - Use speaker mapping in exports

### "Diarization is very slow"

**Problem**: Speaker diarization takes a long time.

**Solutions**:

1. **Use GPU acceleration**:
   ```bash
   podx diarize --device cuda
   ```

2. **Skip diarization** (if not needed):
   ```bash
   podx run --no-diarize
   ```

3. **Use simpler diarization**:
   ```python
   # Reduce clustering complexity
   result = client.diarize("transcript.json", num_speakers=2)
   ```

### "No speakers detected"

**Problem**: Diarization fails to identify any speakers.

**Solutions**:

1. **Check audio has speech**:
   ```bash
   # Verify transcript has content
   cat transcript.json | jq '.segments | length'
   ```

2. **Lower min_speakers**:
   ```python
   result = client.diarize("transcript.json", min_speakers=1)
   ```

3. **Check audio format**:
   ```bash
   ffprobe audio.wav
   # Should be mono, 16kHz
   ```

4. **Increase segment length**:
   - Very short audio clips may not diarize well

---

## API and LLM Issues

### "Invalid API key" or "Authentication failed"

**Problem**: LLM provider rejects API key.

**Solutions**:

1. **Verify API key format**:
   ```bash
   # OpenAI keys start with "sk-"
   echo $OPENAI_API_KEY

   # Anthropic keys start with "sk-ant-"
   echo $ANTHROPIC_API_KEY
   ```

2. **Check key is set**:
   ```bash
   env | grep API_KEY
   ```

3. **Export keys properly**:
   ```bash
   export OPENAI_API_KEY="sk-proj-..."
   export ANTHROPIC_API_KEY="sk-ant-..."
   ```

4. **Add to shell profile** (permanent):
   ```bash
   echo 'export OPENAI_API_KEY="sk-..."' >> ~/.zshrc
   source ~/.zshrc
   ```

5. **Pass key directly** (for testing):
   ```python
   from podx.llm import get_provider

   provider = get_provider("openai", api_key="sk-...")
   ```

### "Rate limit exceeded"

**Problem**: Too many API requests in short time.

**Solutions**:

1. **Add delays between requests**:
   ```python
   import time

   for episode in episodes:
       process_episode(episode)
       time.sleep(60)  # Wait 1 minute between episodes
   ```

2. **Use tier with higher limits**:
   - Upgrade OpenAI/Anthropic account tier

3. **Switch providers**:
   ```bash
   # Use Ollama (local, no rate limits)
   podx run --llm-provider ollama --llm-model llama2
   ```

4. **Batch operations**:
   ```python
   # Process multiple episodes with single LLM call
   client.batch_process(episode_list)
   ```

### "API request timeout"

**Problem**: LLM API calls time out.

**Solutions**:

1. **Increase timeout**:
   ```python
   from podx.llm import get_provider

   provider = get_provider("openai", timeout=120)  # 2 minutes
   ```

2. **Use faster model**:
   ```bash
   podx run --llm-model gpt-4o-mini  # Faster than gpt-4
   ```

3. **Check network connection**:
   ```bash
   curl -I https://api.openai.com
   ```

4. **Reduce prompt size**:
   - Split large transcripts into chunks

### "Model not found" or "Invalid model"

**Problem**: LLM provider doesn't recognize model name.

**Solutions**:

1. **Check available models**:
   ```python
   from podx.llm import get_provider

   provider = get_provider("openai")
   # Use valid model names: gpt-4o, gpt-4, gpt-4o-mini
   ```

2. **Update model name**:
   ```bash
   # Old model names may not work
   podx run --llm-model gpt-4o  # Not gpt-4-turbo
   ```

3. **Check provider access**:
   - Ensure your account has access to requested model

4. **Use default model**:
   ```bash
   # Omit --llm-model to use provider default
   podx run --llm-provider openai
   ```

---

## Performance Problems

### "Processing is too slow"

**Problem**: Overall pipeline takes too long.

**Solutions**:

1. **Use GPU acceleration**:
   ```bash
   # Check CUDA availability
   python -c "import torch; print(torch.cuda.is_available())"

   podx run --device cuda
   ```

2. **Use faster models**:
   ```bash
   podx run --model base --llm-model gpt-4o-mini
   ```

3. **Skip optional steps**:
   ```bash
   podx run --no-deepcast --no-notion --no-export
   ```

4. **Process in parallel** (for multiple episodes):
   ```bash
   # Use GNU parallel or xargs
   cat episode_list.txt | parallel -j 4 podx run --show "Podcast" --date {}
   ```

5. **Enable caching**:
   - Intermediate files are cached by default
   - Reuse `--resume` to skip completed steps

### "High memory usage"

**Problem**: PodX uses too much RAM.

**Solutions**:

1. **Use smaller models**:
   ```bash
   podx run --model base
   ```

2. **Use int8 compute**:
   ```python
   result = client.transcribe("audio.mp3", compute_type="int8")
   ```

3. **Process in chunks**:
   ```python
   # Split large files before processing
   ```

4. **Close other applications**:
   - Free up system memory

5. **Increase swap space** (Linux):
   ```bash
   sudo fallocate -l 8G /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

### "Disk space filling up"

**Problem**: PodX uses too much disk space.

**Solutions**:

1. **Clean up intermediate files**:
   ```bash
   # Remove transcoded audio after processing
   find . -name "*-transcoded.wav" -delete
   ```

2. **Don't keep intermediates**:
   ```bash
   podx run --no-keep-intermediates
   ```

3. **Remove old episodes**:
   ```bash
   # Clean up processed episodes
   rm -rf Podcast_Name/2024-*
   ```

4. **Clear model cache**:
   ```bash
   rm -rf ~/.cache/huggingface
   ```

---

## Platform-Specific Issues

### macOS Issues

#### "Code signature invalid" or "Developer cannot be verified"

**Problem**: macOS blocks FFmpeg or other binaries.

**Solutions**:

1. **Install via Homebrew** (recommended):
   ```bash
   brew install ffmpeg
   ```

2. **Allow in Security & Privacy**:
   - System Preferences → Security & Privacy → Allow anyway

3. **Remove quarantine attribute**:
   ```bash
   xattr -dr com.apple.quarantine /usr/local/bin/ffmpeg
   ```

#### "Microphone access denied"

**Problem**: macOS blocks audio access.

**Solutions**:

1. **Grant microphone permissions**:
   - System Preferences → Security & Privacy → Microphone
   - Enable for Terminal/iTerm

2. **Reset permissions**:
   ```bash
   tccutil reset Microphone
   ```

### Linux Issues

#### "GLIBC version not found"

**Problem**: System has older glibc than required.

**Solutions**:

1. **Use Docker** (recommended):
   ```bash
   docker run -v $(pwd):/data podx podx run --show "Podcast"
   ```

2. **Compile from source**:
   ```bash
   # Install newer Python version
   pyenv install 3.11
   pyenv global 3.11
   ```

3. **Use pre-built binaries**:
   - Download static builds of dependencies

#### "Permission denied" on files

**Problem**: File ownership or permissions issues.

**Solutions**:

1. **Check file permissions**:
   ```bash
   ls -la audio.mp3
   ```

2. **Fix ownership**:
   ```bash
   sudo chown $USER:$USER audio.mp3
   ```

3. **Fix permissions**:
   ```bash
   chmod 644 audio.mp3
   ```

### Windows Issues

#### "FFmpeg not recognized"

**Problem**: Windows can't find FFmpeg.

**Solutions**:

1. **Add to PATH**:
   - System Properties → Environment Variables → Path
   - Add FFmpeg bin directory

2. **Use full path**:
   ```bash
   set FFMPEG_PATH=C:\ffmpeg\bin\ffmpeg.exe
   ```

3. **Install via Chocolatey**:
   ```bash
   choco install ffmpeg
   ```

#### "Line endings / encoding issues"

**Problem**: Text files have wrong line endings or encoding.

**Solutions**:

1. **Use UTF-8 encoding**:
   - Ensure files are saved as UTF-8

2. **Convert line endings**:
   ```bash
   dos2unix file.txt
   # Or in git:
   git config core.autocrlf true
   ```

---

## Episode Fetching Issues

### "Episode not found"

**Problem**: Can't find episode by date or title.

**Solutions**:

1. **Use interactive mode**:
   ```bash
   podx fetch --show "My Podcast" --interactive
   ```

2. **Check show name**:
   ```bash
   # Try variations
   podx fetch --show "Lex Fridman Podcast"
   podx fetch --show "The Lex Fridman Podcast"
   ```

3. **Use direct RSS URL**:
   ```bash
   podx fetch --rss-url "https://feeds.example.com/podcast.xml" --date 2024-10-15
   ```

4. **Check date format**:
   ```bash
   # Use YYYY-MM-DD format
   podx fetch --show "My Podcast" --date 2024-10-15
   ```

5. **Browse available episodes**:
   ```bash
   podx fetch --show "My Podcast" --list-episodes
   ```

### "RSS feed error" or "Feed not accessible"

**Problem**: Can't access or parse podcast RSS feed.

**Solutions**:

1. **Check feed URL**:
   ```bash
   curl -I "https://feeds.example.com/podcast.xml"
   ```

2. **Use alternative feed**:
   - Try different feed providers (Apple Podcasts, Spotify, etc.)

3. **Download manually**:
   ```bash
   # Download audio directly
   wget https://example.com/episode.mp3
   podx transcribe --input episode.mp3
   ```

4. **Check network/firewall**:
   ```bash
   # Test connectivity
   ping feeds.example.com
   ```

### "Download failed" or "Connection refused"

**Problem**: Episode download interrupted or fails.

**Solutions**:

1. **Retry with longer timeout**:
   ```python
   from podx.api import PodxClient

   client = PodxClient()
   result = client.fetch_episode(
       show="My Podcast",
       date="2024-10-15",
       timeout=300  # 5 minutes
   )
   ```

2. **Download manually**:
   ```bash
   wget -c https://example.com/episode.mp3  # -c resumes
   ```

3. **Use aria2** (for faster downloads):
   ```bash
   aria2c -x 16 https://example.com/episode.mp3
   ```

4. **Check disk space**:
   ```bash
   df -h .
   ```

---

## Export and Output Issues

### "Export failed" or "Invalid format"

**Problem**: Exporting to specific format fails.

**Solutions**:

1. **Check format is supported**:
   ```bash
   podx export --formats txt,srt,vtt,md,json
   ```

2. **Verify input file**:
   ```bash
   # Input must be valid JSON
   jq . transcript.json
   ```

3. **Export one format at a time**:
   ```bash
   podx export --formats txt < transcript.json
   podx export --formats srt < transcript.json
   ```

4. **Check output directory permissions**:
   ```bash
   ls -la exports/
   chmod 755 exports/
   ```

### "Unicode/encoding errors in exports"

**Problem**: Special characters broken in exported files.

**Solutions**:

1. **Ensure UTF-8 encoding**:
   ```python
   from podx.api import PodxClient

   client = PodxClient()
   client.export(transcript, "output.txt", encoding="utf-8")
   ```

2. **Check locale settings**:
   ```bash
   locale  # Should include UTF-8
   export LC_ALL=en_US.UTF-8
   ```

3. **Use BOM for Windows**:
   - Some editors need UTF-8 BOM

### "Timestamps incorrect in SRT/VTT"

**Problem**: Subtitle timing is off.

**Solutions**:

1. **Check source transcript**:
   ```bash
   # Verify timestamps in source JSON
   jq '.segments[] | {start, end, text}' transcript.json | head
   ```

2. **Adjust offset**:
   ```python
   # Add time offset if needed
   result = client.export(
       transcript,
       "output.srt",
       time_offset=2.5  # Shift by 2.5 seconds
   )
   ```

3. **Re-transcribe with better timestamps**:
   ```bash
   podx transcribe --timestamp-granularity word
   ```

---

## Debugging Techniques

### Enable Verbose Logging

```bash
# Set log level to DEBUG
export PODX_LOG_LEVEL=DEBUG

# Run command with verbose output
podx run --show "My Podcast" --date 2024-10-15 --verbose
```

### Check Intermediate Files

```bash
# Keep all intermediate files for inspection
podx run --keep-intermediates

# Examine each stage
ls -lh Podcast/2024-10-15-episode/
cat Podcast/2024-10-15-episode/transcript-large-v3-turbo.json | jq
```

### Use Python API for Debugging

```python
import logging
from podx.api import PodxClient

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Step through pipeline
client = PodxClient()

# Fetch
fetch_result = client.fetch_episode("My Podcast", "2024-10-15")
print(f"Fetched: {fetch_result}")

# Transcode
transcode_result = client.transcode(fetch_result["audio_path"])
print(f"Transcoded: {transcode_result}")

# Transcribe
transcript = client.transcribe(transcode_result["output_path"])
print(f"Transcript segments: {len(transcript['segments'])}")
```

### Test Individual Components

```python
# Test LLM provider
from podx.llm import get_provider

provider = get_provider("openai", api_key="sk-...")
response = provider.complete(
    messages=[{"role": "user", "content": "Hello"}],
    model="gpt-4o"
)
print(response)

# Test progress reporting
from podx.progress import ConsoleProgressReporter

reporter = ConsoleProgressReporter()
reporter.start("Test", total_steps=3)
reporter.update("Step 1", current=1)
reporter.update("Step 2", current=2)
reporter.complete("Done")
```

### Profile Performance

```python
import cProfile
import pstats
from podx.api import PodxClient

# Profile transcription
client = PodxClient()

profiler = cProfile.Profile()
profiler.enable()

result = client.transcribe("audio.mp3")

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 slowest functions
```

### Check System Resources

```bash
# Monitor resource usage during processing
top -p $(pgrep -f podx)

# Or use htop
htop -p $(pgrep -f podx)

# Check GPU usage
nvidia-smi -l 1  # Update every second

# Check disk I/O
iotop -p $(pgrep -f podx)
```

---

## Getting Help

### Before Asking for Help

1. **Check this troubleshooting guide**
2. **Search existing issues**: [GitHub Issues](https://github.com/evanhourigan/podx/issues)
3. **Review documentation**:
   - [QUICKSTART.md](QUICKSTART.md)
   - [ADVANCED.md](ADVANCED.md)
   - [FAQ.md](FAQ.md)

### Reporting Issues

When reporting issues, include:

1. **System information**:
   ```bash
   podx --version
   python --version
   ffmpeg -version
   uname -a  # or systeminfo on Windows
   ```

2. **Full error message**:
   ```bash
   podx run ... 2>&1 | tee error.log
   ```

3. **Steps to reproduce**:
   - Exact commands run
   - Input files (if shareable)
   - Expected vs actual behavior

4. **Environment**:
   - Operating system and version
   - Python version
   - Virtual environment or system Python
   - Any custom configuration

### Where to Get Help

- **Documentation**: [docs/](.)
- **GitHub Issues**: [Report bugs](https://github.com/evanhourigan/podx/issues)
- **GitHub Discussions**: [Ask questions](https://github.com/evanhourigan/podx/discussions)
- **Stack Overflow**: Tag with `podx` and `podcast-processing`

### Community Guidelines

- Be respectful and patient
- Provide complete information
- Search before asking
- Give back when you can

---

## Common Error Messages

### "RuntimeError: CUDA out of memory"

**Solution**: Use smaller model or CPU mode (see [CUDA out of memory](#cuda-out-of-memory))

### "FileNotFoundError: [Errno 2] No such file or directory"

**Solution**: Check file paths are correct and files exist

### "JSONDecodeError: Expecting value"

**Solution**: Input file is not valid JSON, regenerate or fix manually

### "PermissionError: [Errno 13] Permission denied"

**Solution**: Check file permissions with `ls -la` and fix with `chmod`

### "ConnectionError: Max retries exceeded"

**Solution**: Check internet connection, API service status, or use proxy

### "ValueError: Unknown LLM provider"

**Solution**: Use valid provider name (openai, anthropic, openrouter, ollama)

### "AssertionError: FFmpeg not found"

**Solution**: Install FFmpeg (see [FFmpeg not found](#ffmpeg-not-found))

---

**Still stuck? [Open an issue](https://github.com/evanhourigan/podx/issues) with full details!**
