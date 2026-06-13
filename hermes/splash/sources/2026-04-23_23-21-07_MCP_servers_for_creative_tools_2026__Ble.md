In 2026, the Model Context Protocol (MCP) has significantly expanded its ecosystem for creative tools, allowing LLMs to directly control software interfaces via standardized server implementations.  **MCP Servers for Creative Tools (2026)** 

* **Blender**:
  + **Blender-MCP-Server**: A comprehensive server exposing 50+ tools for complete Blender control via API. It enables prompt-assisted 3D modeling and scene manipulation.
  + **mcp_link_blender**: Available as a Blender extension or zip file, allowing AI to drive Blender directly.
  + **Integration**: Typically involves installing a Blender add-on and running a local Node/Python server to bridge the connection.
* **DaVinci Resolve**:
  + **davinci-resolve-mcp**: A server that utilizes a universal installer to auto-detect installations and configure the MCP client in one step.
  + **Resolver**: A lightweight, open-source CLI that bridges Resolve's API to Claude and other LLMs.
  + **Integration**: Requires DaVinci Resolve to be running while the server is active.
* **Adobe After Effects**:
  + **after-effects-mcp**: A TypeScript-based server that provides an integration layer for After Effects.
  + **Integration**: Requires installing a bridge script and configuring a `.env` file for local communication.
* **Adobe Premiere Pro**:
  + **Adobe_Premiere_Pro_MCP**: An MCP server that uses a CEP (Common Extensibility Platform) bridge to execute commands within Premiere.
  + **adb-mcp**: A multi-app proxy that handles both Photoshop and Premiere through a Node-based command proxy.
  + **Integration**: Users must enable the "MCP Bridge" extension within Premiere Pro's Window > Extensions menu.
* **Figma**:
  + **Figma Context**: Provides AI coding agents with simplified layout information and layer context via MCP.
  + **Canva MCP Server**: While primarily for Canva, it is often listed alongside Figma for broader creative design automation.  **GitHub Repositories & Integration Guides** 

| Tool `[7][8][9][10][11][12]` | GitHub Repository | Primary Integration Method |
| --- | --- | --- |
| **Blender** | [llm-use/Blender-MCP-Server](https://github.com/llm-use/Blender-MCP-Server) | Blender Add-on + Local Server |
| **DaVinci Resolve** | [samuelgursky/davinci-resolve-mcp](https://github.com/samuelgursky/davinci-resolve-mcp) | Python-based Installer |
| **After Effects** | [Dakkshin/after-effects-mcp](https://github.com/Dakkshin/after-effects-mcp) | Bridge Script + Node.js |
| **Premiere Pro** | [hetpatel-11/Adobe_Premiere_Pro_MCP](https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP) | CEP Extension |
| **Premiere Pro** | [leancoderkavy/premiere-pro-mcp](https://github.com/leancoderkavy/premiere-pro-mcp) | npm / Manual CEP Symlink | **General Integration Steps** 

1. **Environment Setup**: Most creative MCP servers require **Node.js** or **Python** (specifically using tools like [uv](https://github.com/astral-sh/uv) for dependency management).
2. **Server Activation**: Clone the repository and run the startup command (e.g., `npm start` or `python main.py`) to initialize the transport layer (usually **stdio** for local use).
3. **Client Configuration**: Add the server's path to your AI client's configuration file (e.g., `claude_desktop_config.json`) to grant the LLM access to the tools. 

If you'd like, I can: 

* Provide a **step-by-step config snippet** for a specific AI client (like Claude Desktop or Cursor).
* Detail the **specific tools/commands** available in one of these servers.
* Help you **troubleshoot** a specific installation error. `[1][2][3][4][5][6]`

Copy

Creating a public link...

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

[1] punkpeye/awesome-mcp-servers: A collection of ... - GitHub. Opens in new tab.  
https://github.com/punkpeye/awesome-mcp-servers#:~:text=Tips%20&%20Tricks-,What%20is%20MCP?,integrations%2C%20and%20other%20contextual%20services.

[2] Build ANYTHING with MCP Servers - Coding Tutorial. Opens in new tab.  
https://www.youtube.com/watch?v=sMqlObpNz64

[3] 10 Best MCP Servers for coding in 2026 | The Jotform Blog. Opens in new tab.  
https://www.jotform.com/ai/agents/best-mcp-servers/#:~:text=an%20MCP%20server?-,The%20best%20MCP%20servers%20for%20AI%20assistants%20and%20builders,React%20MCP%20Server

[4] ahujasid/blender-mcp - GitHub. Opens in new tab.  
https://github.com/ahujasid/blender-mcp#:~:text=Usage%20*%20In%20Blender%2C%20go%20to%20the,MCP%20server%20is%20running%20in%20your%20terminal.

[5] MCP server integration for DaVinci Resolve - GitHub. Opens in new tab.  
https://github.com/samuelgursky/davinci-resolve-mcp#:~:text=Quick%20Start,client%20%E2%80%94%20all%20in%20one%20step.

[6] Adobe Premiere Pro MCP Server - GitHub. Opens in new tab.  
https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP#:~:text=Confirm%20Premiere%20Pro%20is%20open,Retry%20the%20command.

[7] punkpeye/awesome-mcp-servers: A collection of ... - GitHub. Opens in new tab.  
https://github.com/punkpeye/awesome-mcp-servers#:~:text=Tips%20&%20Tricks-,What%20is%20MCP?,integrations%2C%20and%20other%20contextual%20services.

[8] Build ANYTHING with MCP Servers - Coding Tutorial. Opens in new tab.  
https://www.youtube.com/watch?v=sMqlObpNz64

[9] 10 Best MCP Servers for coding in 2026 | The Jotform Blog. Opens in new tab.  
https://www.jotform.com/ai/agents/best-mcp-servers/#:~:text=an%20MCP%20server?-,The%20best%20MCP%20servers%20for%20AI%20assistants%20and%20builders,React%20MCP%20Server

[10] ahujasid/blender-mcp - GitHub. Opens in new tab.  
https://github.com/ahujasid/blender-mcp#:~:text=Usage%20*%20In%20Blender%2C%20go%20to%20the,MCP%20server%20is%20running%20in%20your%20terminal.

[11] MCP server integration for DaVinci Resolve - GitHub. Opens in new tab.  
https://github.com/samuelgursky/davinci-resolve-mcp#:~:text=Quick%20Start,client%20%E2%80%94%20all%20in%20one%20step.

[12] Adobe Premiere Pro MCP Server - GitHub. Opens in new tab.  
https://github.com/hetpatel-11/Adobe_Premiere_Pro_MCP#:~:text=Confirm%20Premiere%20Pro%20is%20open,Retry%20the%20command.

