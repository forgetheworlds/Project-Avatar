# Ollama Tool Calling & ReAct Patterns for LLM-Driven Drone Control

## Executive Summary

This research document provides comprehensive patterns for implementing safe, local LLM-driven drone control using Ollama's tool calling API with Llama 3, combined with the ReAct (Reasoning + Acting) agent pattern. The focus is on safety-critical implementations with proper constraints, validation, and emergency controls.

---

## 1. Ollama Tool Calling API

### 1.1 Core API Structure

Ollama supports function calling through the `/api/chat` endpoint with a `tools` parameter. The API follows OpenAI-compatible format but runs entirely locally.

#### Basic Tool Definition

```python
from typing import Dict, Any, List, Callable
import requests
import json

# Ollama API endpoint
OLLAMA_URL = "http://localhost:11434/api/chat"

# Tool definition schema
def create_drone_tool(
    name: str,
    description: str,
    parameters: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create a tool definition for Ollama tool calling.

    Args:
        name: Function name (must match the callable)
        description: Clear description for the LLM
        parameters: JSON Schema for function parameters

    Returns:
        Tool definition dict for Ollama API
    """
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": parameters,
                "required": list(parameters.keys())
            }
        }
    }

# Example drone control tools
DRONE_TOOLS = [
    create_drone_tool(
        name="takeoff",
        description="Initiate drone takeoff to a specified altitude. "
                    "Safety: Only works when on ground, altitude 1-30m.",
        parameters={
            "altitude": {
                "type": "number",
                "description": "Target altitude in meters (1-30)",
                "minimum": 1,
                "maximum": 30
            }
        }
    ),
    create_drone_tool(
        name="land",
        description="Safely land the drone at current position or home location. "
                    "Emergency stop will override this if triggered.",
        parameters={
            "location": {
                "type": "string",
                "enum": ["current", "home"],
                "description": "Landing location preference"
            }
        }
    ),
    create_drone_tool(
        name="move_relative",
        description="Move drone relative to current position. "
                    "Max 10m per command for safety. Will be rejected if exceeds bounds.",
        parameters={
            "forward": {
                "type": "number",
                "description": "Meters forward (positive) or backward (negative)",
                "minimum": -10,
                "maximum": 10
            },
            "right": {
                "type": "number",
                "description": "Meters right (positive) or left (negative)",
                "minimum": -10,
                "maximum": 10
            },
            "up": {
                "type": "number",
                "description": "Meters up (positive) or down (negative)",
                "minimum": -10,
                "maximum": 10
            }
        }
    ),
    create_drone_tool(
        name="get_status",
        description="Get current drone telemetry including battery, GPS, altitude, and state.",
        parameters={}
    ),
    create_drone_tool(
        name="emergency_stop",
        description="IMMEDIATE emergency stop - cuts power and initiates emergency landing. "
                    "This is the nuclear option. Use only in life-threatening situations.",
        parameters={
            "reason": {
                "type": "string",
                "description": "Reason for emergency stop (logged for analysis)"
            }
        }
    )
]
```

### 1.2 Multi-Turn Conversation Patterns

Tool calling requires a conversation loop where the LLM decides to call tools, the system executes them, and results are fed back.

```python
from typing import Optional
from dataclasses import dataclass
from enum import Enum

class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

@dataclass
class Message:
    role: MessageRole
    content: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_name: Optional[str] = None

class OllamaChatClient:
    """Client for Ollama chat API with tool calling support."""

    def __init__(self, model: str = "llama3.1:8b", url: str = OLLAMA_URL):
        self.model = model
        self.url = url
        self.conversation_history: List[Dict] = []

    def chat(
        self,
        user_message: str,
        tools: Optional[List[Dict]] = None,
        system_prompt: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """
        Send a chat message to Ollama with optional tool support.

        Args:
            user_message: The user's input
            tools: List of tool definitions (enables tool calling)
            system_prompt: System instructions for the LLM
            stream: Whether to stream the response

        Returns:
            API response dict
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history
        messages.extend(self.conversation_history)

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream
        }

        if tools:
            payload["tools"] = tools

        response = requests.post(self.url, json=payload, stream=stream)
        response.raise_for_status()

        if stream:
            return self._handle_streaming(response)
        else:
            return response.json()

    def _handle_streaming(self, response) -> Dict[str, Any]:
        """Handle streaming response from Ollama."""
        full_content = ""
        tool_calls = []

        for line in response.iter_lines():
            if line:
                chunk = json.loads(line)
                if "message" in chunk and "content" in chunk["message"]:
                    full_content += chunk["message"]["content"]
                if "message" in chunk and "tool_calls" in chunk["message"]:
                    tool_calls.extend(chunk["message"]["tool_calls"])

        return {
            "message": {
                "content": full_content,
                "tool_calls": tool_calls if tool_calls else None
            }
        }

    def add_tool_result(self, tool_name: str, result: str):
        """Add a tool result to the conversation history."""
        self.conversation_history.append({
            "role": "tool",
            "name": tool_name,
            "content": result
        })

    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
```

### 1.3 JSON Mode and Structured Outputs

Ollama supports structured JSON outputs through the `format` parameter.

```python
from pydantic import BaseModel, Field
from typing import Literal

class DroneActionResponse(BaseModel):
    """Structured response from drone control agent."""
    action: Literal["execute", "clarify", "reject", "emergency"]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    safety_checks_passed: List[str]
    safety_concerns: List[str]

class TelemetryData(BaseModel):
    """Structured telemetry data."""
    altitude: float = Field(ge=0, le=500)
    battery_percent: float = Field(ge=0, le=100)
    gps_sats: int = Field(ge=0, le=20)
    latitude: float
    longitude: float
    speed: float = Field(ge=0)
    heading: float = Field(ge=0, le=360)
    state: Literal["grounded", "taking_off", "flying", "landing", "emergency"]

def get_structured_response(
    prompt: str,
    output_schema: Dict[str, Any],
    model: str = "llama3.1:8b"
) -> Dict[str, Any]:
    """
    Get a structured JSON response from Ollama.

    Args:
        prompt: The input prompt
        output_schema: JSON schema dict for output validation
        model: Model to use

    Returns:
        Parsed JSON response
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "format": output_schema,
        "stream": False
    }

    response = requests.post(
        "http://localhost:11434/api/generate",
        json=payload
    )
    response.raise_for_status()
    result = response.json()

    # Parse the structured response
    return json.loads(result["response"])

# Example usage with Pydantic schema
def analyze_flight_safety(telemetry: TelemetryData) -> DroneActionResponse:
    """Use LLM to analyze if a proposed action is safe."""
    schema = DroneActionResponse.model_json_schema()

    prompt = f"""
    Analyze the following drone telemetry and determine if continuing flight is safe:

    Telemetry:
    - Altitude: {telemetry.altitude}m
    - Battery: {telemetry.battery_percent}%
    - GPS Satellites: {telemetry.gps_sats}
    - State: {telemetry.state}
    - Speed: {telemetry.speed} m/s

    Consider:
    1. Battery level (emergency if < 20%)
    2. GPS lock quality (need 6+ sats for precision)
    3. Current state
    4. Any anomalies

    Provide your analysis in the requested JSON format.
    """

    return get_structured_response(prompt, schema)
```

### 1.4 System Prompt Engineering for Safety

