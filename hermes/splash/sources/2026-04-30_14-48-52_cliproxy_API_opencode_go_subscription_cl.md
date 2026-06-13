To integrate **Claude Code** with **OpenCode Go** using **oc-go-cc** (a specialized CLI proxy), you need to route Claude's API requests to your local proxy server. This setup allows you to use your OpenCode Go subscription (typically $10/month) within the official Claude Code CLI. 

1. Set Up OpenCode Go Subscription `[16][17][18]`

First, ensure you have an active OpenCode Go subscription to get your API key. `[13][14][15]`

* **Sign Up**: Register at the [OpenCode Go](https://opencode.ai/go) website.
* **Subscription**: The plan costs **$5 for the first month**, then **$10/month**.
* **API Key**: Obtain your key from the dashboard (format: `sk-opencode-...`). 

2. Install and Configure the Proxy (`oc-go-cc`) `[10][11][12]`

Since Claude Code expects an Anthropic-compatible API, use the [oc-go-cc](https://github.com/samueltuyizere/oc-go-cc) bridge developed in Go. 

1. **Initialize**: Run the following to create the configuration file:
  bash
  

``` oc-go-cc init

```
  Use code with caution.

2. **Set Environment Variable**: Add your OpenCode key:
  bash
  

``` export OC_GO_CC_API_KEY=sk-opencode-your-key-here

```
  Use code with caution.

3. **Start the Proxy**: Launch the server in the background:
  bash
  

``` oc-go-cc serve --background

```
  Use code with caution.The proxy will typically listen on `http://127.0.0.1:3456`. 

3. Integrate with Claude Code CLI `[7][8][9]`

You must tell Claude Code to use your local proxy instead of Anthropic’s default servers. `[4][5][6]`

1. **Redirect Base URL**: Set these variables in your terminal (or add them to your `.zshrc` / `.bashrc`):
  bash
  

``` export ANTHROPIC_BASE_URL=http://127.0.0.1:3456 export ANTHROPIC_AUTH_TOKEN=unused

```
  Use code with caution.

2. **Run Claude**: Simply type `claude` to start the session. All requests will now route through your OpenCode Go subscription. 

Important 2026 Policy Update 

As of **April 4, 2026**, Anthropic has blocked many third-party harnesses from using standard "Claude Max" web subscriptions for API calls. While **CLIProxyAPI** and similar tools still function as local gateways, you must now use an **API-based billing** method (like OpenCode Go) rather than just a web login to power external CLI agents. 

Comparison Table: 2026 AI Coding Options 

| Provider `[1][2][3]` | Cost (2026) | Best For | Source |
| --- | --- | --- | --- |
| **OpenCode Go** | $10/month | Budget-friendly, reliable open-source models | OpenCode Go |
| **Claude Code (Direct)** | Free (Pro/Max) or API-based | Official experience, high-end models | Anthropic |
| **OpenRouter** | Pay-as-you-go | Accessing 200+ models via one key | OpenRouter Setup |

Would you like the specific **PowerShell commands** for a Windows-based setup or help with **troubleshooting connection errors**? 

AI can make mistakes, so double-check responses

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

[1] OpenCode vs Claude Code: I Tested Both and Here's the .... Opens in new tab.  
https://medium.com/all-about-claude/opencode-vs-claude-code-i-tested-both-and-heres-the-real-difference-2026-c752db8f1806

[2] Use your Claude Max subscription as an API with CLIProxyAPI. Opens in new tab.  
https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/

[3] samueltuyizere/oc-go-cc: Use your OpenCode Go ... - GitHub. Opens in new tab.  
https://github.com/samueltuyizere/oc-go-cc

[4] OpenCode vs Claude Code: I Tested Both and Here's the .... Opens in new tab.  
https://medium.com/all-about-claude/opencode-vs-claude-code-i-tested-both-and-heres-the-real-difference-2026-c752db8f1806

[5] Use your Claude Max subscription as an API with CLIProxyAPI. Opens in new tab.  
https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/

[6] samueltuyizere/oc-go-cc: Use your OpenCode Go ... - GitHub. Opens in new tab.  
https://github.com/samueltuyizere/oc-go-cc

[7] OpenCode vs Claude Code: I Tested Both and Here's the .... Opens in new tab.  
https://medium.com/all-about-claude/opencode-vs-claude-code-i-tested-both-and-heres-the-real-difference-2026-c752db8f1806

[8] Use your Claude Max subscription as an API with CLIProxyAPI. Opens in new tab.  
https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/

[9] samueltuyizere/oc-go-cc: Use your OpenCode Go ... - GitHub. Opens in new tab.  
https://github.com/samueltuyizere/oc-go-cc

[10] OpenCode vs Claude Code: I Tested Both and Here's the .... Opens in new tab.  
https://medium.com/all-about-claude/opencode-vs-claude-code-i-tested-both-and-heres-the-real-difference-2026-c752db8f1806

[11] Use your Claude Max subscription as an API with CLIProxyAPI. Opens in new tab.  
https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/

[12] samueltuyizere/oc-go-cc: Use your OpenCode Go ... - GitHub. Opens in new tab.  
https://github.com/samueltuyizere/oc-go-cc

[13] OpenCode vs Claude Code: I Tested Both and Here's the .... Opens in new tab.  
https://medium.com/all-about-claude/opencode-vs-claude-code-i-tested-both-and-heres-the-real-difference-2026-c752db8f1806

[14] Use your Claude Max subscription as an API with CLIProxyAPI. Opens in new tab.  
https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/

[15] samueltuyizere/oc-go-cc: Use your OpenCode Go ... - GitHub. Opens in new tab.  
https://github.com/samueltuyizere/oc-go-cc

[16] OpenCode vs Claude Code: I Tested Both and Here's the .... Opens in new tab.  
https://medium.com/all-about-claude/opencode-vs-claude-code-i-tested-both-and-heres-the-real-difference-2026-c752db8f1806

[17] Use your Claude Max subscription as an API with CLIProxyAPI. Opens in new tab.  
https://rogs.me/2026/02/use-your-claude-max-subscription-as-an-api-with-cliproxyapi/

[18] samueltuyizere/oc-go-cc: Use your OpenCode Go ... - GitHub. Opens in new tab.  
https://github.com/samueltuyizere/oc-go-cc

