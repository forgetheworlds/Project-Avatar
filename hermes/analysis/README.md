# Deep Code Analysis Archive

**What is this?** When nightly research finds relevant open-source projects, I clone them and analyze their actual code — architecture, patterns, lessons learned. Then I delete the repos to save space (these reports are the only thing kept).

**Value:** Learn from what others have built without maintaining their code.

---

## How Analysis Works

1. **Find** — Research identifies promising GitHub repos
2. **Clone** — Download to `/tmp/` for analysis
3. **Analyze** — Study: structure, dependencies, key files, patterns
4. **Report** — Write findings to this folder
5. **Clean** — Delete repo, keep only the analysis

---

## What You Get

Each analysis file includes:

- **Project Overview** — What it does, stack used
- **Architecture** — How components connect
- **Key Files** — Important files and what they do
- **What They Did Well** — Patterns worth adopting
- **What They Did Poorly** — Mistakes to avoid
- **Lessons for Avatar** — Specific actionable takeaways
- **Comparison** — Their approach vs Avatar's approach

---

## Reading Analyses

```bash
# List all analyses
ls ~/downloads/project-avatar/hermes/analysis/

# Read specific analysis
cat ~/downloads/project-avatar/hermes/analysis/echopilot-2026-04-14.md

# Search across all analyses
grep -r "MAVSDK" ~/downloads/project-avatar/hermes/analysis/
grep -r "safety" ~/downloads/project-avatar/hermes/analysis/
```

---

## Analysis Selection Criteria

I only analyze projects that:
- Are directly relevant to Avatar's current challenges
- Have >100 stars or recent activity
- Demonstrate something Avatar hasn't built yet
- Are worth learning from (good or bad examples)

---

*This folder is auto-populated by nightly research when relevant projects are found.*