```python
DRONE_SYSTEM_PROMPT = """You are an AI control system for an autonomous drone. Your primary objective is SAFE OPERATION above all else.

## Core Principles (in order of priority):
1. HUMAN SAFETY: Never take actions that could harm people
2. PROPERTY SAFETY: Avoid damage to property when possible
3. MISSION SUCCESS: Complete assigned tasks safely
4. EFFICIENCY: Optimize for battery and time

## Operational Constraints:
- Maximum altitude: 120m (legal limit in most jurisdictions)
- Maximum speed: 15 m/s in open areas, 5 m/s near obstacles
- Minimum battery for landing: 20%
- Emergency stop available for immediate use

## Tool Calling Protocol:
1. ANALYZE: Consider the request and current state
2. REASON: Think through the safest approach (output reasoning)
3. VALIDATE: Check against safety constraints
4. ACT: Call appropriate tool if safe
5. OBSERVE: Wait for result before next action

## Safety Override Conditions (trigger emergency_stop):
- Uncontrolled descent detected
- Heading toward no-fly zone
- Battery below 15%
- Communication loss > 5 seconds
- Human in immediate danger

## Response Format:
For every request, provide:
- Your reasoning process
- Safety assessment
- Confidence level (0-1)
- Tool calls only if ALL checks pass

Remember: It is ALWAYS better to ask for clarification than to take an unsafe action.
"""
```

---

## 2. ReAct (Reasoning + Acting) Pattern

### 2.1 Explicit Thought Steps

The ReAct pattern combines reasoning traces (thoughts) with actions in an interleaved manner.

```python
from typing import TypedDict, Annotated, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import re

@dataclass
class ReActStep:
    """A single step in the ReAct loop."""
    step_number: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict] = None
    observation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)

class ReActAgent:
    """
    ReAct agent with safety constraints for drone control.

    ReAct Loop:
    1. Thought: Reason about the current state and goal
    2. Action: Execute a tool based on reasoning
    3. Observation: Receive and process the result
    4. Repeat until goal achieved or max iterations
    """

    def __init__(
        self,
        llm_client: OllamaChatClient,
        tools: Dict[str, Callable],
        max_iterations: int = 10,
        safety_checker: Optional[Callable] = None
    ):
        self.llm = llm_client
        self.tools = tools
        self.max_iterations = max_iterations
        self.safety_checker = safety_checker or self._default_safety_check
        self.history: List[ReActStep] = []

    def _default_safety_check(
        self,
        action: str,
        params: Dict,
        context: Dict
    ) -> tuple[bool, str]:
        """
        Default safety validation for drone actions.

        Returns:
            (is_safe, reason)
        """
        # Critical safety checks
        if action == "emergency_stop":
            return True, "Emergency stop always allowed"

        if context.get("emergency_triggered"):
            return False, "Emergency state active - only emergency_stop allowed"

        if context.get("battery", 100) < 15:
            return False, "Battery critically low - must land"

        if action in ["move_relative", "move_absolute"]:
            # Check altitude bounds
            if params.get("up", 0) + context.get("altitude", 0) > 120:
                return False, "Would exceed maximum altitude (120m)"

            # Check speed bounds
            speed = params.get("speed", 0)
            if speed > 15:
                return False, f"Speed {speed} exceeds max (15 m/s)"

        return True, "Safety checks passed"

    def _build_react_prompt(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> str:
        """Build the ReAct prompt with history."""
        prompt = f"""You are a ReAct agent controlling a drone. Follow this exact format:

Goal: {goal}

Current Context:
{json.dumps(context, indent=2)}

Available Tools:
{self._format_tools()}

Previous Steps:
{self._format_history()}

Now respond using this EXACT format:

Thought: [Your detailed reasoning about the current situation and what to do next]
Action: [Tool name from available tools, or "FINISH" if goal is complete]
Action Input: [JSON object with tool parameters, or final answer if FINISH]

Remember:
1. ALWAYS start with "Thought:"
2. Follow with "Action:" and "Action Input:"
3. Use only available tools
4. Be specific about safety considerations
"""
        return prompt

    def _format_tools(self) -> str:
        """Format available tools for the prompt."""
        return "\n".join([
            f"- {name}: {tool.__doc__ or 'No description'}"
            for name, tool in self.tools.items()
        ])

    def _format_history(self) -> str:
        """Format conversation history."""
        if not self.history:
            return "None yet."

        lines = []
        for step in self.history:
            lines.append(f"Step {step.step_number}:")
            lines.append(f"  Thought: {step.thought}")
            if step.action:
                lines.append(f"  Action: {step.action}")
                lines.append(f"  Input: {step.action_input}")
            if step.observation:
                lines.append(f"  Observation: {step.observation}")
        return "\n".join(lines)

    def _parse_response(self, response: str) -> tuple[str, str, Dict]:
        """
        Parse the ReAct format response.

        Returns:
            (thought, action, action_input)
        """
        thought_match = re.search(r"Thought:\s*(.+?)(?=\nAction:|$)", response, re.DOTALL)
        action_match = re.search(r"Action:\s*(.+?)(?=\nAction Input:|$)", response, re.DOTALL)
        input_match = re.search(r"Action Input:\s*(.+?)(?=\n|$)", response, re.DOTALL)

        thought = thought_match.group(1).strip() if thought_match else ""
        action = action_match.group(1).strip() if action_match else ""
        action_input_str = input_match.group(1).strip() if input_match else "{}"

        try:
            action_input = json.loads(action_input_str)
        except json.JSONDecodeError:
            action_input = {"response": action_input_str}

        return thought, action, action_input

    def run(
        self,
        goal: str,
        initial_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the ReAct loop.

        Args:
            goal: The objective to achieve
            initial_context: Starting state information

        Returns:
            Final result with history and status
        """
        context = initial_context.copy()
        iteration = 0

        while iteration < self.max_iterations:
            iteration += 1

            # Get LLM reasoning and action decision
            prompt = self._build_react_prompt(goal, context)
            response = self.llm.chat(
                user_message=prompt,
                system_prompt=DRONE_SYSTEM_PROMPT,
                stream=False
            )

            content = response["message"]["content"]
            thought, action, action_input = self._parse_response(content)

            # Check if goal is complete
            if action.upper() == "FINISH":
                step = ReActStep(
                    step_number=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input
                )
                self.history.append(step)
                return {
                    "success": True,
                    "result": action_input.get("response", "Task completed"),
                    "history": self.history,
                    "iterations": iteration
                }

            # Safety check before executing
            is_safe, safety_reason = self.safety_checker(action, action_input, context)

            if not is_safe:
                observation = f"SAFETY VIOLATION: {safety_reason}. Action blocked."
                step = ReActStep(
                    step_number=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    observation=observation
                )
                self.history.append(step)

                # Check if we should trigger emergency
                if "critical" in safety_reason.lower() or "emergency" in safety_reason.lower():
                    return {
                        "success": False,
                        "error": observation,
                        "history": self.history,
                        "emergency": True
                    }

                continue

            # Execute the tool
            if action in self.tools:
                try:
                    tool_result = self.tools[action](**action_input)
                    observation = str(tool_result)
                except Exception as e:
                    observation = f"Tool execution error: {str(e)}"
            else:
                observation = f"Unknown tool: {action}"

            # Record the step
            step = ReActStep(
                step_number=iteration,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation
            )
            self.history.append(step)

            # Update context with observation
            context["last_observation"] = observation
            context["last_action"] = action

        # Max iterations reached
        return {
            "success": False,
            "error": f"Max iterations ({self.max_iterations}) reached",
            "history": self.history,
            "iterations": iteration
        }
```

### 2.2 Observation Feedback Loop

