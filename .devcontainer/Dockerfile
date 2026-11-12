FROM mcr.microsoft.com/devcontainers/python:1-3.11-bookworm

USER root

# Node 24 is supplied by the Dev Container feature, rather than Debian's older Node.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        poppler-utils \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-ron \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

USER vscode
