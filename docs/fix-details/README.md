# Fix Details

This directory contains detailed troubleshooting and fix documentation.

## Purpose

When issues are complex enough to warrant detailed documentation beyond a quick summary, they get their own `{ISSUE_NAME}_FIX.md` file here.

## What Goes Here

- Step-by-step fix procedures
- Extensive code examples
- Complete testing workflows
- Long explanations with context
- Screenshots or diagrams (if needed)

## Quick Reference

For concise issue summaries and an index of all fixes, see: [../ux/troubleshooting.md](../ux/troubleshooting.md)

## Current Fix Documents

- **[FCOSE_FIX.md](FCOSE_FIX.md)** - fcose layout extension registration fix (2026-01-27)

## Adding New Fix Documents

1. Get timestamp: `date -u +"%Y-%m-%d %H:%M:%S UTC"`
2. Create `{ISSUE_NAME}_FIX.md` in this directory
3. Add timestamp at the top of the file
4. Add entry to troubleshooting.md with link to this file
5. Add to the "Current Fix Documents" list above