```python
class ObservationProcessor:
    """Process and enrich observations from tool execution."""

    @staticmethod
    def process_telemetry(raw_data: Dict) -> TelemetryData:
        """Convert raw telemetry to structured data."""
        return TelemetryData(
            altitude=raw_data.get("altitude", 0),
            battery_percent=raw_data.get("battery", 100),
            gps_sats=raw_data.get("gps_sats", 0),
            latitude=raw_data.get("lat", 0),
            longitude=raw_data.get("lon", 0),
            speed=raw_data.get("speed", 0),
            heading=raw_data.get("heading", 0),
            state=raw_data.get("state", "unknown")
        )

    @staticmethod
    def enrich_observation(
        tool_name: str,
        raw_result: Any,
        context: Dict
    ) -> str:
        """
        Enrich observation with contextual analysis.

        This adds value beyond raw tool output for better LLM reasoning.
        """
        if tool_name == "get_status":
            telemetry = ObservationProcessor.process_telemetry(raw_result)

            concerns = []
            if telemetry.battery_percent < 20:
                concerns.append(f"LOW BATTERY: {telemetry.battery_percent}% - consider landing")
            if telemetry.gps_sats < 6:
                concerns.append(f"WEAK GPS: {telemetry.gps_sats} satellites - precision degraded")
            if telemetry.altitude > 100:
                concerns.append(f"HIGH ALTITUDE: {telemetry.altitude}m - near legal limit")

            enriched = {
                "telemetry": telemetry.model_dump(),
                "analysis": {
                    "flight_ready": telemetry.battery_percent > 25 and telemetry.gps_sats >= 6,
                    "safety_concerns": concerns,
                    "recommended_action": "continue" if not concerns else "monitor_closely"
                }
            }
            return json.dumps(enriched, indent=2)

        return str(raw_result)
```

### 2.3 Iteration Limits and Loop Prevention

```python
from enum import Enum, auto

class LoopDetectionStrategy(Enum):
    """Strategies for detecting and preventing infinite loops."""
    EXACT_REPEAT = auto()      # Same action/input repeated
    SIMILAR_THOUGHT = auto()   # Cosine similarity of thoughts
    STUCK_STATE = auto()       # No progress in N iterations
    CYCLIC_PATTERN = auto()    # Detects A->B->A patterns

@dataclass
class LoopDetector:
    """Detect and prevent infinite loops in agent execution."""

    max_iterations: int = 10
    strategies: List[LoopDetectionStrategy] = field(default_factory=lambda: [
        LoopDetectionStrategy.EXACT_REPEAT,
        LoopDetectionStrategy.STUCK_STATE
    ])
    action_history: List[tuple] = field(default_factory=list)

    def check_for_loop(self, action: str, inputs: Dict, result: Any) -> Optional[str]:
        """
        Check if the agent is in a loop.

        Returns:
            Loop description if detected, None otherwise
        """
        current = (action, json.dumps(inputs, sort_keys=True))
        self.action_history.append(current)

        # Strategy 1: Exact repeat detection
        if LoopDetectionStrategy.EXACT_REPEAT in self.strategies:
            if len(self.action_history) >= 3:
                last_three = self.action_history[-3:]
                if len(set(last_three)) == 1:
                    return "Exact action repeat detected 3 times"

        # Strategy 2: Stuck state (no meaningful change)
        if LoopDetectionStrategy.STUCK_STATE in self.strategies:
            if len(self.action_history) >= 5:
                # Check if last 5 actions all produced similar results
                return None  # Would need result comparison

        return None

    def should_terminate(self, iteration: int) -> bool:
        """Check if we should force termination."""
        return iteration >= self.max_iterations
```

### 2.4 Error Handling and Recovery

```python
class DroneControlError(Exception):
    """Base exception for drone control errors."""
    pass

class SafetyViolationError(DroneControlError):
    """Raised when a safety constraint is violated."""
    pass

class ToolExecutionError(DroneControlError):
    """Raised when tool execution fails."""
    pass

class SafeReActAgent(ReActAgent):
    """ReAct agent with comprehensive error handling and recovery."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_count = 0
        self.max_errors = 3
        self.recovery_strategies: Dict[str, Callable] = {
            "gps_loss": self._handle_gps_loss,
            "low_battery": self._handle_low_battery,
            "communication_error": self._handle_comm_error,
            "tool_failure": self._handle_tool_failure
        }

    def _handle_gps_loss(self, context: Dict) -> Dict:
        """Recovery strategy for GPS signal loss."""
        return {
            "action": "hold_position",
            "reason": "GPS degraded - holding position for signal recovery",
            "timeout": 30  # seconds to wait
        }

    def _handle_low_battery(self, context: Dict) -> Dict:
        """Recovery strategy for low battery."""
        return {
            "action": "emergency_land",
            "reason": "Battery critical - immediate landing required",
            "location": "nearest_safe"
        }

    def _handle_comm_error(self, context: Dict) -> Dict:
        """Recovery strategy for communication errors."""
        return {
            "action": "return_to_home",
            "reason": "Communication lost - executing RTH protocol",
            "retry_connection": True
        }

    def _handle_tool_failure(self, context: Dict) -> Dict:
        """Recovery strategy for tool execution failure."""
        return {
            "action": "retry_with_fallback",
            "reason": "Tool execution failed - attempting fallback",
            "max_retries": 2
        }

    def execute_with_recovery(
        self,
        action: str,
        params: Dict,
        context: Dict
    ) -> tuple[bool, Any]:
        """
        Execute tool with error handling and recovery.

        Returns:
            (success, result_or_error)
        """
        try:
            if action not in self.tools:
                raise ToolExecutionError(f"Unknown tool: {action}")

            result = self.tools[action](**params)
            self.error_count = 0  # Reset on success
            return True, result

        except SafetyViolationError as e:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                return False, {
                    "error": "Too many errors - entering safe mode",
                    "recovery_action": "emergency_stop"
                }
            return False, {"error": str(e), "recoverable": False}

        except Exception as e:
            self.error_count += 1
            error_type = self._classify_error(str(e))

            if error_type in self.recovery_strategies:
                recovery = self.recovery_strategies[error_type](context)
                return False, {
                    "error": str(e),
                    "recovery": recovery,
                    "recoverable": True
                }

            return False, {"error": str(e), "recoverable": False}

    def _classify_error(self, error_msg: str) -> str:
        """Classify error type for recovery strategy selection."""
        error_lower = error_msg.lower()
        if "gps" in error_lower or "satellite" in error_lower:
            return "gps_loss"
        if "battery" in error_lower:
            return "low_battery"
        if "connect" in error_lower or "timeout" in error_lower:
            return "communication_error"
        return "tool_failure"
```

---

## 3. Safety-Critical Implementation

### 3.1 Tool Whitelisting

```python
from functools import wraps
import hashlib

class ToolRegistry:
    """Whitelisted tool registry with cryptographic verification."""

    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._signatures: Dict[str, str] = {}
        self._frozen = False

    def register(
        self,
        name: str,
        func: Callable,
        signature: Optional[str] = None
    ):
        """
        Register a tool with optional signature verification.

        Args:
            name: Tool identifier
            func: The callable function
            signature: Expected hash of function source (for verification)
        """
        if self._frozen:
            raise RuntimeError("Registry is frozen - cannot add new tools")

        # Verify function source if signature provided
        if signature:
            actual_sig = self._hash_function(func)
            if actual_sig != signature:
                raise SecurityError(
                    f"Tool {name} signature mismatch - possible tampering"
                )

        self._tools[name] = func
        self._signatures[name] = signature or self._hash_function(func)

    def _hash_function(self, func: Callable) -> str:
        """Create hash of function source code."""
        import inspect
        source = inspect.getsource(func)
        return hashlib.sha256(source.encode()).hexdigest()[:16]

    def get(self, name: str) -> Callable:
        """Get a tool by name (raises if not found)."""
        if name not in self._tools:
            raise SecurityError(f"Tool '{name}' not in whitelist")
        return self._tools[name]

    def freeze(self):
        """Freeze registry - no new tools can be added."""
        self._frozen = True

    def verify_all(self) -> bool:
        """Verify all registered tools match their signatures."""
        for name, func in self._tools.items():
            current_sig = self._hash_function(func)
            if current_sig != self._signatures[name]:
                return False
        return True

class SecurityError(Exception):
    """Security-related error."""
    pass

# Decorator for whitelisted tools
def whitelisted_tool(
    registry: ToolRegistry,
    name: Optional[str] = None,
    dangerous: bool = False,
    requires_confirmation: bool = False
):
    """Decorator for registering whitelisted tools."""
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            # Pre-execution logging
            print(f"[SECURITY] Executing whitelisted tool: {tool_name}")

            if dangerous:
                print(f"[SECURITY WARNING] Dangerous tool: {tool_name}")

            if requires_confirmation:
                # In production, this would require explicit user confirmation
                pass

            return func(*args, **kwargs)

        registry.register(tool_name, wrapper)
        return wrapper
    return decorator

# Example usage
registry = ToolRegistry()

@whitelisted_tool(registry, dangerous=True, requires_confirmation=True)
def emergency_stop(reason: str) -> str:
    """EMERGENCY: Cut power and land immediately."""
    # Implementation
    return f"Emergency stop triggered: {reason}"

@whitelisted_tool(registry)
def get_status() -> Dict:
    """Get current drone telemetry."""
    # Implementation
    return {"altitude": 50, "battery": 85}

registry.freeze()  # Lock the registry
```

