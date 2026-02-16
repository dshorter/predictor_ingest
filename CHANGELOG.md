# Changelog

All notable changes to this project will be documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project uses [PEP 440](https://peps.python.org/pep-0440/) versioning.

## [0.1.0b1] — 2026-02-16

First beta release.

### Features
- RSS ingestion pipeline with configurable feeds (arXiv, Hugging Face, OpenAI)
- HTML cleaning and metadata extraction (readability, boilerplate removal)
- LLM-based entity and relation extraction with JSON Schema validation
- Semi-manual extraction workflow via ChatGPT copy/paste (Mode B)
- Entity resolution with alias merging and similarity matching
- Cytoscape.js graph export (mentions, claims, dependencies, trending views)
- Trend scoring: velocity, novelty, bridge signals, mention counts
- Interactive web client with desktop and mobile support
- SQLite-backed document and entity storage
- Daily pipeline orchestration via Makefile
- CI/CD with GitHub Actions (test + deploy)

### Known Limitations
- No persistent node positions (force-directed layout on each load)
- Entity resolution is basic (string similarity, no Wikidata linking yet)
- No staging environment in CI/CD pipeline
- Scale limited to < 5,000 nodes in the web client
