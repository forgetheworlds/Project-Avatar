As of March 2026, the

[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent) is an open-source AI agent designed to "grow with you" by building a persistent memory of your projects and skills. It transitioned from a single-agent system with basic delegation to a more robust **multi-agent architecture** in early 2026. 

Key Features 

* **Self-Improving Learning Loop**: Unlike standard chatbots, it creates **Skill Documents** (searchable markdown files) from experience. It improves these skills during use and builds a deepening model of the user across sessions.
* **Omnipresent Gateway**: You can interact with the agent via **Telegram, Discord, Slack, WhatsApp, and CLI** from a single gateway process. You can start a task on one platform and pick it up on another.
* **Flexible Execution Backends**: It supports five sandboxed environments to run tasks: **Local, Docker, SSH, Singularity, and Modal**.
* **Natural Language Automation**: Users can schedule autonomous tasks (like daily reports or backups) using plain English cron schedules.
* **Model Agnostic**: Compatible with any model via Nous Portal, OpenRouter, or custom vLLM/SGLang endpoints. 

Multi-Agent Capabilities (2026 Update) `[1][2][3]`

While initial versions focused on a single agent, the 2026 updates introduced: 

* **Subagent Delegation**: The ability to spawn parallel subagents for isolated workstreams, each with its own terminal and Python RPC scripts.
* **Specialized Roles**: Support for agents with distinct identities and toolsets, such as specialized researchers, coders, or reviewers.
* **Orchestration & Cooperation**: Development of structured workflows where agents share context and iterate together rather than working in total isolation. 

Technical Specifications 

* **Base Model**: Optimized for **Hermes-3** (and the latest **Hermes 4** series) fine-tuned with Atropos RL for high tool-call accuracy.
* **Tool Integration**: Includes over 40 built-in tools for web search, file system access, browser automation, and image generation.
* **License**: Released under the **MIT License**. 

Would you like help with **installation instructions** for a specific backend like Docker, or are you looking for **configuration examples** for the multi-agent orchestration? 

Copy

Creating a public link...

Good response

Bad response

Thank you

Your feedback helps Google improve. See our [Privacy Policy](https://policies.google.com/privacy?hl=en).

Share more feedbackReport a problemClose

---

## Sources:

[1] Hermes Agent - Nous Research. Opens in new tab.  
https://hermes-agent.nousresearch.com/#:~:text=hermes-,Features,Modal%2C%20Daytona%2C%20or%20Singularity.

[2] README.md - NousResearch/hermes-agent - GitHub. Opens in new tab.  
https://github.com/NousResearch/hermes-agent/blob/main/README.md#:~:text=Hermes%20Agent%20%E2%9A%95,a%20researched%20answer%20with%20citations.

[3] NousResearch/hermes-agent: The agent that grows with you. Opens in new tab.  
https://github.com/nousresearch/hermes-agent#:~:text=Hermes%20Agent%20%E2%98%A4,works%20on%20a%20cloud%20VM.