### 3.2 Parameter Bounds Validation

```python
from pydantic import BaseModel, Field, validator, ValidationError
from typing import Annotated
import inspect

class DroneMoveParams(BaseModel):
    """Validated parameters for drone movement."""

    forward: Annotated[float, Field(ge=-10, le=10, default=0)]
    right: Annotated[float, Field(ge=-10, le=10, default=0)]
    up: Annotated[float, Field(ge=-10, le=10, default=0)]
    speed: Annotated[float, Field(ge=0, le=15, default=5)]

    @validator('forward', 'right', 'up')
    def check_cumulative_movement(cls, v, values):
        """Ensure total movement doesn't exceed safety bounds."""
        forward = values.get('forward', 0) or 0
        right = values.get('right', 0) or 0
        up = values.get('up', 0) or 0

        total_distance = (forward**2 + right**2 + up**2) ** 0.5
        if total_distance > 15:
            raise ValueError(f"Total movement {total_distance:.1f}m exceeds 15m safety limit")
        return v

class ParameterValidator:
    """Centralized parameter validation for all drone operations."""

    # Safety bounds for all parameters
    BOUNDS = {
        "altitude": {"min": 0, "max": 120, "unit": "m"},
        "speed": {"min": 0, "max": 15, "unit": "m/s"},
        "distance": {"min": -10, "max": 10, "unit": "m"},
        "battery": {"min": 0, "max": 100, "unit": "%"},
        "gps_sats": {"min": 0, "max": 20, "unit": "count"},
        "heading": {"min": 0, "max": 360, "unit": "degrees"},
    }

    @classmethod
    def validate_bounds(
        cls,
        param_name: str,
        value: float,
        context: Optional[Dict] = None
    ) -> tuple[bool, str]:
        """
        Validate a parameter against safety bounds.

        Returns:
            (is_valid, message)
        """
        if param_name not in cls.BOUNDS:
            return True, f"No bounds defined for {param_name}"

        bounds = cls.BOUNDS[param_name]

        if value < bounds["min"]:
            return False, f"{param_name}={value} below minimum {bounds['min']}{bounds['unit']}"

        if value > bounds["max"]:
            return False, f"{param_name}={value} exceeds maximum {bounds['max']}{bounds['unit']}"

        # Context-specific validation
        if context:
            # Dynamic bounds based on current state
            if param_name == "altitude":
                current_alt = context.get("altitude", 0)
                proposed_alt = current_alt + value if param_name != "altitude" else value
                if proposed_alt > 120:
                    return False, f"Proposed altitude {proposed_alt}m exceeds legal limit (120m)"

        return True, "Valid"

    @classmethod
    def validate_dict(cls, params: Dict, context: Optional[Dict] = None) -> Dict[str, tuple]:
        """Validate multiple parameters at once."""
        results = {}
        for name, value in params.items():
            results[name] = cls.validate_bounds(name, value, context)
        return results

def create_validated_tool(
    func: Callable,
    param_schema: type[BaseModel]
) -> Callable:
    """
    Wrap a function with Pydantic parameter validation.

    Args:
        func: The function to wrap
        param_schema: Pydantic model defining valid parameters

    Returns:
        Validated wrapper function
    """
    @wraps(func)
    def wrapper(**kwargs):
        try:
            # Validate and coerce parameters
            validated = param_schema(**kwargs)
            # Call with validated data
            return func(**validated.model_dump())
        except ValidationError as e:
            errors = []
            for err in e.errors():
                errors.append(f"{err['loc']}: {err['msg']}")
            raise ValueError(f"Parameter validation failed: {'; '.join(errors)}")

    return wrapper

# Example usage
@create_validated_tool
async def move_drone(forward: float, right: float, up: float, speed: float) -> str:
    """Move drone with validated parameters."""
    # Implementation here receives validated params
    return f"Moving: F={forward} R={right} U={up} @ {speed}m/s"
```

### 3.3 Timeout Handling for Async Calls

```python
import asyncio
from asyncio import TimeoutError as AsyncTimeoutError
from dataclasses import dataclass
from enum import Enum
import time

class CallStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"

@dataclass
class AsyncCallResult:
    """Result of an async tool call with timeout."""
    status: CallStatus
    result: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    retry_count: int = 0

class AsyncToolExecutor:
    """Execute tools with timeout and retry logic."""

    def __init__(
        self,
        default_timeout: float = 5.0,
        max_retries: int = 2,
        backoff_base: float = 1.0
    ):
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    async def execute(
        self,
        tool_func: Callable,
        params: Dict,
        timeout: Optional[float] = None,
        critical: bool = False
    ) -> AsyncCallResult:
        """
        Execute a tool with timeout and retry.

        Args:
            tool_func: The async function to call
            params: Parameters to pass
            timeout: Override default timeout (seconds)
            critical: If True, shorter timeout and no retries

        Returns:
            AsyncCallResult with status and data
        """
        actual_timeout = timeout or self.default_timeout
        actual_retries = 0 if critical else self.max_retries

        start_time = time.time()

        for attempt in range(actual_retries + 1):
            try:
                result = await asyncio.wait_for(
                    tool_func(**params),
                    timeout=actual_timeout
                )

                duration = (time.time() - start_time) * 1000
                return AsyncCallResult(
                    status=CallStatus.SUCCESS,
                    result=result,
                    duration_ms=duration,
                    retry_count=attempt
                )

            except AsyncTimeoutError:
                if attempt < actual_retries:
                    # Exponential backoff
                    wait = self.backoff_base * (2 ** attempt)
                    await asyncio.sleep(wait)
                    continue

                duration = (time.time() - start_time) * 1000
                return AsyncCallResult(
                    status=CallStatus.TIMEOUT,
                    error=f"Timeout after {actual_timeout}s and {attempt + 1} attempts",
                    duration_ms=duration,
                    retry_count=attempt
                )

            except Exception as e:
                duration = (time.time() - start_time) * 1000
                return AsyncCallResult(
                    status=CallStatus.ERROR,
                    error=str(e),
                    duration_ms=duration,
                    retry_count=attempt
                )

        # Should not reach here
        return AsyncCallResult(status=CallStatus.ERROR, error="Unexpected execution path")

class TimeoutManager:
    """Manage timeouts for different tool categories."""

    TIMEOUTS = {
        "status_query": 2.0,      # Quick telemetry
        "movement": 5.0,          # Physical movement
        "navigation": 10.0,       # Path planning
        "emergency": 1.0,         # Emergency must be fast
        "system": 3.0,            # System commands
    }

    @classmethod
    def get_timeout(cls, tool_name: str, critical: bool = False) -> float:
        """Get appropriate timeout for a tool."""
        base = 1.0 if critical else 5.0

        for category, timeout in cls.TIMEOUTS.items():
            if category in tool_name.lower():
                return timeout if not critical else timeout / 2

        return base
```

