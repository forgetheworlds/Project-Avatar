# workflow
- User writes all code themselves; assistant should act as mentor/reference-desk: explain concepts, provide API references and syntax patterns, review code, but never generate or write files. Confidence: 0.90
- Learning order for this project: C++ firmware first, then Python (ground station), then JavaScript (phone app). Confidence: 0.80

# project-context
- The goal is to build a portfolio project for a research position at TMU's ELIXIR Lab (embodied AI, RL, neural networks, real robots). Frame work as research contributions, not hobby projects. Confidence: 0.85
- Core research pitch: LLM-planned + RL-executed hierarchical controller on a physical USV (autonomous surface vessel), with measurable sim-to-real transfer, deployed on an ESP32-S3 microcontroller. Confidence: 0.80
- User is computer engineering (not mechatronics/mechanical). Focus discussions on software, control, AI/ML, and embedded systems. De-emphasize CAD, mechanical design, and physical fabrication topics. Confidence: 0.75
- CAD and mechanical design are acceptable as AI-assisted tasks but are not the user's passion or desired area of depth. When physical design is needed, treat it as something AI tools handle so the user can focus on software/embedded/ML. Confidence: 0.70
- Long-term career direction: hardware — specifically designing custom chips for local AI inference (VLAs, vision models, LLMs) in embodied systems. Software is becoming commoditized; hardware/ASIC design for on-device AI is the defensible path. Confidence: 0.70

# compute
- Compute available: M3 MacBook Pro 16GB unified RAM + Oracle VPS (24GB RAM, 4-core AMD CPU). No GPU. Cloud API for LLM inference. CPU-based RL (PPO/SAC on low-dim state) is feasible. Confidence: 0.75

# subagents
- Delegate subagents using DeepSeek Flash model unless explicitly specified otherwise. Be liberal with subagent usage — prefer delegating over doing everything in main context. Confidence: 0.80

# research
- When asked for factual, institution-specific, or current information (professors, programs, opportunities, course details), do actual web research rather than answering from general knowledge. Confidence: 0.65
- Use Google AI Mode as the primary research tool for web research tasks. Confidence: 0.70

# communication-style
- Avoid hype and overpromising. Don't frame the user's projects as equivalent to professional/industrial efforts — err on the side of humility. The user knows their own level and doesn't need inflated comparisons. Confidence: 0.70

