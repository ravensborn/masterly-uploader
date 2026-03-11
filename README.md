# R2 Video Uploader — Dev Environment

A Docker-based development environment for building a PySide6 desktop app that converts videos via FFmpeg and uploads them to Cloudflare R2 with resumable multipart uploads.

## What's Included

- **Python 3.12** with boto3, PySide6, ffmpeg-python
- **FFmpeg** for video conversion
- **Claude Code** (native installer) for AI-assisted development

## Quick Start

```bash
# 1. Clone / enter the project
cd r2-uploader

# 2. Copy and fill in your credentials
cp .env.example .env
# Edit .env with your R2 keys

# 3. Create upload/output dirs
mkdir -p uploads output

# 4. Build and start
docker compose build
docker compose up -d

# 5. Enter the container
docker compose exec r2-uploader bash

# 6. Inside the container — verify tools
ffmpeg -version
python -c "import PySide6; print('PySide6 OK')"
claude --version
```

## Using Claude Code Inside the Container

```bash
# Interactive login (first time)
claude

# Or set ANTHROPIC_API_KEY in .env for API key auth
```

## GUI on Linux

The compose file mounts the X11 socket so PySide6 windows display on your host. Make sure to run:

```bash
xhost +local:docker
```

## GUI on Windows

For Windows, you have two options:

1. **WSL2 + WSLg** (Windows 11) — GUI works automatically
2. **VcXsrv / X410** — Install an X server, set `DISPLAY` in `.env`

## Project Structure

```
r2-uploader/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── uploads/          # Drop files here to upload
├── output/           # FFmpeg converted files land here
└── src/              # Your app code goes here
```