### 3.4 Emergency Stop Mechanisms

```python
import threading
from concurrent.futures import ThreadPoolExecutor
import signal

class EmergencyStopManager:
    """
    Manages emergency stop state with hardware-level integration.

    Thread-safe singleton for emergency state management.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self._emergency_active = False
        self._emergency_reason: Optional[str] = None
        self._stop_timestamp: Optional[float] = None
        self._callbacks: List[Callable] = []
        self._executor = ThreadPoolExecutor(max_workers=1)

        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle OS signals as emergency triggers."""
        self.trigger(f"OS signal {signum} received")

    def trigger(self, reason: str, immediate: bool = True) -> bool:
        """
        Trigger emergency stop.

        Args:
            reason: Why the emergency was triggered
            immediate: If True, execute immediately; else queue

        Returns:
            True if emergency was newly triggered
        """
        with self._lock:
            if self._emergency_active:
                return False  # Already in emergency

            self._emergency_active = True
            self._emergency_reason = reason
            self._stop_timestamp = time.time()

        if immediate:
            self._execute_emergency_stop()
        else:
            self._executor.submit(self._execute_emergency_stop)

        return True

    def _execute_emergency_stop(self):
        """Execute the emergency stop sequence."""
        print(f"[EMERGENCY] STOP TRIGGERED: {self._emergency_reason}")

        try:
            # Step 1: Cut motors (or reduce to minimum for controlled landing)
            self._cut_motors()

            # Step 2: Deploy emergency systems if available
            self._deploy_emergency_systems()

            # Step 3: Log for post-incident analysis
            self._log_emergency()

            # Step 4: Notify all registered callbacks
            for callback in self._callbacks:
                try:
                    callback(self._emergency_reason)
                except Exception as e:
                    print(f"[EMERGENCY] Callback error: {e}")

        except Exception as e:
            print(f"[EMERGENCY] Critical error in emergency stop: {e}")

    def _cut_motors(self):
        """Cut motor power or initiate emergency landing."""
        # Platform-specific implementation
        print("[EMERGENCY] Motor power reduced to emergency landing level")

    def _deploy_emergency_systems(self):
        """Deploy parachute or other emergency systems."""
        print("[EMERGENCY] Emergency systems standby")

    def _log_emergency(self):
        """Log emergency details for analysis."""
        emergency_log = {
            "timestamp": self._stop_timestamp,
            "reason": self._emergency_reason,
            "telemetry_at_stop": self._get_current_telemetry()
        }
        # Write to persistent storage
        print(f"[EMERGENCY] Logged: {emergency_log}")

    def _get_current_telemetry(self) -> Dict:
        """Get current telemetry for emergency logging."""
        # Query drone state
        return {}

    def register_callback(self, callback: Callable):
        """Register a callback to be called on emergency."""
        self._callbacks.append(callback)

    def is_active(self) -> bool:
        """Check if emergency stop is currently active."""
        with self._lock:
            return self._emergency_active

    def reset(self, authorization_code: str) -> bool:
        """
        Reset emergency state (requires authorization).

        This should only be called after manual inspection and
        when it's safe to resume operations.
        """
        # Verify authorization (in production, this would be
        # a physical button or authenticated command)
        if authorization_code != "MANUAL_RESET_AUTH":
            return False

        with self._lock:
            if not self._emergency_active:
                return False

            self._emergency_active = False
            self._emergency_reason = None
            self._stop_timestamp = None

        print("[EMERGENCY] State reset - manual confirmation required before flight")
        return True

    def assert_not_emergency(self):
        """Raise exception if in emergency state."""
        if self.is_active():
            raise SafetyViolationError(
                f"Emergency stop active: {self._emergency_reason}"
            )

# Global emergency manager instance
emergency = EmergencyStopManager()

# Decorator to check emergency state before tool execution
def check_emergency(func: Callable) -> Callable:
    """Decorator that blocks execution during emergency state."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        emergency.assert_not_emergency()
        return func(*args, **kwargs)
    return wrapper
```

---

## 4. Complete Python Implementation

### 4.1 Main ReAct Agent Class

