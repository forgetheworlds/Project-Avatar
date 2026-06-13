**EchoPilot** is an open-source voice control architecture that enables operators to control **PX4-powered drones** using natural language commands. It leverages Anthropic’s **Model Context Protocol (MCP)** to standardise drone commands as discoverable tools, **LangGraph** for multi-step mission orchestration, and an **LLM** for parsing conversational intents. `[85][86][87][88][89][90]`

---

🌐 System Architecture Overview 

The EchoPilot architecture removes the need to hard-code strict api integrations for unique drone actions. Instead, it uses a decoupled three-layer approach to process voice inputs and convert them into hardware-level flight operations: `[79][80][81][82][83][84]`

```
  [ Human Operator ] 🗣️ Voice Command ("Take off, orbit the bridge, and land")
         │
         ▼
 ┌────────────────────────────────────────────────────────┐
 │ 🎙️  Voice/LLM Layer                                    │
 │    • STT (Speech-to-Text) -> Text Prompt               │
 │    • Ollama / Local LLM (Intention & Parameter Parsing)│
 └───────┬────────────────────────────────────────────────┘
         │ Text Context
         ▼
 ┌────────────────────────────────────────────────────────┐
 │ 🗺️  Orchestration Layer (LangGraph Host)              │
 │    • Compiles intents into a structured DAG state graph│
 │    • Resolves conditional execution & flight safety     │
 └───────┬────────────────────────────────────────────────┘
         │ JSON-RPC Tool Requests
         ▼
 ┌────────────────────────────────────────────────────────┐
 │ 🔌  Hardware Interface Layer (MCP Server)              │
 │    • Exposes MAVSDK-Python commands as standard tools  │
 │    • Translates requests into MAVLink packets          │
 └───────┬────────────────────────────────────────────────┘
         │ MAVLink Protocol
         ▼
  [ 🛸  PX4 Flight Controller ] (Physical Drone / SITL Simulation)

```

---

🧱 Core Components 

1. The MCP Server Layer (The Hardware Wrapper) 

The system exposes core flight mechanics as standard JSON-RPC tools through an **MCP Server**. It wraps around **MAVSDK-Python**, acting as a direct bridge to any drone speaking the ubiquitous **MAVLink protocol** (like PX4 and ArduPilot). `[73][74][75][76][77][78]`

* **Discoverable Tools**: The server automatically broadcasts available flight primitives to the LLM. `[67][68][69][70][71][72]`
* **Core Exposed Primitives**:
  + `takeoff(altitude: float)`
  + `goto_location(latitude: float, longitude: float, altitude: float)`
  + `orbit(radius: float, velocity: float)`
  + `land()`
  + `get_telemetry()` (Battery status, GPS lock, altitude checks) `[61][62][63][64][65][66]`

2. The LangGraph Layer (The Flight Planner) 

Instead of executing linear tool calls, EchoPilot uses **LangGraph** to construct a stateful Directed Acyclic Graph (DAG) for mission generation. `[55][56][57][58][59][60]`

* **Deterministic Execution Chains**: A verbal phrase like *"Fly to the bridge, orbit it, then land there"* is compiled by LangGraph into a multi-node sequence: `[takeoff]`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

 `[fly_to_coordinates]`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

 `[orbit]`
  
  <!-- MathML: <math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mo>→</mo><annotation encoding="text/plain">right arrow</annotation></semantics></math> --> →right arrow

 `[land]`. `[49][50][51][52][53][54]`
* **Conditional Logic**: If the drone's telemetry detects low battery (`get_telemetry`), LangGraph routes execution away from the destination node and triggers an automated `[return_to_launch]` or emergency landing sequence. `[43][44][45][46][47][48]`

3. Voice & LLM Integration (The Natural Interface) 

* **Local Processing**: Typically integrated with local engines like **Ollama** (e.g., Llama 3 or Qwen architectures) to preserve low-latency, privacy-first edge execution without cloud fees. `[37][38][39][40][41][42]`
* **Zero-Shot Parameterization**: The LLM extracts implied variables from conversational instructions (e.g., matching the word *"bridge"* to predefined geographical coordinates stored in an environmental database). `[31][32][33][34][35][36]`

---

🛠️ Execution Lifecycle Example 

When an operator provides a multi-step instruction, EchoPilot routes the request through the following loop: 

