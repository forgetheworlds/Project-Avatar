---
name: google-ai-mode-skill
description: Use when the Project Avatar flight deck operator asks for current documentation, API references, simulator/drone research, mapping/geospatial research, hardware compatibility, or web-cited technical information.
---

# Google AI Mode Skill

Use this for current web research with citations. The installed skill lives at:

```bash
/Users/muadhsambul/.agents/skills/google-ai-mode
```

## Command
Always run through the skill wrapper:

```bash
cd /Users/muadhsambul/.agents/skills/google-ai-mode
python scripts/run.py search.py --query "QUERY" --save --debug
```

## Query Rules
- Optimize the query before searching.
- Include the current year for current APIs/hardware/simulator questions.
- Ask for structured results with citations.
- Use this for docs, PX4/Gazebo/MAVSDK issues, camera streaming options, mapping APIs, regulations, and hardware compatibility.

## Output Rules
- Summarize the answer.
- Include cited source links from the saved result.
- If no AI overview appears or CAPTCHA blocks the search, report that limitation and the saved log path.