```python
"""
SafeReActDroneAgent - Production-ready ReAct agent for drone control
using Ollama with Llama 3 and comprehensive safety constraints.
"""

import json
import asyncio
import re
from typing import Dict, List, Optional, Callable, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
import requests
from pydantic import BaseModel, Field, ValidationError
import time
import threading

# ============================================================================
# Configuration
# ============================================================================

OLLAMA_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.1:8b"
MAX_ITERATIONS = 10
DEFAULT_TIMEOUT = 5.0

# ============================================================================
# Data Models
# ============================================================================

class AgentState(Enum):
    IDLE = auto()
    PLANNING = auto()
    EXECUTING = auto()
    OBSERVING = auto()
    COMPLETE = auto()
    ERROR = auto()
    EMERGENCY = auto()

@dataclass
class ReActStep:
    """Single ReAct iteration record."""
    step_number: int
    thought: str
    action: Optional[str] = None
    action_input: Optional[Dict] = None
    observation: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0

@dataclass
class AgentResult:
    """Final result from agent execution."""
    success: bool
    final_answer: Optional[str] = None
    error: Optional[str] = None
    history: List[ReActStep] = field(default_factory=list)
    iterations: int = 0
    total_duration_ms: float = 0.0
    emergency_triggered: bool = False

class TelemetryData(BaseModel):
    """Structured drone telemetry."""
    altitude: float = Field(ge=0, le=500)
    battery_percent: float = Field(ge=0, le=100)
    gps_sats: int = Field(ge=0, le=20)
    latitude: float
    longitude: float
    speed: float = Field(ge=0)
    heading: float = Field(ge=0, le=360)
    state: str = "unknown"

# ============================================================================
# Ollama Client
# ============================================================================

class OllamaClient:
    """Async-capable Ollama API client."""

    def __init__(self, host: str = OLLAMA_HOST, model: str = DEFAULT_MODEL):
        self.host = host
        self.model = model
        self.chat_url = f"{host}/api/chat"
        self.generate_url = f"{host}/api/generate"

    def chat(
        self,
        messages: List[Dict],
        system: Optional[str] = None,
        tools: Optional[List[Dict]] = None,
        stream: bool = False
    ) -> Dict:
        """Send chat request to Ollama."""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": stream
        }

        if system:
            payload["messages"].insert(0, {"role": "system", "content": system})

        if tools:
            payload["tools"] = tools

        response = requests.post(self.chat_url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

    def generate(
        self,
        prompt: str,
        format: Optional[Dict] = None,
        system: Optional[str] = None
    ) -> Dict:
        """Generate with structured output support."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }

        if format:
            payload["format"] = format

        if system:
            payload["system"] = system

        response = requests.post(self.generate_url, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()

# ============================================================================
# Safety Systems
# ============================================================================

class SafetyManager:
    """Centralized safety management for drone operations."""

    # Parameter bounds
    BOUNDS = {
        "altitude": {"min": 0, "max": 120, "critical_max": 150},
        "speed": {"min": 0, "max": 15, "critical_max": 20},
        "battery": {"min": 0, "max": 100, "critical_min": 15},
        "gps_sats": {"min": 0, "max": 20, "min_safe": 6},
    }

    def __init__(self):
        self.emergency_active = False
        self.emergency_reason: Optional[str] = None
        self._lock = threading.Lock()

    def validate_action(
        self,
        action: str,
        params: Dict,
        context: Dict
    ) -> Tuple[bool, str]:
        """
        Validate if an action is safe to execute.

        Returns:
            (is_safe, reason)
        """
        # Check emergency state
        if self.emergency_active:
            if action != "emergency_stop":
                return False, f"Emergency active: {self.emergency_reason}"

        # Check battery
        battery = context.get("battery", 100)
        if battery < self.BOUNDS["battery"]["critical_min"]:
            if action not in ["land", "emergency_stop", "get_status"]:
                return False, f"Critical battery ({battery}%) - only landing allowed"

        # Check altitude limits
        if action in ["move_relative", "move_absolute"]:
            current_alt = context.get("altitude", 0)
            delta_alt = params.get("up", 0)
            new_alt = current_alt + delta_alt

            if new_alt > self.BOUNDS["altitude"]["critical_max"]:
                return False, f"Proposed altitude {new_alt}m exceeds critical limit"

            if new_alt > self.BOUNDS["altitude"]["max"]:
                return True, f"Warning: Proposed altitude {new_alt}m exceeds legal limit"

        # Check speed limits
        if "speed" in params:
            speed = params["speed"]
            if speed > self.BOUNDS["speed"]["critical_max"]:
                return False, f"Speed {speed} exceeds critical safety limit"

        return True, "Safe"

    def trigger_emergency(self, reason: str) -> bool:
        """Trigger emergency stop."""
        with self._lock:
            if self.emergency_active:
                return False
            self.emergency_active = True
            self.emergency_reason = reason
        return True

    def is_emergency(self) -> bool:
        """Check if emergency state is active."""
        with self._lock:
            return self.emergency_active

# ============================================================================
# Tool Registry
# ============================================================================

class ToolRegistry:
    """Registry for validated, whitelisted tools."""

    def __init__(self, safety_manager: SafetyManager):
        self._tools: Dict[str, Callable] = {}
        self._schemas: Dict[str, Dict] = {}
        self._safety = safety_manager

    def register(
        self,
        name: str,
        func: Callable,
        schema: Optional[Dict] = None
    ):
        """Register a tool with optional JSON schema."""
        self._tools[name] = func
        self._schemas[name] = schema or {}

    def execute(
        self,
        name: str,
        params: Dict,
        context: Dict,
        timeout: float = DEFAULT_TIMEOUT
    ) -> Tuple[bool, Any]:
        """
        Execute a tool with safety checks and timeout.

        Returns:
            (success, result_or_error)
        """
        if name not in self._tools:
            return False, f"Unknown tool: {name}"

        # Safety check
        is_safe, reason = self._safety.validate_action(name, params, context)
        if not is_safe:
            return False, f"SAFETY VIOLATION: {reason}"

        # Execute with timeout
        try:
            func = self._tools[name]

            # Handle async functions
            if asyncio.iscoroutinefunction(func):
                result = asyncio.wait_for(func(**params), timeout=timeout)
            else:
                result = func(**params)

            return True, result

        except asyncio.TimeoutError:
            return False, f"Tool execution timeout ({timeout}s)"
        except Exception as e:
            return False, f"Tool error: {str(e)}"

    def get_schema(self, name: str) -> Optional[Dict]:
        """Get JSON schema for a tool."""
        return self._schemas.get(name)

    def list_tools(self) -> List[str]:
        """List registered tool names."""
        return list(self._tools.keys())

# ============================================================================
# SafeReActDroneAgent
# ============================================================================

class SafeReActDroneAgent:
    """
    Production-ready ReAct agent for safe drone control.

    Combines:
    - ReAct reasoning pattern
    - Ollama tool calling
    - Comprehensive safety checks
    - Timeout and error handling
    - Emergency stop integration
    """

    SYSTEM_PROMPT = """You are SafeReAct, an AI agent controlling a physical drone.

Your task is to safely accomplish user goals using the ReAct pattern:
1. THINK: Analyze the situation and plan your approach
2. ACT: Execute one of the available tools
3. OBSERVE: Process the result and update your understanding
4. REPEAT until the goal is achieved

SAFETY RULES (non-negotiable):
- NEVER execute actions that could harm people
- Respect all altitude limits (max 120m)
- Land immediately if battery < 20%
- Emergency stop available for any danger
- Ask for clarification if uncertain

RESPONSE FORMAT (STRICT):
Thought: <your reasoning>
Action: <tool_name>
Action Input: <json parameters>

When complete:
Thought: Task complete
Action: FINISH
Action Input: {"result": "<summary>"}

Available tools:
{tool_descriptions}
"""

    def __init__(
        self,
        ollama_client: Optional[OllamaClient] = None,
        model: str = DEFAULT_MODEL,
        max_iterations: int = MAX_ITERATIONS
    ):
        self.ollama = ollama_client or OllamaClient(model=model)
        self.max_iterations = max_iterations
        self.safety = SafetyManager()
        self.tools = ToolRegistry(self.safety)
        self.history: List[ReActStep] = []

    def _build_tool_descriptions(self) -> str:
        """Build tool descriptions for system prompt."""
        descriptions = []
        for name in self.tools.list_tools():
            schema = self.tools.get_schema(name)
            desc = f"- {name}"
            if schema:
                desc += f": {schema.get('description', 'No description')}"
            descriptions.append(desc)
        return "\n".join(descriptions)

    def _parse_response(self, text: str) -> Tuple[str, str, Dict]:
        """Parse ReAct format response."""
        thought_match = re.search(
            r"Thought:\s*(.+?)(?=\nAction:|$)", text, re.DOTALL | re.IGNORECASE
        )
        action_match = re.search(
            r"Action:\s*(.+?)(?=\nAction Input:|$)", text, re.DOTALL | re.IGNORECASE
        )
        input_match = re.search(
            r"Action Input:\s*(.+?)(?=\n|$)", text, re.DOTALL | re.IGNORECASE
        )

        thought = thought_match.group(1).strip() if thought_match else ""
        action = action_match.group(1).strip() if action_match else ""
        input_str = input_match.group(1).strip() if input_match else "{}"

        try:
            action_input = json.loads(input_str)
        except json.JSONDecodeError:
            action_input = {"raw": input_str}

        return thought, action, action_input

    def _build_prompt(
        self,
        goal: str,
        context: Dict,
        history: List[ReActStep]
    ) -> str:
        """Build the ReAct prompt."""
        lines = [
            f"Goal: {goal}",
            "",
            f"Current State: {json.dumps(context, indent=2)}",
            "",
            "Previous Actions:",
        ]

        for step in history:
            lines.append(f"  Step {step.step_number}: {step.action}")
            if step.observation:
                lines.append(f"    -> {step.observation[:100]}...")

        lines.extend([
            "",
            "What is your next Thought, Action, and Action Input?",
            "Follow the exact format specified in your instructions."
        ])

        return "\n".join(lines)

    def run(
        self,
        goal: str,
        context: Dict[str, Any]
    ) -> AgentResult:
        """
        Execute the ReAct loop to achieve the goal.

        Args:
            goal: The objective to accomplish
            context: Current drone state and telemetry

        Returns:
            AgentResult with success status and history
        """
        start_time = time.time()
        self.history = []
        system_prompt = self.SYSTEM_PROMPT.format(
            tool_descriptions=self._build_tool_descriptions()
        )

        for iteration in range(1, self.max_iterations + 1):
            step_start = time.time()

            # Build prompt with history
            prompt = self._build_prompt(goal, context, self.history)

            # Get LLM response
            try:
                response = self.ollama.chat(
                    messages=[{"role": "user", "content": prompt}],
                    system=system_prompt
                )
                content = response["message"]["content"]
            except Exception as e:
                return AgentResult(
                    success=False,
                    error=f"LLM communication error: {str(e)}",
                    history=self.history,
                    iterations=iteration,
                    total_duration_ms=(time.time() - start_time) * 1000
                )

            # Parse response
            thought, action, action_input = self._parse_response(content)

            # Check for completion
            if action.upper() == "FINISH":
                step = ReActStep(
                    step_number=iteration,
                    thought=thought,
                    action=action,
                    action_input=action_input,
                    duration_ms=(time.time() - step_start) * 1000
                )
                self.history.append(step)

                return AgentResult(
                    success=True,
                    final_answer=action_input.get("result", "Task completed"),
                    history=self.history,
                    iterations=iteration,
                    total_duration_ms=(time.time() - start_time) * 1000
                )

            # Execute tool
            success, result = self.tools.execute(
                action, action_input, context
            )

            observation = str(result) if success else f"ERROR: {result}"

            # Record step
            step = ReActStep(
                step_number=iteration,
                thought=thought,
                action=action,
                action_input=action_input,
                observation=observation,
                duration_ms=(time.time() - step_start) * 1000
            )
            self.history.append(step)

            # Check for emergency
            if self.safety.is_emergency():
                return AgentResult(
                    success=False,
                    error=f"Emergency triggered: {self.safety.emergency_reason}",
                    history=self.history,
                    iterations=iteration,
                    total_duration_ms=(time.time() - start_time) * 1000,
                    emergency_triggered=True
                )

            # Update context with observation
            context["last_observation"] = observation
            context["last_action"] = action

        # Max iterations reached
        return AgentResult(
            success=False,
            error=f"Max iterations ({self.max_iterations}) reached without completion",
            history=self.history,
            iterations=self.max_iterations,
            total_duration_ms=(time.time() - start_time) * 1000
        )

# ============================================================================
# Example Tool Implementations
# ============================================================================

# Mock implementations for demonstration
def mock_takeoff(altitude: float) -> str:
    """Simulate drone takeoff."""
    return f"Taking off to {altitude}m"

def mock_land(location: str = "current") -> str:
    """Simulate drone landing."""
    return f"Landing at {location} location"

def mock_move_relative(forward: float = 0, right: float = 0, up: float = 0) -> str:
    """Simulate relative movement."""
    return f"Moving: F={forward}m, R={right}m, U={up}m"

def mock_get_status() -> Dict:
    """Simulate telemetry."""
    return {
        "altitude": 50,
        "battery": 80,
        "gps_sats": 8,
        "state": "flying"
    }

def mock_emergency_stop(reason: str) -> str:
    """Simulate emergency stop."""
    return f"EMERGENCY STOP: {reason}"

# ============================================================================
# Example Usage
# ============================================================================

def main():
    """Example usage of SafeReActDroneAgent."""

    # Initialize components
    client = OllamaClient()
    agent = SafeReActDroneAgent(client)

    # Register tools
    agent.tools.register("takeoff", mock_takeoff)
    agent.tools.register("land", mock_land)
    agent.tools.register("move_relative", mock_move_relative)
    agent.tools.register("get_status", mock_get_status)
    agent.tools.register("emergency_stop", mock_emergency_stop)

    # Initial context
    context = {
        "altitude": 0,
        "battery": 95,
        "gps_sats": 10,
        "state": "grounded"
    }

    # Run agent
    result = agent.run(
        goal="Take off to 20m altitude, then move forward 5m",
        context=context
    )

    # Print results
    print(f"\n{'='*60}")
    print(f"Success: {result.success}")
    print(f"Answer: {result.final_answer}")
    print(f"Error: {result.error}")
    print(f"Iterations: {result.iterations}")
    print(f"Duration: {result.total_duration_ms:.0f}ms")
    print(f"\nExecution History:")
    for step in result.history:
        print(f"\n  Step {step.step_number} ({step.duration_ms:.0f}ms):")
        print(f"    Thought: {step.thought[:80]}...")
        print(f"    Action: {step.action}")
        if step.observation:
            print(f"    -> {step.observation[:80]}...")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
```

