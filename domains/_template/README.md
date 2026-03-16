# Domain Template

Copy this directory to create a new domain:

```bash
cp -r domains/_template domains/<your-domain>
```

Then:

1. **Discover** — Read 20–30 representative documents from your domain
2. **Edit `domain.yaml`** — Fill in entity types, relations, ID prefixes, suppressed entities
3. **Edit `prompts/`** — Customize system/user prompts for your domain vocabulary
4. **Edit `feeds.yaml`** — Add RSS feeds relevant to your domain
5. **Edit `views.yaml`** — Configure which relations appear in each graph view
6. **Generate tense variants** — Auto-populate mechanical normalization entries:
   ```bash
   python scripts/generate_normalization.py domains/<your-domain>/domain.yaml --apply
   ```
   Review the generated block and remove any entries that conflict with
   domain-specific meanings. Then add semantic synonyms manually.
7. **Validate**: `python -m pytest tests/test_domain_profile.py`
8. **Run**: `make daily DOMAIN=<your-domain>`

See `domains/ai/` for a complete working example and
`docs/fix-details/new-domain-lessons-learned.md` for setup guidance.
