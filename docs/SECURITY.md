# Security Policy

## Supported Versions

We actively support the following versions of podx with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them responsibly:

### Email

Send an email to: **security@yourproject.com** (replace with actual email)

Include the following information:
- **Description**: Clear description of the vulnerability
- **Impact**: Potential security impact and affected components
- **Reproduction**: Step-by-step instructions to reproduce
- **Environment**: Python version, OS, podx version
- **Suggested Fix**: If you have one (optional)

### What to Expect

1. **Acknowledgment**: Within 48 hours
2. **Initial Assessment**: Within 1 week
3. **Fix Timeline**:
   - **Critical**: Patch within 24-48 hours
   - **High**: Patch within 1 week
   - **Medium**: Next minor release
   - **Low**: Next minor release

4. **Disclosure**: Coordinated disclosure after patch is released
   - We will credit you (unless you prefer to remain anonymous)
   - Public advisory will be published with fix

### Public Disclosure Timeline

- We aim for responsible disclosure
- Security patches released before public disclosure
- Minimum 7 days for users to upgrade before full details published
- Critical vulnerabilities may have shorter timeline with advance notice

## Security Best Practices for Users

### 1. API Key Management

**Never** commit API keys to version control:

```bash
# Bad
export OPENAI_API_KEY="sk-..."
git commit -m "Add config"

# Good
echo "OPENAI_API_KEY=sk-..." >> .env
echo ".env" >> .gitignore
```

Use environment variables or secure vaults:
```bash
# Load from .env file
export $(cat .env | xargs)

# Or use a secrets manager
aws secretsmanager get-secret-value --secret-id podx/openai-key
```

### 2. Dependency Security

Keep dependencies updated:

```bash
# Update podx
pip install --upgrade podx

# Check for known vulnerabilities
pip-audit

# Review installed packages
pip list --outdated
```

### 3. File System Safety

When processing untrusted podcast feeds:

```bash
# Use a dedicated working directory
podx run --show "Untrusted Podcast" --working-dir /tmp/podx-isolated/

# Avoid running as root
# Create a dedicated user for podx processing
```

### 4. Network Security

When using podx in production:

- **Use HTTPS** for all API endpoints
- **Validate SSL certificates** (don't disable certificate verification)
- **Rate limit** API calls to prevent abuse
- **Monitor** for unusual activity

### 5. Secrets in Configuration

Don't put secrets in `podcast-config.yaml`:

```yaml
# Bad - secrets in config
analysis:
  default:
    api_key: "sk-abc123"  # NEVER DO THIS

# Good - reference environment variables
analysis:
  default:
    model: "gpt-4.1"
    # API key loaded from OPENAI_API_KEY env var
```

## Security Features

### Input Validation

podx validates all inputs via Pydantic:
- Type checking
- Field validation
- Safe defaults
- No code execution from config files

### Safe Subprocess Execution

- All subprocess calls use `shell=False`
- Commands passed as lists, not strings
- No user input directly interpolated into shell commands

### Credential Handling

- API keys loaded from environment variables
- No credentials in logs or error messages
- Secrets never written to disk (except user's .env files)

## Known Security Limitations

### 1. Podcast Feed Validation

podx trusts RSS feed content (titles, descriptions, audio URLs). When processing untrusted feeds:
- Use isolated working directories
- Validate URLs before downloading
- Consider sandboxing (containers, VMs)

### 2. Third-Party APIs

podx integrates with external services:
- OpenAI API (for transcription and analysis)
- Anthropic API (for analysis)
- Notion API (for publishing)
- YouTube (for downloads)

**User responsibility**: Validate API provider security practices and terms of service.

### 3. Audio File Processing

Audio files are processed using:
- `soundfile` (libsndfile)
- `ffmpeg` (via yt-dlp)
- `faster-whisper` (CTranslate2)

**Recommendation**: Only process audio from trusted sources.

## Security Audit History

| Date       | Version | Auditor         | Result |
|------------|---------|-----------------|--------|
| 2025-01-19 | 1.0.0   | Internal Review | PASS   |

Next audit scheduled: After v1.1 or 6 months (whichever comes first)

## Security-Related Configuration

### Recommended Production Setup

```bash
# Use dedicated user
useradd -m -s /bin/bash podx-worker

# Restrict file permissions
chmod 700 /home/podx-worker/.podx/
chmod 600 /home/podx-worker/.env

# Use environment-specific configs
export PODX_CONFIG=/etc/podx/production.yaml

# Enable structured logging
export PODX_LOG_FORMAT=json
export PODX_LOG_LEVEL=WARNING

# Monitor logs
tail -f /var/log/podx/production.log | jq .
```

## Contact

For security-related questions (non-vulnerability):
- GitHub Discussions: https://github.com/yourusername/podx/discussions
- General email: contact@yourproject.com

For security vulnerabilities:
- Security email: security@yourproject.com

---

**Last updated**: 2025-01-19
**Policy version**: 1.0