### 4.2 Streaming Response Handler

```python
import asyncio
from typing import AsyncIterator, Callable
import json

class StreamingReActHandler:
    """Handle streaming responses from Ollama for real-time ReAct."""

    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
        self.buffer = ""
        self.current_thought = ""
        self.current_action = ""

    async def stream_react(
        self,
        goal: str,
        context: Dict,
        on_thought: Optional[Callable[[str], None]] = None,
        on_action: Optional[Callable[[str, Dict], None]] = None,
        on_observation: Optional[Callable[[str], None]] = None
    ) -> AsyncIterator[Dict]:
        """
        Stream ReAct execution with real-time callbacks.

        Yields intermediate states for UI updates.
        """
        iteration = 0

        while iteration < MAX_ITERATIONS:
            iteration += 1

            # Build and send request
            prompt = self._build_prompt(goal, context)

            payload = {
                "model": self.ollama.model,
                "messages": [{"role": "user", "content": prompt}],
                "system": DRONE_SYSTEM_PROMPT,
                "stream": True
            }

            # Stream response
            full_content = ""
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ollama.chat_url,
                    json=payload
                ) as response:
                    async for line in response.content:
                        if line:
                            chunk = json.loads(line)
                            if "message" in chunk:
                                delta = chunk["message"].get("content", "")
                                full_content += delta

                                # Check for complete thought
                                if "Thought:" in full_content:
                                    thought_match = re.search(
                                        r"Thought:\s*(.+?)(?=\nAction:|$)",
                                        full_content,
                                        re.DOTALL
                                    )
                                    if thought_match and on_thought:
                                        thought = thought_match.group(1).strip()
                                        if thought != self.current_thought:
                                            self.current_thought = thought
                                            on_thought(thought)
                                            yield {
                                                "type": "thought",
                                                "content": thought,
                                                "iteration": iteration
                                            }

                                # Check for complete action
                                if "Action:" in full_content and "Action Input:" in full_content:
                                    action_match = re.search(
                                        r"Action:\s*(.+?)\n",
                                        full_content
                                    )
                                    input_match = re.search(
                                        r"Action Input:\s*(.+?)(?=\n|$)",
                                        full_content
                                    )

                                    if action_match and input_match:
                                        action = action_match.group(1).strip()
                                        try:
                                            action_input = json.loads(
                                                input_match.group(1).strip()
                                            )
                                        except:
                                            action_input = {}

                                        if action != self.current_action:
                                            self.current_action = action
                                            on_action(action, action_input)
                                            yield {
                                                "type": "action",
                                                "action": action,
                                                "input": action_input,
                                                "iteration": iteration
                                            }

                                            # Execute and observe
                                            if action != "FINISH":
                                                # Execute tool
                                                success, result = await self._execute_tool(
                                                    action, action_input
                                                )
                                                observation = str(result) if success else f"Error: {result}"

                                                if on_observation:
                                                    on_observation(observation)

                                                yield {
                                                    "type": "observation",
                                                    "content": observation,
                                                    "success": success,
                                                    "iteration": iteration
                                                }

                                                # Update context and continue
                                                context["last_observation"] = observation
                                                break  # Break streaming to start next iteration

                                            else:
                                                # FINISH action
                                                yield {
                                                    "type": "complete",
                                                    "result": action_input.get("result", "Done"),
                                                    "iterations": iteration
                                                }
                                                return

    async def _execute_tool(
        self,
        action: str,
        params: Dict
    ) -> Tuple[bool, Any]:
        """Execute a tool (placeholder - integrate with actual drone SDK)."""
        # Tool execution logic here
        return True, f"Executed {action} with {params}"
```

### 4.3 Pydantic Schema Validation for Tools

