**Hermes Agent** is a persistent, self-improving AI framework developed by [Nous Research](https://github.com/NousResearch/hermes-agent). Released in early 2026, it is designed to grow with the user by autonomously creating skills and maintaining a deepening model of user preferences across sessions. 

Key Features 

* **Self-Improving Learning Loop**: The only agent with a built-in cycle that creates new skills from experience and improves them during use.
* **Persistent Memory**: Uses FTS5 session search and "Honcho" dialectic user modeling to recall past conversations and build a continuous model of the user.
* **Multi-Channel Access**: Accessible via a unified gateway on Telegram, Discord, Slack, WhatsApp, Signal, and a terminal TUI.
* **Model Agnostic**: Supports 200+ models via OpenRouter, Nous Portal, or local endpoints like VLLM/SGLang with zero code changes.
* **Autonomous Skill Creation**: Converts complex tasks into reusable "Skills" (instructions + shell commands) that it can call in future sessions. 

Architecture 

Hermes is currently a **single-agent system** that uses **delegation** rather than true peer-to-peer multi-agent orchestration. 

* **Parent-Child Delegation**: The main Hermes agent can spawn "throwaway" child agents for specific tasks using a `delegate_task` function. These children work in isolation and return summaries to the parent.
* **Gateway Layer**: A single process manages connections to multiple messaging platforms simultaneously.
* **Hybrid Backend**: Can run on everything from a $5 VPS to a GPU cluster, with support for local-model friendliness and ephemeral cloud execution. 

Comparison: Hermes vs. OpenClaw 

| Feature `[7][8][9]` | Hermes Agent | [OpenClaw](https://www.meta-intelligence.tech/en/insight-openclaw-multi-agent) |
| --- | --- | --- |
| **Orchestration** | Single agent with task delegation. | Native multi-agent (Orchestrator, P2P, Hierarchical). |
| **Philosophy** | "Grows with you"; focuses on long-term memory. | Automation engine for complex parallel workflows. |
| **Configuration** | Dynamic skill creation and TUI-based config. | Declarative YAML-based configuration. |
| **Learning** | Built-in learning loop for skill improvement. | Minimal focus on self-improvement; focused on execution. |
| **Hardware** | Runs on low-cost VPS or cloud VMs. | Often requires more local power (e.g., Mac minis). |

Setup Guide 

Follow these steps to install Hermes Agent from the official GitHub repository: `[4][5][6]`

1. **Clone the Repository**:
  bash
  

``` git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git cd hermes-agent

```
  Use code with caution.

Copied to clipboard

2. **Initialize Environment**: Install the `uv` package manager and create a Python 3.11 virtual environment.
  bash
  

``` curl -LsSf https://astral.sh/uv/install.sh | sh uv venv venv --python 3.11

```
  Use code with caution.

Copied to clipboard

3. **Install Dependencies**: Use `[all]` to include messaging and cron support.
  bash
  

``` export VIRTUAL_ENV="$(pwd)/venv" uv pip install -e ".[all]" uv pip install -e "./mini-swe-agent"  # Terminal tool backend

```
  Use code with caution.

Copied to clipboard

4. **Configuration**: Create the required directory structure and configuration files.
  bash
  

``` mkdir -p ~/.hermes/{cron,sessions,logs,memories,skills} cp cli-config.yaml.example ~/.hermes/config.yaml touch ~/.hermes/.env

```
  Use code with caution.

Copied to clipboard

5. **Set API Keys**: Add your OpenRouter or other provider key to `~/.hermes/.env`.
  bash
  

``` echo "OPENROUTER_API_KEY=sk-or-v1-your-key" >> ~/.hermes/.env

```
  Use code with caution.

Copied to clipboard

6. **Verify & Launch**:
  bash
  

``` hermes doctor  # Diagnoses your setup hermes model   # Interactively select your LLM hermes         # Start chatting

```
  Use code with caution.

Copied to clipboard

 `[1][2][3]`

Would you like help configuring the **Telegram gateway** or setting up **custom skills** for a specific workflow? 

Copy

Creating a public link...

Good response

Bad response

Thank you

Your feedback helps Google improve. See our [Privacy Policy](https://policies.google.com/privacy?hl=en).

Share more feedbackReport a problemClose

---

## Sources:

[1] NousResearch/hermes-agent: The agent that grows with you. Opens in new tab.  
https://github.com/NousResearch/hermes-agent#:~:text=Hermes%20Agent%20%E2%98%A4,Honcho%20dialectic%20user%20modeling.

[2] Feature: Multi-Agent Architecture — Orchestration ... - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/issues/344#:~:text=What%20%22multi%2Dagent%20Hermes%22,other's%20work%2C%20and%20iterate%20together

[3] README.md - NousResearch/hermes-agent - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/blob/main/README.md#:~:text=The%20fully%20open%2Dsource%20AI,generation%20of%20tool%2Dcalling%20models.

[4] NousResearch/hermes-agent: The agent that grows with you. Opens in new tab.  
https://github.com/NousResearch/hermes-agent#:~:text=Hermes%20Agent%20%E2%98%A4,Honcho%20dialectic%20user%20modeling.

[5] Feature: Multi-Agent Architecture — Orchestration ... - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/issues/344#:~:text=What%20%22multi%2Dagent%20Hermes%22,other's%20work%2C%20and%20iterate%20together

[6] README.md - NousResearch/hermes-agent - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/blob/main/README.md#:~:text=The%20fully%20open%2Dsource%20AI,generation%20of%20tool%2Dcalling%20models.

[7] NousResearch/hermes-agent: The agent that grows with you. Opens in new tab.  
https://github.com/NousResearch/hermes-agent#:~:text=Hermes%20Agent%20%E2%98%A4,Honcho%20dialectic%20user%20modeling.

[8] Feature: Multi-Agent Architecture — Orchestration ... - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/issues/344#:~:text=What%20%22multi%2Dagent%20Hermes%22,other's%20work%2C%20and%20iterate%20together

[9] README.md - NousResearch/hermes-agent - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/blob/main/README.md#:~:text=The%20fully%20open%2Dsource%20AI,generation%20of%20tool%2Dcalling%20models.

