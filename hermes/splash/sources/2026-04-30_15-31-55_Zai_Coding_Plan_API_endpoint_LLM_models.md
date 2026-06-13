As of April 2026, the **Z.ai Coding Plan** provides a dedicated API endpoint and high-usage quotas for developers using frontier models like **GLM-5.1** and **GLM-5-Turbo**. This subscription is specifically designed for integration with coding agents and IDEs, offering an OpenAI-compatible interface to streamline workflows.  **API Endpoint and Model Access** 

To use the Coding Plan via third-party tools, you must often override the default Z.ai base URL with the specific coding PAAS endpoint: `[7][8][9]`

* **API Base URL**: `https://api.z.ai/api/coding/paas/v4`
* **Authentication**: Uses a standard API key generated in the [Z.ai Developer Dashboard](https://docs.z.ai/guides/overview/quick-start). `[4][5][6]` **Available Models (2026)** 

The following models are primarily supported through the Coding Plan: 

* **GLM-5.1**: Flagship "Agentic Engineering" model, benchmarked at approximately 94.6% of Claude Opus 4.6's performance.
* **GLM-5-Turbo**: High-speed variant optimized for rapid code generation.
* **GLM-4.7 / 4.5-Air**: Legacy and lightweight models for simpler tasks or reduced quota consumption.
* **GLM-5V-Turbo**: Multimodal model specialized for visual programming tasks.  **Subscription Tiers & Usage Limits** 

The Z.ai Coding Plan uses a recurring subscription model (Lite, Pro, Max) rather than pure pay-as-you-go pricing for these specific endpoints. 

| Plan Tier `[1][2][3]` | Price (Approx.) | 5-Hour Prompt Limit | Weekly Prompt Limit |
| --- | --- | --- | --- |
| **Lite Plan** | $10–18 / month | ~80 prompts | ~400 prompts |
| **Pro Plan** | Varies | ~400 prompts | ~2,000 prompts |
| **Max Plan** | ~$80 / month | ~1,600 prompts | ~8,000 prompts | **Critical Usage Policies** 

* **Coding Only**: [Z.ai](https://z.ai/) enforces an aggressive **coding-only policy**. Using these endpoints for general-purpose chat or non-coding tasks can lead to temporary throttling or permanent account bans after three violations.
* **Concurrency Limits**: Many users report strict concurrency limits (often 1) regardless of the plan tier, which can lead to `429 Rate Limit` errors during heavy multi-agent use.
* **Fair Use**: Subscriptions are for individuals only; sharing API keys or credentials across organizations is prohibited.  **Integration Highlights** 

The [Z.ai Developer Documentation](https://docs.z.ai/devpack/tool/others) provides specific setup guides for 20+ tools: 

* **Claude Code / Cline**: Native support by updating model names to `GLM-5.1` or `GLM-5` in local configuration files.
* **Cursor**: Requires setting the "Override OpenAI Base URL" to the PAAS endpoint and entering model names in **uppercase** (e.g., `GLM-5.1`).
* **Mastra**: Supports a built-in model router using the `zai-coding-plan/` prefix. 

Would you like the specific **JSON configuration** for a particular IDE like Cursor or VS Code to get started? 

Copy

Creating a public link...

Share

Good response

Bad response

Saved time

Clear

Helpful

Comprehensive

Other

Incorrect

Inappropriate

Not working

Unhelpful

Other

A copy of this chat will be included with your feedback

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] Overview - Z.AI DEVELOPER DOCUMENT. Opens in new tab.  
https://docs.z.ai/devpack/overview

[2] Quick Start - Overview - Z.AI DEVELOPER DOCUMENT. Opens in new tab.  
https://docs.z.ai/guides/overview/quick-start

[3] Z.AI (Zhipu AI) - liteLLM. Opens in new tab.  
https://docs.litellm.ai/docs/providers/zai

[4] Overview - Z.AI DEVELOPER DOCUMENT. Opens in new tab.  
https://docs.z.ai/devpack/overview

[5] Quick Start - Overview - Z.AI DEVELOPER DOCUMENT. Opens in new tab.  
https://docs.z.ai/guides/overview/quick-start

[6] Z.AI (Zhipu AI) - liteLLM. Opens in new tab.  
https://docs.litellm.ai/docs/providers/zai

[7] Overview - Z.AI DEVELOPER DOCUMENT. Opens in new tab.  
https://docs.z.ai/devpack/overview

[8] Quick Start - Overview - Z.AI DEVELOPER DOCUMENT. Opens in new tab.  
https://docs.z.ai/guides/overview/quick-start

[9] Z.AI (Zhipu AI) - liteLLM. Opens in new tab.  
https://docs.litellm.ai/docs/providers/zai

