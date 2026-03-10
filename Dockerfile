FROM python:3.12-slim

# Avoid interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# ─── System dependencies ───
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FFmpeg for video conversion
    ffmpeg \
    # Qt6 runtime dependencies
    libgl1 \
    libegl1 \
    libxkbcommon0 \
    libdbus-1-3 \
    libfontconfig1 \
    libfreetype6 \
    libx11-xcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-cursor0 \
    libxcb-xkb1 \
    libxkbcommon-x11-0 \
    # General tools
    curl \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# ─── Claude Code (native installer) ───
RUN curl -fsSL https://claude.ai/install.sh | bash

# Make claude available in PATH for all users
ENV PATH="/root/.claude/bin:/root/.local/bin:${PATH}"

# ─── Python dependencies ───
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─── Application code ───
COPY . .

# Default command — drop into shell for development
CMD ["bash"]