1. **Transcription & Parsing**: The operator speaks to the system. The voice engine transcribes the request, and the LLM maps intents to the tool definitions dynamically broadcasted by the **MCP Server**. `[25][26][27][28][29][30]`
2. **Graph Compilation**: **LangGraph** creates a structured plan state containing the steps required to fulfil the instruction safely. `[19][20][21][22][23][24]`
3. **Execution & Validation**: LangGraph steps through each node, passing the target tool calls to the **MCP Client**. `[13][14][15][16][17][18]`
4. **Hardware Command**: The MCP Server runs the underlying Python MAVSDK code, sending low-level command packets directly down to the **PX4 Flight Controller** over serial, telemetry radio, or a local network connection. `[7][8][9][10][11][12]`

---

📈 Technical Advantages 

* **LLM Agnostic**: Because the hardware capabilities are decoupled via standard MCP specifications, you can hot-swap the underlying AI model (from local Ollama instances to cloud models) without altering any drone control code.
* **Safety Context Injection**: System states and flight fences are directly provided to the AI agent via the protocol, preventing the model from outputting impossible commands (e.g., setting altitudes that violate local aviation rules).
* **Extensible Ecosystem**: Multi-server connections allow you to plug in a **Google Maps MCP server** alongside the **Drone MCP server** to fetch live navigation data simultaneously. `[1][2][3][4][5][6]`

If you would like to implement or modify this architecture, let me know if you plan to run it on **physical drone hardware** or within a **SITL (Software In The Loop) simulation** environment! 

Copy

# Share public link

This public link is valid for 7 days and shares a thread, including any personal information you added. This link or copies made by others cannot be deleted. If you share with third parties, their policies apply.

Can’t copy the link right now. Try again later.

Facebook

Gmail

X

Reddit

WhatsApp

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

A copy of this chat, including the images and video, will be included with your feedback

A copy of this chat will be included with your feedback

Your feedback will include a copy of this chat and the image from your search

Your feedback will include a copy of this chat, any links you shared, and the image from your search.

Thanks for letting us know

Google may use account and system data to understand your feedback and improve our services, subject to our [Privacy Policy](https://policies.google.com/privacy) and [Terms of Service](https://policies.google.com/terms). For legal issues, [make a legal removal request](https://support.google.com/legal/answer/3110420).

---

## Sources:

[1] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[2] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[3] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[4] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[5] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[6] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[7] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[8] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[9] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[10] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[11] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[12] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[13] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[14] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[15] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[16] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[17] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[18] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[19] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[20] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[21] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[22] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[23] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[24] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[25] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[26] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[27] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[28] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[29] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[30] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[31] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[32] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[33] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[34] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[35] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[36] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[37] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[38] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[39] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[40] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[41] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[42] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[43] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[44] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[45] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[46] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[47] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[48] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[49] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[50] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[51] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[52] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[53] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[54] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[55] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[56] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[57] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[58] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[59] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[60] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[61] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[62] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[63] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[64] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[65] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[66] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[67] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[68] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[69] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[70] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[71] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[72] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[73] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[74] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[75] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[76] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[77] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[78] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[79] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[80] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[81] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[82] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[83] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[84] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

[85] LangGraph + MCP Server for Natural Language PX4 Control. Opens in new tab.  
https://discuss.px4.io/t/echopilot-langgraph-mcp-server-for-natural-language-px4-control/46998

[86] A Universal Large Language Model - Drone Command and Control .... Opens in new tab.  
https://arxiv.org/html/2601.15486v2

[87] A Beginner’s Guide to Using MCP with LangGraph | by Damilola Oyedunmade | AI Engineering BootCamp | Medium. Opens in new tab.  
https://medium.com/ai-engineering-bootcamp/a-beginners-guide-to-using-mcp-with-langgraph-47624f8c4580

[88] Build Multi-Agent System with MCP on LangGraph. Opens in new tab.  
https://www.youtube.com/watch?v=OnG5E9WHbbs

[89] Engineering Agentic Workflows: With MCP and LangGraph. Opens in new tab.  
https://dzone.com/articles/engineering-agentic-workflows-mcp-langgraph

[90] A Step-by-Step Guide to Integrating MCP Servers with LangGraph. Opens in new tab.  
https://medium.com/@amolkavitkar/building-an-advanced-ai-agent-a-step-by-step-guide-to-integrating-mcp-servers-with-langgraph-ff5f1d9db6e6

