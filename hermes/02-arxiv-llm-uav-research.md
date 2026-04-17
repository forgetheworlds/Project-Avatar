# LLM-Driven UAV/Drone Control: Academic Literature Survey (2023-2026)

> Generated: 2026-04-13 | For: Project Avatar (LLM-driven autonomous drone with natural language control)

---

## Table of Contents

1. [Core LLM-Drone Control Papers](#1-core-llm-drone-control-papers)
2. [PX4 + LLM Integration](#2-px4--llm-integration)
3. [Vision-Language Navigation (VLN) for Drones](#3-vision-language-navigation-vln-for-drones)
4. [Autonomous Drone Cinematography](#4-autonomous-drone-cinematography)
5. [LLM Safety for Robot/Drone Control](#5-llm-safety-for-robotdrone-control)
6. [Human-AI Joint Planning & Elicitation](#6-human-ai-joint-planning--elicitation)
7. [Surveys & Benchmarks](#7-surveys--benchmarks)
8. [Key Takeaways for Project Avatar](#8-key-takeaways-for-project-avatar)

---

## 1. Core LLM-Drone Control Papers

### 1.1 A Universal LLM-Drone Command and Control Interface via MCP

| Field | Value |
|-------|-------|
| **Title** | A Universal Large Language Model -- Drone Command and Control Interface |
| **Authors** | Javier N. Ramos-Silva, Peter J. Burke (UC Irvine) |
| **Year** | 2026 (Jan) |
| **arXiv ID** | 2601.15486 |
| **Code** | https://github.com/PeterJBurke/droneserver (GNU license) |

**Core Contribution:** First universal, LLM-agnostic, and drone-agnostic control interface using the Model Context Protocol (MCP) standard to bridge natural language AI with physical drone command and control via the Mavlink protocol. Demonstrated on both a real UAV and simulated drone with Google Maps MCP integration.

**Architecture/Approach:**
- Cloud-hosted MCP server ("DroneServer") in Python, running on Ubuntu
- Mavlink protocol via MavSDK (high-level abstraction over 155 MavSDK methods; 45 tools exposed = 34 MavSDK + 11 custom)
- Physical: Ardupilot/PX4 flight controller + Raspberry Pi Zero W companion (UART + WiFi), TCP/IP over Tailscale VPN
- **LLMs tested:** Claude 3.5 Sonnet/Opus 4, GPT-4/4 Turbo, Gemini 2.0/2.5, Llama 3.2/3.3 70B, Qwen 2.5 72B, qwen2.5-7b-instruct via LM Studio locally
- **Safety layers:** MavSDK's built-in safety features; custom "wait" tools to prevent sequential command timing issues; monitoring logic built into MCP server for long-duration missions

**Key Results/Benchmarks:**
- Demonstrated stable hover and flight under internet LLM control
- First demonstration of LLM natural language control of a real drone responding to unpredictable/pre-trained world knowledge using MCP
- ~5k tokens consumed by 45 tool definitions (manageable for commercial LLMs; 32k context needed for local 7B models)

**Relevance to Project Avatar: HIGH**
- This is the closest paper to Project Avatar's architecture: MCP protocol, Mavlink, PX4/Ardupilot, real drone control via natural language
- Directly demonstrates feasibility of the MCP-based control approach
- Identified key challenge: LLMs operate in "fire and forget" mode -- not suitable for continuous long-duration monitoring without server-side logic

---

### 1.2 Large Language Model-Driven Closed-Loop UAV Operation with Semantic Observations

| Field | Value |
|-------|-------|
| **Title** | Large Language Model-Driven Closed-Loop UAV Operation with Semantic Observations |
| **Authors** | (IEEE IoT Journal accepted, 2025) |
| **Year** | 2025 |
| **arXiv ID** | 2507.01930 |
| **Code** | Not indicated |

**Core Contribution:** A closed-loop LLM-driven UAV control framework with two LLM modules (Code Generator + Evaluator) that transforms numerical state observations into natural language trajectory descriptions for iterative code refinement and simulation-verified execution before deployment to physical drones.

**Architecture/Approach:**
- Two LLM modules: Code Generator (synthesizes/refines UAV control code) + Evaluator (assesses code performance, provides NL feedback)
- Numerical state observations converted to natural language trajectory descriptions
- Simulation-based refinement loop eliminates risk to physical UAVs during code testing
- Open-loop baseline comparison to validate closed-loop improvement

**Key Results/Benchmarks:**
- Significantly outperforms baseline open-loop approaches in success rate and task completeness
- Performance advantage increases with task complexity
- Published in IEEE IoT Journal (peer-reviewed)

**Relevance to Project Avatar: HIGH**
- Directly addresses the reliability problem of LLM-generated drone code
- Closed-loop feedback + simulation-first approach is critical for safe real-world deployment
- Semantic observation transformation (numeric -> NL) is a pattern Project Avatar should adopt

---

### 1.3 TypeFly: Flying Drones with Large Language Model

| Field | Value |
|-------|-------|
| **Title** | TypeFly: Flying Drones with Large Language Model |
| **Authors** | Guojun Chen, Xiaojing Yu, Lin Zhong |
| **Year** | 2023 (Dec) |
| **arXiv ID** | 2312.14950 |
| **Code** | https://typefly.github.io/ (project page) |

**Core Contribution:** One of the earliest systems to use cloud-based LLMs to generate executable drone programs. Introduces a custom DSL (MiniSpec) instead of Python to reduce token cost and improve code generation reliability.

**Architecture/Approach:**
- Edge-based vision intelligence for scene description
- Custom mini-language (MiniSpec) designed specifically for drone tasks -- LLM writes MiniSpec, not Python
- Cloud-based LLM service generates MiniSpec programs from English task descriptions
- Runtime executes MiniSpec on the drone
- Novel prompt engineering strategy

**Key Results/Benchmarks:**
- 2x reduction in both LLM service cost and task execution time vs. Python-based approaches
- Validated on increasingly challenging drone tasks

**Relevance to Project Avatar: MEDIUM**
- Important early work establishing the NL-to-drone-code paradigm
- DSL approach is relevant: Project Avatar could use a similar abstraction layer between LLM and PX4
- Edge vision intelligence concept aligns with onboard perception needs

---

### 1.4 Next-Generation LLM for UAV: From Natural Language to Autonomous Flight (NeLV)

| Field | Value |
|-------|-------|
| **Title** | Next-Generation LLM for UAV: From Natural Language to Autonomous Flight |
| **Authors** | (Liang Qiyuan et al.) |
| **Year** | 2025 (Oct) |
| **arXiv ID** | 2510.21739 |
| **Code** | https://liangqiyuan.github.io/NeLV/ (project page with code and videos) |

**Core Contribution:** Comprehensive position paper proposing a multi-scale LLM-UAV integration system covering short-, medium-, and long-range UAVs. Introduces a 5-level automation taxonomy from LLM-as-Parser (Level 1) to LLM-as-Autopilot (Level 5).

**Architecture/Approach:**
- 5 technical components: (i) LLM-as-Parser, (ii) Route Planner, (iii) Path Planner, (iv) Control Platform, (v) UAV Monitoring
- Demonstrated on three use cases: multi-UAV patrol, multi-POI delivery, multi-hop relocation
- Addresses regulatory compliance, airport procedures for larger UAVs
- Comprehensive literature review table comparing all prior work

**Key Results/Benchmarks:**
- 10 citations already (significant for a position paper)
- First work to systematically cover medium/long-range UAV with LLM integration
- Roadmap from current state to fully autonomous LLM-as-Autopilot

**Relevance to Project Avatar: HIGH**
- The 5-level automation taxonomy directly informs Project Avatar's development roadmap
- Multi-scale approach (short to long range) aligns with potential Avatar use cases
- Comprehensive literature table is a reference for related work

---

### 1.5 Large Language Models to Enhance Multi-task Drone Operations in Simulated Environments

| Field | Value |
|-------|-------|
| **Title** | Large Language Models to Enhance Multi-task Drone Operations in Simulated Environments |
| **Authors** | Feng, Snoussi et al. |
| **Year** | 2026 (Jan) |
| **arXiv ID** | 2601.08405 |
| **Venue** | DAUS' 2025 (1st Int. Conf. on Drones and Unmanned Systems) |

**Core Contribution:** Fine-tuned CodeT5 model to translate natural language prompts into executable drone code in AirSim simulator, demonstrating multi-task drone control without relying on large commercial LLMs.

**Architecture/Approach:**
- Fine-tuned CodeT5 (not GPT/Claude) for NL-to-drone-code translation
- AirSim (Unreal Engine-based) as simulation environment
- Specialized dataset for simple and complex drone tasks
- Modular, open-source approach

**Key Results/Benchmarks:**
- Validated multi-task operations in realistic simulation
- Demonstrates that smaller, fine-tuned models can handle drone code generation

**Relevance to Project Avatar: MEDIUM**
- Shows alternative to commercial LLMs: fine-tuned CodeT5 can work
- AirSim simulation pipeline is useful for testing
- Open-source and modular approach aligns with Project Avatar philosophy

---

### 1.6 AI-Generated Drone Command and Control Station Hosted in the Sky

| Field | Value |
|-------|-------|
| **Title** | Robot builds a robot's brain: AI generated drone command and control station hosted in the sky |
| **Authors** | (2025) |
| **Year** | 2025 |
| **arXiv ID** | 2508.02962 |

**Core Contribution:** AI-generated command and control system where an LLM creates the drone's own control station, exploring emergent strengths and practical boundaries of AI-driven robot control code generation at current model scales.

**Architecture/Approach:**
- LLM generates the entire C2 station, not just commands
- Explores limits of current model capabilities for drone control
- Analysis of emergent capabilities in AI code generation for robotics

**Relevance to Project Avatar: MEDIUM**
- Relevant for understanding the frontier of what LLMs can generate for drone systems
- Highlights practical boundaries that Project Avatar needs to work within

---

## 2. PX4 + LLM Integration

### 2.1 Taking Flight with Dialogue: Natural Language Control for PX4-based Drone Agent

| Field | Value |
|-------|-------|
| **Title** | Taking Flight with Dialogue: Enabling Natural Language Control for PX4-based Drone Agent |
| **Authors** | (Shoon Kit Lim et al.) |
| **Year** | 2025 (Jun) |
| **arXiv ID** | 2506.07509 |
| **Code** | https://github.com/limshoonkit/ros2-agent-ws (open source) |

**Core Contribution:** Open-source agentic framework integrating PX4-based flight control, ROS2 middleware, and locally hosted models via Ollama, benchmarking 4 LLM families for command generation and 3 VLM families for scene understanding.

**Architecture/Approach:**
- PX4 flight controller + ROS2 middleware + Ollama (local model hosting)
- **LLMs tested:** Gemma3, Qwen2.5, Llama-3.2, DeepSeek-LLM
- **VLMs tested:** Gemma3, Llama3.2-Vision, Llava1.6
- Custom quadcopter hardware platform
- ros-agents framework as foundation

**Key Results/Benchmarks:**
- LLM valid flight command rate: Gemma3/Qwen2.5/Llama-3.2 = 100%; DeepSeek-LLM = 38%
- VLM object detection accuracy: 97-100% across all models
- Best mission success rate: Gemma3 LLM + Gemma3 VLM = 40%
- Simulation and real hardware validation

**Relevance to Project Avatar: HIGH**
- Directly demonstrates PX4 + ROS2 + local LLM (Ollama) -- exactly the stack Project Avatar targets
- Open-source code available for reference
- Benchmark data on LLM/VLM model selection is immediately useful
- 40% mission success rate shows significant room for improvement (opportunity)

---

## 3. Vision-Language Navigation (VLN) for Drones

### 3.1 UAV-VLN: End-to-End Vision Language guided Navigation for UAVs

| Field | Value |
|-------|-------|
| **Title** | UAV-VLN: End-to-End Vision Language guided Navigation for UAVs |
| **Authors** | (ECMR 2025) |
| **Year** | 2025 |
| **arXiv ID** | 2504.21432 |
| **Venue** | Proc. European Conference on Mobile Robots (ECMR), 2025 |

**Core Contribution:** Novel end-to-end VLN framework enabling UAVs to interpret and execute free-form natural language instructions in complex, real-world environments by combining fine-tuned LLMs with open-vocabulary visual grounding.

**Architecture/Approach:**
- Fine-tuned large language models + open-vocabulary visual grounding
- End-to-end pipeline from NL instruction to navigation action
- Minimal task supervision required
- Dynamic environment handling

**Key Results/Benchmarks:**
- Published at ECMR 2025 (peer-reviewed)
- Real-world UAV navigation demonstrations

**Relevance to Project Avatar: HIGH**
- End-to-end VLN is exactly what Project Avatar needs for autonomous navigation
- Open-vocabulary visual grounding enables flexible scene understanding
- Minimal supervision approach reduces data requirements

---

### 3.2 AutoFly: Vision-Language-Action Model for UAV Autonomous Navigation in the Wild

| Field | Value |
|-------|-------|
| **Title** | AutoFly: Vision-Language-Action Model for UAV Autonomous Navigation in the Wild |
| **Authors** | (Xiaolousun et al.) |
| **Year** | 2026 (Feb) |
| **arXiv ID** | 2602.09657 |
| **Venue** | **Accepted at ICLR 2026** |
| **Code** | https://xiaolousun.github.io/AutoFly (model, data, code publicly available) |

**Core Contribution:** End-to-end Vision-Language-Action (VLA) model for autonomous UAV navigation with pseudo-depth encoder for spatial reasoning from RGB, progressive two-stage training strategy, and novel autonomous navigation dataset.

**Architecture/Approach:**
- Pseudo-depth encoder derives depth-aware features from RGB inputs (no depth sensor needed)
- Progressive two-stage training: aligns visual, depth, and linguistic representations with action policies
- Novel dataset shifting paradigm from instruction-following to autonomous behavior modeling
- Real-world data integration + trajectory collection emphasizing obstacle avoidance and planning

**Key Results/Benchmarks:**
- 47.9% success rate vs. OpenVLA 44% vs. RT-2 41.9% (3.9% improvement over prior SOTA)
- Consistent performance across simulated and real environments
- **ICLR 2026 acceptance** -- top-tier venue validates quality

**Relevance to Project Avatar: HIGH**
- State-of-the-art VLA model for UAV navigation
- Pseudo-depth from RGB is critical: eliminates need for expensive depth sensors
- Publicly available model, data, and code -- directly reusable
- Progressive training strategy could inform Project Avatar's training approach

---

### 3.3 SINGER: Onboard Generalist Vision-Language Navigation Policy for Drones

| Field | Value |
|-------|-------|
| **Title** | SINGER: An Onboard Generalist Vision-Language Navigation Policy for Drones |
| **Authors** | Maximilian Adang, JunEn Low, Ola Shorinwa, Mac Schwager (Stanford) |
| **Year** | 2025 (Sep) |
| **arXiv ID** | 2509.18610 |
| **Code** | Not indicated |

**Core Contribution:** Lightweight end-to-end visuomotor policy for real-time closed-loop drone navigation given natural language goal specification, trained entirely on synthetic data with zero-shot sim-to-real transfer, using only onboard sensors and compute.

**Architecture/Approach:**
- Photorealistic language-embedded flight simulator using **Gaussian Splatting** for efficient data generation with minimal sim-to-real gap
- RRT-inspired multi-trajectory generation expert for collision-free navigation demonstrations
- Lightweight end-to-end visuomotor policy (runs fully onboard)
- ~700K-1M observation-action pairs training data
- No external pose estimation required

**Key Results/Benchmarks:**
- +23.33% improvement in query reached (success rate)
- +16.67% improvement in query maintained in FOV
- -10% fewer collisions
- Zero-shot sim-to-real transfer to unseen environments
- Handles unseen language-conditioned goal objects

**Relevance to Project Avatar: HIGH**
- Onboard-only compute requirement aligns with Avatar's real-time constraints
- Gaussian Splatting for training data is an innovative approach
- Zero-shot transfer eliminates need for real-world training data
- Natural language goal specification directly matches Avatar's interface

---

### 3.4 Aerial Vision-Language Navigation with Unified Framework for Spatial, Temporal and Embodied Reasoning

| Field | Value |
|-------|-------|
| **Title** | Aerial Vision-Language Navigation with a Unified Framework for Spatial, Temporal and Embodied Reasoning |
| **Authors** | (2025) |
| **Year** | 2025 (Dec) |
| **arXiv ID** | 2512.08639 |
| **Code** | Not indicated |

**Core Contribution:** Unified aerial VLN framework operating solely on egocentric monocular RGB observations (no depth/odometry/panoramic cameras), formulating navigation as next-token prediction with prompt-guided multi-task learning.

**Architecture/Approach:**
- Monocular RGB-only input (minimal hardware requirements)
- Navigation formulated as next-token prediction problem
- Keyframe selection strategy to reduce visual redundancy
- Action merging and label reweighting for long-tailed supervision
- Joint optimization of spatial perception, trajectory reasoning, and action prediction

**Key Results/Benchmarks:**
- Significantly outperforms existing RGB-only baselines
- Narrows performance gap with panoramic RGB-D counterparts
- Strong results in both seen and unseen environments

**Relevance to Project Avatar: MEDIUM-HIGH**
- Monocular RGB-only approach matches low-cost hardware constraints
- Next-token prediction formulation could leverage LLM architecture directly
- Keyframe selection is useful for bandwidth-constrained scenarios

---

### 3.5 Vision-Language Navigation for Aerial Robots: Towards the Era of Large Language Models (Survey)

| Field | Value |
|-------|-------|
| **Title** | Vision-Language Navigation for Aerial Robots: Towards the Era of Large Language Models |
| **Authors** | (2026) |
| **Year** | 2026 (Apr) |
| **arXiv ID** | 2604.07705 |
| **Code** | Not indicated |

**Core Contribution:** Comprehensive survey (28 pages, 8 figures) covering the intersection of vision-language navigation and aerial robotics, including TypeFly, UAV-VLN, SINGER, and other key works.

**Relevance to Project Avatar: MEDIUM**
- Excellent reference for understanding the VLN landscape for drones
- Categorizes approaches and benchmarks

---

## 4. Autonomous Drone Cinematography

### 4.1 Agentic Aerial Cinematography (ACDC): From Dialogue Cues to Cinematic Trajectories

| Field | Value |
|-------|-------|
| **Title** | Agentic Aerial Cinematography: From Dialogue Cues to Cinematic Trajectories |
| **Authors** | (2025) |
| **Year** | 2025 (Sep) |
| **arXiv ID** | 2509.16176 |
| **Code** | Not indicated |

**Core Contribution:** Autonomous drone cinematography system that converts free-form natural language prompts directly into executable indoor UAV video tours using LLMs and vision foundation models (VFMs), replacing manual waypoint/angle selection.

**Architecture/Approach:**
- Vision-language retrieval pipeline for initial waypoint selection
- Preference-based Bayesian optimization (BO) framework that refines poses using aesthetic feedback
- Motion planner generates safe quadrotor trajectories through refined waypoints
- LLM + VFM combination for intent interpretation and scene understanding
- Inputs: exploratory video + 3D environment model + free-form NL prompt

**Key Results/Benchmarks:**
- Validated in simulation and hardware-in-the-loop experiments
- Professional-quality footage across diverse indoor scenes
- No robotics or cinematography expertise required from users

**Relevance to Project Avatar: HIGH**
- Directly relevant if Project Avatar includes cinematic shot capabilities
- NL-to-trajectory pipeline is transferable to general navigation tasks
- Bayesian optimization for aesthetic refinement is a novel pattern
- VFM + LLM combination is aligned with Avatar's multimodal approach

---

## 5. LLM Safety for Robot/Drone Control

### 5.1 RoboGuard: Safety Guardrails for LLM-Enabled Robots

| Field | Value |
|-------|-------|
| **Title** | Safety Guardrails for LLM-Enabled Robots (RoboGuard) |
| **Authors** | (UPenn/Georgia Tech) |
| **Year** | 2025 (Mar) |
| **arXiv ID** | 2503.07885 |
| **Code** | Referenced in Awesome-LLM-Robotics list |

**Core Contribution:** Two-stage guardrail architecture (monitoring + intervention) using formal control synthesis to ensure LLM-generated robot plans comply with safety specifications, resolving conflicts between safety constraints and LLM outputs.

**Architecture/Approach:**
- Stage 1: Monitoring layer evaluates LLM-generated plans against safety specifications
- Stage 2: Intervention layer uses formal control synthesis to modify plans if unsafe
- Resolves conflicts between safety specs and LLM-generated actions
- Tested on Clearpath Jackal robot with GPT-4o-based online LLM planner

**Key Results/Benchmarks:**
- Simulation and real-world validation
- Demonstrates that formal methods can be integrated with LLM planning

**Relevance to Project Avatar: HIGH**
- Critical for safe deployment: formal safety guarantees around LLM outputs
- Two-stage architecture (monitor + intervene) is a pattern Avatar should adopt
- GPT-4o planner reference shows real-time LLM planning is feasible

---

### 5.2 Safe LLM-Controlled Robots with Formal Guarantees via Reachability Analysis

| Field | Value |
|-------|-------|
| **Title** | Safe LLM-Controlled Robots with Formal Guarantees via Reachability Analysis |
| **Authors** | Hafez et al. |
| **Year** | 2025 (Mar) |
| **arXiv ID** | 2503.03911 |
| **Code** | Available (per Awesome-LLM-Robotics) |

**Core Contribution:** Data-driven reachability analysis framework providing formal safety guarantees for LLM-controlled robots, ensuring all possible system trajectories remain within safe operational limits without requiring explicit analytical models.

**Architecture/Approach:**
- Data-driven reachability analysis (not model-based -- uses historical data)
- Constructs reachable sets of states for the robot-LLM system
- Validates LLM navigation commands against reachable safe state sets
- No explicit analytical robot model required

**Key Results/Benchmarks:**
- Effective at mitigating risks from LLM-generated commands
- Validates through autonomous navigation and task planning case studies
- Addresses the 19-29% performance degradation from adversarial prompt modifications

**Relevance to Project Avatar: HIGH**
- Formal safety guarantees without requiring precise robot models -- critical for real drones
- Data-driven approach works with real-world uncertain dynamics
- Directly applicable to Avatar's PX4-based system

---

### 5.3 Modular Safety Guardrails for Foundation-Model-Enabled Robots

| Field | Value |
|-------|-------|
| **Title** | Modular Safety Guardrails Are Necessary for Foundation-Model-Enabled Robots in the Real World |
| **Authors** | (2026) |
| **Year** | 2026 (Feb) |
| **arXiv ID** | 2602.04056 |

**Core Contribution:** Characterizes FM-enabled robot safety along three dimensions (action safety, decision safety, human-centered safety) and argues for modular guardrail architectures with monitoring and intervention layers, including cross-layer co-design opportunities.

**Architecture/Approach:**
- Three safety dimensions: action safety (physical), decision safety (semantic), human-centered safety (intent alignment)
- Modular guardrails: monitoring (evaluation) + intervention layers
- Cross-layer co-design: representation alignment + conservatism allocation
- Argues against monolithic end-to-end learned policies for safety-critical systems

**Relevance to Project Avatar: HIGH**
- Provides a principled framework for designing Avatar's safety architecture
- Three-dimensional safety model is comprehensive
- Modular approach aligns with Avatar's layered architecture
- Argument against end-to-end approaches supports Avatar's hierarchical design

---

## 6. Human-AI Joint Planning & Elicitation

### 6.1 MINT: Reasoning Knowledge-Gap in Drone Planning via LLM-based Active Elicitation

| Field | Value |
|-------|-------|
| **Title** | Reasoning Knowledge-Gap in Drone Planning via LLM-based Active Elicitation |
| **Authors** | (2026) |
| **Year** | 2026 (Mar) |
| **arXiv ID** | 2603.07824 |
| **Code** | Not indicated |

**Core Contribution:** Paradigm shift from control handover to active information elicitation when facing uncertainties. MINT (Minimal Information Neuro-Symbolic Tree) uses LLMs to formulate optimal binary queries that resolve planning ambiguities with minimal human interaction.

**Architecture/Approach:**
- 3-stage pipeline: Object-driven uncertainty identification (VLM + semantic map) -> Knowledge-gap reasoning via MINT tree -> Active elicitation and plan refinement
- Binary query generation maximizing information gain: q* = argmax_q H(T) - E[H(T|y)]
- Voice interface (STT/TTS) for natural human interaction
- VLM for semantic perception + neuro-symbolic reasoning + low-level UAV controller
- Validated in NVIDIA Isaac simulation AND real-world deployment

**Key Results/Benchmarks:**
- Simulation: 100% success rate (vs 77% pure LLM baseline) with only 1.4 avg queries (vs 2.0 exhaustive)
- Real world: 100% success (vs 35% baseline) in 20 trials
- ~20.7 second trajectory latency
- Natural voice interaction felt intuitive to operators

**Relevance to Project Avatar: HIGH**
- Active elicitation is a powerful interaction model for Avatar
- Voice interface + VLM + reasoning stack matches Avatar's planned architecture
- Real-world validation with 100% success rate is impressive
- Neuro-symbolic reasoning (combining neural perception with symbolic planning) is architecturally relevant

---

## 7. Surveys & Benchmarks

### 7.1 Large Language Model-Assisted UAV Operations and Communications: A Multifaceted Survey and Tutorial

| Field | Value |
|-------|-------|
| **Title** | Large Language Model-Assisted UAV Operations and Communications: A Multifaceted Survey and Tutorial |
| **Authors** | (2026) |
| **Year** | 2026 (Feb) |
| **arXiv ID** | 2602.19534 |

**Core Contribution:** Comprehensive survey covering LLM adaptation techniques (pretraining, fine-tuning, RAG, prompt engineering), reasoning capabilities (CoT, ICL), UAV operations (navigation, planning, swarm, safety), multimodal LLMs for human-swarm interaction, and ethical considerations including HITL strategies.

**Relevance to Project Avatar: MEDIUM**
- Excellent reference for RAG, prompt engineering, and CoT techniques applicable to drone control
- Covers ethical considerations and HITL design
- 172K+ chars -- extremely thorough

---

### 7.2 UAVs Meet LLMs: Comprehensive GitHub Repository

| Field | Value |
|-------|-------|
| **URL** | https://github.com/Hub-Tian/UAVs_Meet_LLMs |
| **Stars** | 460 |
| **License** | MIT |

**Core Contribution:** Living survey paper/repository covering LLMs, VLMs, VFMs, environmental perception, navigation, planning, flight control, and infrastructure for UAV-LLM integration. Includes categorized papers across all subdomains.

**Relevance to Project Avatar: MEDIUM**
- Excellent ongoing reference to track new papers
- Categorized taxonomy helps identify relevant sub-areas

---

## 8. Key Takeaways for Project Avatar

### Architecture Patterns Emerging from Literature

1. **MCP Protocol is the emerging standard** (arXiv 2601.15486): The Model Context Protocol provides a universal, LLM-agnostic interface to drone hardware. Project Avatar should adopt MCP as its primary control interface.

2. **Closed-loop refinement is essential** (arXiv 2507.01930): Open-loop LLM code generation is unreliable. A feedback loop with an evaluator LLM + simulation verification before real-world deployment is critical.

3. **PX4 + ROS2 +  is a proven stack** (arXiv 2506.07509): This exact combination has been demonstrated.  are the top-performing local models.

4. **Vision-Language-Action (VLA) models are the frontier** (arXiv 2602.09657 - ICLR 2026): End-to-end VLA models with pseudo-depth from RGB represent the state of the art for autonomous navigation.

6. **Active elicitation outperves passive control** (arXiv 2603.07824): When uncertain, asking the human a minimal binary question achieves 100% success vs 35-77% for passive approaches.

### Recommended Architecture for Project Avatar

```
[Human NL Input]
       |
  [LLM Planner] (GPT-4o / Claude / Gemma3) -- via MCP Protocol
       |
  [Code Generator] --> [Simulator Verification] <-- [Evaluator LLM]
       |                       |
       |  (closed-loop         |  (retry if failed)
       |   refinement)         |
       v                       v
  [Safety Guardrail Layer]  (RoboGuard + Reachability Analysis)
       |
  [PX4 Flight Controller] <-- ROS2 Middleware
       |
  [Drone Hardware]
```

### Priority Papers to Read/Implement

| Priority | Paper | arXiv ID | Why |
|----------|-------|----------|-----|
| 1 | Universal LLM-Drone MCP Interface | 2601.15486 | MCP architecture directly applicable |
| 2 | Taking Flight with PX4 + Dialogue | 2506.07509 | Same PX4+ROS2+Ollama stack, open-source code |
| 3 | Closed-Loop UAV Operation | 2507.01930 | Reliability pattern for code generation |
| 4 | AutoFly (ICLR 2026) | 2602.09657 | SOTA VLA model with code available |
| 5 | RoboGuard Safety | 2503.07885 | Formal safety guardrail pattern |
| 6 | MINT Active Elicitation | 2603.07824 | Human-AI interaction for uncertain scenarios |
| 7 | SINGER Onboard VLN | 2509.18610 | Zero-shot sim-to-real onboard policy |
| 8 | ACDC Cinematography | 2509.16176 | NL-to-cinematic trajectory pipeline |
| 9 | NeLV Multi-Scale System | 2510.21739 | Automation roadmap and taxonomy |
| 10 | Modular Safety Guardrails | 2602.04056 | Safety architecture design principles |

### Open Challenges Identified

- **Continuous control**: Current LLMs are request-response, not suitable for real-time continuous drone control (2601.15486)
- **Context window**: Tool definitions consume ~5k tokens; limits local model options (2601.15486)
- **Low success rates**: Even the best PX4+LLM system achieves only 40% mission success (2506.07509) -- significant room for improvement
- **Sim-to-real gap**: Most systems validated primarily in simulation; real-world deployment remains challenging
- **No MCP + PX4 integrated solution yet**: The MCP paper uses Mavlink/MavSDK; the PX4 paper uses ROS2/Ollama -- no paper combines both

---

*This survey covers 17 papers across 7 categories. The field is rapidly evolving with significant activity in 2025-2026. Project Avatar has an opportunity to be among the first to combine MCP protocol + PX4 + closed-loop LLM refinement + formal safety guardrails in an integrated system.*
