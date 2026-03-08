# Domain Template

Copy this directory to create a new domain:

```bash
cp -r domains/_template domains/<your-domain>
```

Then:

1. Edit `domain.yaml` — fill in entity types, relations, ID prefixes, suppressed entities
2. Edit `prompts/` — customize system/user prompts for your domain vocabulary
3. Edit `feeds.yaml` — add RSS feeds relevant to your domain
4. Edit `views.yaml` — configure which relations appear in each graph view
5. Validate: `python -m pytest tests/test_domain_profile.py`
6. Run: `make daily --domain <your-domain>`

See `domains/ai/` for a complete working example.
