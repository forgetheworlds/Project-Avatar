# Hermes Research Archive — Project Avatar

**What is this?** This is where all external research lives — papers, benchmarks, competitor analysis, and technical findings that guide Project Avatar's direction.

**Updated:** Automatically every night at 4 AM by Hermes (the research agent)

---

## Quick Access

### Core Research Topics

| Topic | File | Key Finding | Confidence |
|-------|------|-------------|------------|
| **Open-source Landscape** | [01-opensource-px4-llm-landscape.md](01-opensource-px4-llm-landscape.md) | Very few PX4+LLM open-source projects; Avatar's MCP approach is unique | Medium |
| **Academic Papers** | [02-arxiv-llm-uav-research.md](02-arxiv-llm-uav-research.md) | 17 papers analyzed; MCP protocol emerging as standard; 4-layer safety validated | High |
| **SITL on macOS** | [03-gazebo-macos-sitl-viability.md](03-gazebo-macos-sitl-viability.md) | Native Gazebo broken; use Docker x86_64 or SIH | High |
| **Offboard Control** | [04-mavsdk-offboard-best-practices.md](04-mavsdk-offboard-best-practices.md) | Must pre-stream setpoint; 20Hz target; clean finally cleanup | High |
| **Vision Performance** | [05-yolov8-rpi4-benchmarks.md](05-yolov8-rpi4-benchmarks.md) | RPi 4: 2 FPS stock, 5-7 FPS with NCNN; 10 FPS needs RPi 5 or Hailo-8L | High |

### Deep Code Analysis

**Location:** [`analysis/`](analysis/)

When research finds relevant open-source projects, I **clone and analyze their actual code**:

- Architecture patterns they use
- How they handle PX4/LLM/vision/safety
- Code quality and lessons learned
- Specific files worth studying

**After analysis:** Repos are deleted to save space (analysis lives on)

**Example:** `analysis/echopilot-2026-04-14.md` — What EchoPilot did, what Avatar can learn

### Nightly Research Log

**Location:** [`nightly/`](nightly/)

Each morning, a new file appears here: `YYYY-MM-DD-research.md`

**What's inside:** 5 self-directed research questions + findings + actionable recommendations

**How to read:**
- Skim the 5 questions at the top
- Read the "Relevance to Avatar" and "Recommended Actions" sections
- Check "Confidence" rating (High = act on this; Low = interesting but verify)

---

## How to Use This Archive

### Finding Research

```bash
# List all research files
ls -la ~/downloads/project-avatar/hermes/

# Search within research
grep -r "YOLOv8" ~/downloads/project-avatar/hermes/
grep -r "10 FPS" ~/downloads/project-avatar/hermes/
grep -r "MCP protocol" ~/downloads/project-avatar/hermes/

# Read latest nightly research
ls -t ~/downloads/project-avatar/hermes/nightly/*.md | head -1 | xargs cat
```

### Quick Navigation by Topic

| If you're working on... | Read these files |
|------------------------|------------------|
| Simulator setup | `03-gazebo-macos-sitl-viability.md` |
| Offboard velocity control | `04-mavsdk-offboard-best-practices.md` |
| Vision pipeline (Stage 2) | `05-yolov8-rpi4-benchmarks.md` + `02-arxiv-llm-uav-research.md` (vision-language section) |
| Safety architecture | `02-arxiv-llm-uav-research.md` (safety papers) |
| MCP protocol design | `02-arxiv-llm-uav-research.md` (MCP paper) + `01-opensource-px4-llm-landscape.md` |
| Hardware decisions (RPi 4 vs 5) | `05-yolov8-rpi4-benchmarks.md` |
| Competitive analysis | `01-opensource-px4-llm-landscape.md` |

### Tracking Research Quality

Each file ends with a meta-reflection section that tracks:
- What search queries worked
- Source quality
- Confidence in findings
- Suggestions for future research

---

## Morning Briefing

**What:** Every morning at ~6 AM (after 4 AM research run), a summary appears in your chat

**Contains:**
- 1-sentence summary of each of the 5 findings
- 1-2 most important findings highlighted
- Link to full research file

**How to give feedback:**
```
"Research quality: 4/5" — I'll learn what topics to prioritize
"This finding was wrong: [explanation]" — I'll correct my understanding
"Research [topic] next" — I'll add it to tomorrow's queue
```

---

## Research Methodology

**How research is generated:**
1. **Assess** — Read project files to understand current state
2. **Generate** — Identify 5 high-impact questions  
3. **Research** — Use Perplexity (Comet MCP), arXiv, web search
4. **Synthesize** — Convert to actionable findings
5. **Analyze** — Clone and study relevant open-source projects (if found)
6. **Deliver** — Write to file + update memories

**Time budget:** ~2-3 hours per night (analysis adds ~1 hour when projects found)

**Quality criteria:**
- **High confidence:** Multiple credible sources, consistent findings, recent (2024-2026)
- **Medium confidence:** Some uncertainty, fewer sources, or older research
- **Low confidence:** Single source, conflicting info, or speculation

---

## Active Research Threads

These are ongoing areas of investigation:

1. **Simulator viability on macOS** — Alternative to broken native Gazebo
2. **Vision pipeline optimization** — Achieving 10 FPS on edge devices
3. **LLM safety guardrails** — Academic best practices for robotics
4. **MAVSDK patterns** — Proven approaches for PX4 offboard control
5. **Competitive landscape** — Other projects building PX4+LLM systems

---

## How to Request Custom Research

Want something specific researched? Tell me:

```
"Hermes, research [topic] for me"

Example:
"Hermes, research ROS2 vs direct MAVSDK latency benchmarks"
"Hermes, research latest Hailo-8L performance for YOLO"
"Hermes, research PX4 parameter tuning for cinematic shots"
```

I'll do an immediate deep-dive and add to this archive.

## Directory Structure

```
hermes/
├── README.md                    ← This index
├── FEEDBACK_GUIDE.md            ← How to give feedback
├── 01-opensource-px4-llm-landscape.md  ← Core research files
├── 02-arxiv-llm-uav-research.md
├── 03-gazebo-macos-sitl-viability.md
├── 04-mavsdk-offboard-best-practices.md
├── 05-yolov8-rpi4-benchmarks.md
├── analysis/                    ← Deep code analysis of other projects
│   ├── echopilot-2026-04-14.md
│   └── [project]-[date].md
└── nightly/
    ├── YYYY-MM-DD-research.md   ← Auto-generated research
    ├── YYYY-MM-DD-research.md
    └── FEEDBACK_TEMPLATE.md
```

- **Index:** 2026-04-13
- **Latest research:** 2026-04-13 (5 foundational research files)
- **Next automatic research:** Tonight at 4 AM

---

*This archive is maintained by Hermes (GLM-5.1). For questions about research methodology or to suggest topics, just ask.*
