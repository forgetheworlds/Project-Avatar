In 2026, setting up **CLIProxyAPI** to bridge **OpenCode Go** with **Claude Code** allows you to use your existing subscriptions (like OpenCode Zen or Claude Pro) as a universal API endpoint for various coding agents. This is particularly useful for routing **Claude-3.5/4.5** models through a unified local proxy. 

1. Installation of CLIProxyAPI 

To install the proxy, you typically need a [Go environment](https://blog.wenhaofree.com/en/posts/articles/cli-proxy-api-local-setup-guide/). `[4][5][6]`

* **Clone the Repository**:
  bash
  

``` git clone https://github.com/router-for-me/CLIProxyAPI cd CLIProxyAPI

```
  Use code with caution.

* **Compile and Run**: Use Go to build the binary or run the python-based proxy script if using the legacy version. For the modern Go-based **OpenCode Go** integration, you can also use pre-built tools like `oc-go-cc`. 

2. Configuration for OpenCode Go 

OpenCode Go acts as a provider that manages your subscriptions and API keys. `[1][2][3]`

* **Get Your Key**: Sign in to [OpenCode Zen](https://opencode.ai/auth), subscribe to the "Go" plan, and copy your API key.
* **Initial Connect**: Run the `/connect` command in your OpenCode terminal and select **OpenCode Go** to paste your key.
* **Configuration File**: Ensure your `~/.config/opencode/opencode.json` includes the correct provider settings:
  json
  

```
{
  "providers": {
    "opencode-go": {
      "apiKey": "YOUR_OPENCODE_GO_KEY",
      "baseUrl": "https://opencode.ai/zen/go/v1"
    }
  }
}

```
  Use code with caution. 

3. Integrating with Claude Code 

To make **Claude Code** (the official Anthropic CLI) use your local proxy instead of direct Anthropic servers, set the base URL environment variable. 

* **Start the Proxy**:
  bash
  

``` oc-go-cc serve --background

```
  Use code with caution.

* **Set Environment Variables**:
  bash
  

``` export ANTHROPIC_BASE_URL=http://127.0.0.1:3456 export ANTHROPIC_AUTH_TOKEN=unused

```
  Use code with caution.

* **Run Claude**: Simply type `claude` to start a session routed through your proxy. 

4. Advanced Management (Dashboard) 

For easier management, the [CLIProxyAPI Dashboard](https://github.com/0xAstroAlpha/cliProxyAPI-Dashboard) can be used. 

* **Features**: The dashboard offers a web interface for real-time log streaming, OAuth provider integration (for Claude/Gemini/Codex), and automatic config sync with OpenCode via a companion plugin.
* **Authentication**: Use `opencode auth login` to manage credentials for multiple providers like Models.dev or custom local endpoints. 

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

[1] OpenCode Tutorial 2026: Complete Install, Setup ... - NxCode. Opens in new tab.  
https://www.nxcode.io/resources/news/opencode-tutorial-2026

[2] Providers - OpenCode. Opens in new tab.  
https://opencode.ai/docs/providers/

[3] Go - OpenCode. Opens in new tab.  
https://opencode.ai/docs/go/

[4] OpenCode Tutorial 2026: Complete Install, Setup ... - NxCode. Opens in new tab.  
https://www.nxcode.io/resources/news/opencode-tutorial-2026

[5] Providers - OpenCode. Opens in new tab.  
https://opencode.ai/docs/providers/

[6] Go - OpenCode. Opens in new tab.  
https://opencode.ai/docs/go/