```python
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Annotated, Literal
import json

class TakeoffParams(BaseModel):
    """Validated parameters for takeoff command."""

    altitude: Annotated[float, Field(
        ge=1, le=30,
        description="Target altitude in meters (1-30)"
    )]
    speed: Annotated[float, Field(
        ge=0.5, le=5, default=2,
        description="Ascent speed in m/s"
    )]

    @field_validator('altitude')
    @classmethod
    def check_reasonable_altitude(cls, v: float) -> float:
        if v > 20:
            # Log warning but allow (within bounds)
            print(f"[WARN] High takeoff altitude: {v}m")
        return v

class MoveParams(BaseModel):
    """Validated parameters for movement command."""

    forward: Annotated[float, Field(ge=-10, le=10, default=0)]
    right: Annotated[float, Field(ge=-10, le=10, default=0)]
    up: Annotated[float, Field(ge=-10, le=10, default=0)]
    speed: Annotated[float, Field(ge=0, le=15, default=5)]
    heading_mode: Literal["relative", "absolute"] = "relative"

    @model_validator(mode='after')
    def check_total_distance(self):
        """Ensure total movement distance is reasonable."""
        total = (self.forward**2 + self.right**2 + self.up**2) ** 0.5
        if total > 15:
            raise ValueError(f"Total movement {total:.1f}m exceeds safe limit of 15m")
        return self

    @model_validator(mode='after')
    def check_speed_for_distance(self):
        """Adjust speed based on distance for safety."""
        total = (self.forward**2 + self.right**2 + self.up**2) ** 0.5
        if total < 2 and self.speed > 5:
            # Slow down for small movements
            self.speed = min(self.speed, 3)
        return self

class ToolSchemaGenerator:
    """Generate JSON schemas for Ollama tool definitions from Pydantic models."""

    @staticmethod
    def from_pydantic(
        name: str,
        description: str,
        param_model: type[BaseModel]
    ) -> Dict:
        """
        Convert Pydantic model to Ollama tool schema.

        Args:
            name: Tool name
            description: Tool description for LLM
            param_model: Pydantic model class for parameters

        Returns:
            Ollama-compatible tool definition
        """
        schema = param_model.model_json_schema()

        # Convert to Ollama format
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", [])
                }
            }
        }

    @staticmethod
    def validate_and_call(
        func: Callable,
        param_model: type[BaseModel],
        raw_params: Dict
    ) -> Tuple[bool, Any]:
        """
        Validate parameters and call function.

        Returns:
            (success, result_or_error)
        """
        try:
            validated = param_model(**raw_params)
            result = func(**validated.model_dump())
            return True, result
        except ValidationError as e:
            errors = []
            for err in e.errors():
                field = ".".join(str(x) for x in err['loc'])
                errors.append(f"{field}: {err['msg']}")
            return False, f"Validation failed: {'; '.join(errors)}"
        except Exception as e:
            return False, f"Execution error: {str(e)}"

# Example: Generate schemas for all drone tools
DRONE_TOOL_SCHEMAS = [
    ToolSchemaGenerator.from_pydantic(
        "takeoff",
        "Initiate controlled takeoff to specified altitude",
        TakeoffParams
    ),
    ToolSchemaGenerator.from_pydantic(
        "move_relative",
        "Move relative to current position with safety limits",
        MoveParams
    ),
]
```

---

## 5. Integration Patterns for Real-World Use

### 5.1 Hardware Abstraction Layer

```python
from abc import ABC, abstractmethod
from typing import Protocol

class DroneHardwareInterface(Protocol):
    """Protocol for drone hardware abstraction."""

    async def connect(self) -> bool: ...
    async def disconnect(self) -> None: ...
    async def takeoff(self, altitude: float) -> bool: ...
    async def land(self) -> bool: ...
    async def move(self, dx: float, dy: float, dz: float) -> bool: ...
    async def get_telemetry(self) -> Dict: ...
    async def emergency_stop(self) -> bool: ...

class MockDroneHardware:
    """Mock implementation for testing."""

    def __init__(self):
        self.altitude = 0
        self.battery = 100
        self.connected = False

    async def connect(self) -> bool:
        self.connected = True
        return True

    async def takeoff(self, altitude: float) -> bool:
        self.altitude = altitude
        return True

    async def land(self) -> bool:
        self.altitude = 0
        return True

    async def move(self, dx: float, dy: float, dz: float) -> bool:
        self.altitude += dz
        return True

    async def get_telemetry(self) -> Dict:
        return {
            "altitude": self.altitude,
            "battery": self.battery,
            "gps_sats": 8
        }

    async def emergency_stop(self) -> bool:
        self.altitude = 0
        return True
```

### 5.2 Configuration and Deployment

```python
from dataclasses import dataclass
import yaml

@dataclass
class AgentConfig:
    """Configuration for SafeReActDroneAgent."""

    # Model settings
    ollama_host: str = "http://localhost:11434"
    model: str = "llama3.1:8b"

    # Safety limits
    max_altitude: float = 120.0
    max_speed: float = 15.0
    min_battery: float = 15.0
    min_gps_sats: int = 6

    # Execution limits
    max_iterations: int = 10
    default_timeout: float = 5.0
    emergency_timeout: float = 1.0

    # ReAct settings
    enable_streaming: bool = False
    verbose_logging: bool = True

    @classmethod
    def from_yaml(cls, path: str) -> "AgentConfig":
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)

# Example config file (config.yaml)
EXAMPLE_CONFIG = """
ollama_host: http://localhost:11434
model: llama3.1:8b
max_altitude: 120.0
max_speed: 15.0
min_battery: 15.0
max_iterations: 10
default_timeout: 5.0
enable_streaming: false
verbose_logging: true
"""
```

---

## 6. Summary and Best Practices

### Key Takeaways

1. **Ollama Tool Calling**
   - Use `/api/chat` with `tools` parameter
   - Follow OpenAI-compatible function schema
   - Support multi-turn conversations with tool results
   - Use `format` parameter for structured outputs

2. **ReAct Pattern Implementation**
   - Enforce strict Thought -> Action -> Observation format
   - Implement iteration limits to prevent infinite loops
   - Use regex parsing to extract structured components
   - Maintain conversation history for context

3. **Safety-Critical Design**
   - Implement tool whitelisting with registry
   - Use Pydantic for rigorous parameter validation
   - Add bounds checking for all physical parameters
   - Implement timeout handling for all async operations
   - Create comprehensive emergency stop mechanisms

4. **Production Considerations**
   - Mock hardware interface for safe testing
   - Configuration-driven behavior
   - Comprehensive logging for incident analysis
   - Graceful degradation on component failure

### Testing Strategy

```python
def test_safety_bounds():
    """Test that safety constraints are enforced."""
    safety = SafetyManager()

    # Should reject altitude exceeding limit
    is_safe, reason = safety.validate_action(
        "move_relative",
        {"up": 200},
        {"altitude": 0}
    )
    assert not is_safe
    assert "exceeds" in reason.lower()

def test_emergency_stop():
    """Test emergency stop functionality."""
    safety = SafetyManager()

    # Trigger emergency
    safety.trigger_emergency("test")

    # All actions except emergency_stop should be blocked
    is_safe, _ = safety.validate_action("takeoff", {"altitude": 10}, {})
    assert not is_safe

    # Emergency stop should be allowed
    is_safe, _ = safety.validate_action("emergency_stop", {}, {})
    assert is_safe
```

---

## References

- Ollama Documentation: https://github.com/ollama/ollama/blob/main/docs/api.md
- ReAct Paper: "ReAct: Synergizing Reasoning and Acting in Language Models"
- Pydantic Documentation: https://docs.pydantic.dev/
- Drone Safety Standards: ISO 21384-3:2019
