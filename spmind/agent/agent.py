"""
SP-Mind Agent using the Claude Agent SDK.

Requirements:
    - Claude Code CLI: npm install -g @anthropic-ai/claude-code
    - Logged in: claude login
    - Python SDK: pip install claude-agent-sdk
"""

import asyncio
import os
from pathlib import Path
from typing import Any, AsyncIterator

from claude_agent_sdk import query, ClaudeAgentOptions

from spmind.config import default_config
from spmind.utils import read_module2api


# Skill retrieval configuration
SKILL_KEYWORDS = {
    "annotation/cell_type_annotation.md": [
        "annotation", "annotate", "cell type", "celltype", "cell-type",
        "label cells", "identify cell", "cluster annotation"
    ],
    "clustering/cell_clustering.md": [
        "cluster", "clustering", "phenograph", "leiden", "louvain",
        "group cells", "cell population"
    ],
    "segmentation/cell_segmentation.md": [
        "segment", "segmentation", "unmicst", "s3segmenter", "cell mask",
        "nucleus detection", "cell detection"
    ],
    "imaging/illumination_correction.md": [
        "illumination", "flat-field", "dark-field", "ffp", "dfp",
        "basic_illumination", "correction profile"
    ],
    "imaging/stitching.md": [
        "stitch", "stitching", "ashlar", "register", "align",
        "tile", "mosaic"
    ],
    "imaging/background_subtraction.md": [
        "background subtraction", "subtract background", "autofluorescence",
        "background_subtraction", "backsub"
    ],
    "quantification/cell_quantification.md": [
        "quantif", "mcquant", "intensity", "expression",
        "measure marker", "extract feature"
    ],
}


class SPMindAgent:
    """SP-Mind Agent using the Claude Agent SDK.

    Uses Claude Code CLI and a Claude Pro/Max subscription.
    Multi-turn conversation is maintained via session_id.

    Usage:
        agent = SPMindAgent()

        # Synchronous (recommended for scripts and REPL)
        result = agent.go("Analyze this gene expression data")

        # Multi-turn conversation (automatically maintains session)
        result = agent.go("Follow up question")

        # Start new conversation
        agent.reset_session()

        # Async streaming
        async for msg in agent.go_stream("Your task"):
            print(msg)
    """

    def __init__(
        self,
        path: str | None = None,
        timeout_seconds: int | None = None,
        model: str | None = None,
        permission_mode: str = "default",
        no_skill: bool = False,
    ):
        """Initialize the Claude SDK Agent.

        Args:
            path: Path to the data directory.
            timeout_seconds: Timeout for code execution in seconds.
            model: Claude model identifier (e.g., "claude-sonnet-4-5").
            permission_mode: Permission strategy — "default" (requires approval),
                "acceptEdits" (auto-approves file edits), or "bypassPermissions"
                (fully autonomous).
            no_skill: If True, disable skill injection except the basic
                quantification skill for quantification tasks.
        """
        self._session_id: str | None = None

        # Use default_config values for unspecified parameters
        if path is None:
            path = default_config.path
        if timeout_seconds is None:
            timeout_seconds = default_config.timeout_seconds

        self.timeout_seconds = timeout_seconds
        self.model = model
        self.permission_mode = permission_mode
        self.no_skill = no_skill

        # Display configuration
        print("\n" + "=" * 50)
        print("🔧 SP-MIND AGENT CONFIGURATION")
        print("=" * 50)
        print("  Using: Official Claude Agent SDK")
        if model:
            print(f"  Model: {model}")
        print(f"  Permission Mode: {permission_mode}")
        print(f"  Timeout: {timeout_seconds}s")
        print("=" * 50 + "\n")

        # Ensure data directory exists
        os.makedirs(path, exist_ok=True)
        self.path = path

        # Load tool descriptions
        self.module2api = read_module2api()

        # Skills directory
        self.skills_dir = Path(__file__).parent.parent / "skills"

        # Build system prompt (without task-specific skill)
        self.base_system_prompt = self._build_base_system_prompt()
        self.system_prompt = self.base_system_prompt  # Default, updated per task

    def _load_skill(self, skill_path: str) -> str:
        """Load a skill file's content.

        Args:
            skill_path: Relative path within the skills directory
                (e.g., "annotation/cell_type_annotation.md").

        Returns:
            Skill content as string, or empty string if not found.
        """
        full_path = self.skills_dir / skill_path
        if full_path.exists():
            return full_path.read_text()
        return ""

    def _retrieve_skills(self, task: str) -> list[tuple[str, str]]:
        """Retrieve relevant skills based on keyword matching against the task.

        Args:
            task: The user's task description.

        Returns:
            List of (skill_name, skill_content) tuples for matching skills.
        """
        task_lower = task.lower()
        matched = []
        seen_paths = set()

        if self.no_skill:
            quant_keywords = SKILL_KEYWORDS.get("quantification/cell_quantification.md", [])
            for keyword in quant_keywords:
                if keyword in task_lower:
                    skill_content = self._load_skill("quantification/cell_quantification_basic.md")
                    if skill_content:
                        print("📚 Skill activated: Quantification > Cell Quantification Basic (no-skill mode)")
                        matched.append(("Quantification > Cell Quantification Basic", skill_content))
                    break
            return matched

        for skill_path, keywords in SKILL_KEYWORDS.items():
            if skill_path in seen_paths:
                continue
            for keyword in keywords:
                if keyword in task_lower:
                    skill_content = self._load_skill(skill_path)
                    if skill_content:
                        skill_name = skill_path.replace("/", " > ").replace(".md", "").replace("_", " ").title()
                        print(f"📚 Skill activated: {skill_name}")
                        matched.append((skill_name, skill_content))
                        seen_paths.add(skill_path)
                    break
        return matched

    def _build_system_prompt_with_skill(self, task: str) -> str:
        """Build system prompt with task-specific skills injected.

        Args:
            task: The user's task description.

        Returns:
            Complete system prompt with relevant skill sections appended.
        """
        skills = self._retrieve_skills(task)

        if skills:
            skill_sections = []
            for i, (name, content) in enumerate(skills, 1):
                skill_sections.append(f"### Skill {i}: {name}\n\n{content}")
            all_skills = "\n\n---\n\n".join(skill_sections)
            return f"""{self.base_system_prompt}

## 📚 ACTIVE SKILLS (Follow These Methodologies!)

{all_skills}
"""
        return self.base_system_prompt

    def _build_base_system_prompt(self) -> str:
        """Build the base system prompt listing available tools and guidelines."""
        tool_modules = list(self.module2api.keys())
        tool_modules_str = "\n".join([f"- {m}" for m in tool_modules])

        prompt = f"""You are SP-Mind, an expert spatial proteomics data analysis assistant.

## Your Environment
- Working directory: {self.path}

## Available SP-Mind Tool Modules
{tool_modules_str}

## Key SP-Mind Tools for Spatial Proteomics (MCMICRO Pipeline)

### Image Preprocessing & Stitching
- spmind.tool.basic_illumination: generate_illumination_profiles, batch_generate_illumination_profiles
- spmind.tool.registration: stitch_and_register_tiles_ashlar, align_cyclic_images_ashlar
- spmind.tool.background_subtraction: subtract_background

### TMA Dearraying (CRITICAL: Use this for TMA cores!)
- spmind.tool.unetcoreograph: dearray_tma, batch_dearray_tma
  - dearray_tma(input_image, output_dir, channel=0, downsample_factor=5)
  - Use channel parameter to specify DAPI/nuclear channel (0-indexed)

### Segmentation
- spmind.tool.segmentation_unmicst: generate_probability_maps, batch_generate_probability_maps
- spmind.tool.segmentation_s3segmenter: segment_cells, batch_segment_cells

### Quantification & Analysis
- spmind.tool.quantification: quantify_cells, batch_quantify_cells
- spmind.tool.clustering: cluster_cells, phenotype_cells_supervised
- spmind.tool.spatial_phlex: run_spatial_phlex_clustering_only, run_spatial_phlex_clustered_barrier

## How to Use SP-Mind Tools

### Step 1: Check function signature before using
```bash
python -c "from spmind.tool.unetcoreograph import dearray_tma; help(dearray_tma)"
```

### Step 2: Import and use the function
```bash
python -c "
from spmind.tool.unetcoreograph import dearray_tma
result = dearray_tma(
    input_image='path/to/tma.ome.tif',
    output_dir='path/to/output/',
    channel=2  # DAPI channel (0-indexed)
)
print(result)
"
```

For longer scripts, write to a file first and then execute it.

### IMPORTANT: Always check the correct module!
- TMA dearraying → spmind.tool.unetcoreograph (NOT imaging)
- Illumination correction → spmind.tool.basic_illumination (NOT imaging)
- Image stitching → spmind.tool.registration

## Container Runtime Note
SP-Mind tools auto-detect and use available container runtime (Docker, Apptainer, or Singularity).
- On Mac/local: Docker is preferred (start Docker Desktop if needed)
- On HPC cluster: Apptainer/Singularity is preferred
All tools accept `container_runtime` parameter: "auto" (default), "docker", "apptainer", "singularity"

## CRITICAL: Data-First Approach

When analyzing data (especially for tasks like cell type annotation, clustering, or quantification):

1. **EXPLORE DATA FIRST** - Before writing any analysis code:
   - Load the data and print its structure
   - Calculate summary statistics (mean, std, range) for each group/cluster
   - Print the actual values to understand the data distribution
   - Examine what markers/features are high or low for each group

2. **MAKE DATA-DRIVEN DECISIONS** - Base your analysis parameters on observed values:
   - Don't use generic thresholds (like 0.3) without checking the data
   - Look at actual expression ranges before setting cutoffs
   - Examine marker combinations, not just single markers

3. **ITERATE AND REFINE** - Don't write one big script:
   - Execute small code blocks and print results
   - Adjust your approach based on what you observe
   - Re-examine ambiguous cases

Example workflow for cell type annotation:
```python
# Step 1: Load and examine
df = pd.read_csv(input_file)
cluster_means = df.groupby('cluster')[marker_cols].mean()
print(cluster_means)  # LOOK at the values!

# Step 2: Identify patterns from the printed values
# e.g., "Cluster 11 has CD30=0.625, much higher than others (0.08-0.2)"
# → Use threshold like 0.5 for CD30, not a generic 0.1

# Step 3: Write annotation logic based on observed patterns
```

## Instructions
1. Analyze the user's biomedical task
2. **Explore and understand the data first** by printing intermediate results
3. Write and execute Python code using SP-Mind tools
4. Print results clearly and save plots to files
5. Explain your findings

Solve the user's task step by step using the available tools.
"""
        return prompt

    def _build_options(self, is_resume: bool = False) -> ClaudeAgentOptions:
        """Build ClaudeAgentOptions for the SDK query call.

        Args:
            is_resume: If True, resume from an existing session.

        Returns:
            Configured ClaudeAgentOptions instance.
        """
        options_dict = {
            "cwd": self.path,
            "permission_mode": self.permission_mode,
        }

        if not is_resume:
            options_dict["system_prompt"] = self.system_prompt

        if self.model:
            options_dict["model"] = self.model

        if is_resume and self._session_id:
            options_dict["resume"] = self._session_id

        return ClaudeAgentOptions(**options_dict)

    async def _run_async(self, prompt: str, verbose: bool = False) -> str:
        """Run the agent asynchronously via the Claude Agent SDK.

        Args:
            prompt: The user's task/query.
            verbose: If True, print detailed progress information.

        Returns:
            The agent's final text response.
        """
        is_resume = self._session_id is not None
        options = self._build_options(is_resume=is_resume)

        result_text = ""
        cost_usd = 0.0
        num_turns = 0

        try:
            async for message in query(prompt=prompt, options=options):
                msg_type = type(message).__name__

                if hasattr(message, 'session_id'):
                    self._session_id = message.session_id

                if verbose:
                    self._print_verbose_message(message, msg_type)

                if hasattr(message, 'content'):
                    for block in message.content:
                        if hasattr(block, 'text'):
                            result_text = block.text

                if hasattr(message, 'result'):
                    result_text = str(message.result)

                if hasattr(message, 'total_cost_usd'):
                    cost_usd = message.total_cost_usd
                if hasattr(message, 'num_turns'):
                    num_turns = message.num_turns
        except RuntimeError as e:
            if "cancel scope" in str(e):
                if verbose:
                    print(f"⚠️  SDK teardown warning (safe to ignore): {e}")
            else:
                raise

        if verbose and cost_usd > 0:
            print(f"💰 Cost: ${cost_usd:.4f} ({num_turns} turns)")

        return result_text

    def reset_session(self):
        """Reset the session so the next query starts a fresh conversation."""
        self._session_id = None

    @property
    def session_id(self) -> str | None:
        """Current session ID, or None if no session is active."""
        return self._session_id

    def _print_verbose_message(self, message, msg_type: str):
        """Print human-readable progress for a single SDK message."""
        if msg_type in ("SystemMessage", "SDKSystemMessage"):
            session_id = getattr(message, 'session_id', 'unknown')
            print(f"🚀 Session started: {session_id[:8]}...")

        elif msg_type == "AssistantMessage":
            # Check for tool use (ToolUseBlock) or text (TextBlock)
            if hasattr(message, 'content'):
                for block in message.content:
                    block_type = type(block).__name__
                    if block_type == "ToolUseBlock" or hasattr(block, 'name'):
                        tool_name = getattr(block, 'name', 'unknown')
                        print(f"🔧 Using tool: {tool_name}")
                        # Show tool input preview (increased to 200 chars)
                        if hasattr(block, 'input'):
                            input_preview = str(block.input)[:200]
                            if len(str(block.input)) > 200:
                                input_preview += "..."
                            print(f"   Input: {input_preview}")
                    elif block_type == "ThinkingBlock":
                        # Extended thinking (for thinking models)
                        thinking = getattr(block, 'thinking', '')[:80]
                        print(f"🧠 Thinking: {thinking}...")
                    elif hasattr(block, 'text') and block.text:
                        if 'error' in block.text.lower() or 'Error' in block.text:
                            print(f"💭 {block.text}")
                        else:
                            text_preview = block.text[:150].replace('\n', ' ')
                            if len(block.text) > 150:
                                text_preview += "..."
                            print(f"💭 {text_preview}")

        elif msg_type == "UserMessage":
            # Tool result (ToolResultBlock) - increased to 300 chars
            if hasattr(message, 'content'):
                for block in message.content:
                    if hasattr(block, 'content'):
                        result_preview = str(block.content)[:300].replace('\n', ' ')
                        if len(str(block.content)) > 300:
                            result_preview += "..."
                        is_error = getattr(block, 'is_error', False)
                        icon = "❌" if is_error else "✓"
                        print(f"   {icon} Result: {result_preview}")

        elif msg_type in ("ResultMessage", "SDKResultMessage"):
            is_error = getattr(message, 'is_error', False)
            if is_error:
                print("❌ Completed with error")
                # Print full error details
                if hasattr(message, 'result') and message.result:
                    print(f"   Error details: {message.result}")
            else:
                print("✅ Done")

    def go(self, prompt: str, verbose: bool = False) -> str:
        """Execute the agent synchronously and return the response.

        Args:
            prompt: The user's task/query.
            verbose: If True, print detailed progress information.

        Returns:
            The agent's final text response.
        """
        self.system_prompt = self._build_system_prompt_with_skill(prompt)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(self._run_async(prompt, verbose=verbose))
            return result
        finally:
            pending = asyncio.all_tasks(loop)
            for task in pending:
                task.cancel()
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    async def go_async(self, prompt: str, verbose: bool = False) -> str:
        """Execute the agent asynchronously and return the response.

        Args:
            prompt: The user's task/query.
            verbose: If True, print detailed progress information.

        Returns:
            The agent's final text response.
        """
        self.system_prompt = self._build_system_prompt_with_skill(prompt)
        return await self._run_async(prompt, verbose=verbose)

    async def go_stream(self, prompt: str) -> AsyncIterator[Any]:
        """Execute the agent and yield raw SDK messages as they arrive.

        Args:
            prompt: The user's task/query.

        Yields:
            SDK message objects (SystemMessage, AssistantMessage,
            UserMessage, ResultMessage).
        """
        self.system_prompt = self._build_system_prompt_with_skill(prompt)
        is_resume = self._session_id is not None
        options = self._build_options(is_resume=is_resume)

        async for message in query(prompt=prompt, options=options):
            if hasattr(message, 'session_id'):
                self._session_id = message.session_id
            yield message


def run_spmind_agent(prompt: str, **kwargs) -> str:
    """Create a one-shot agent, execute the prompt, and return the response.

    Args:
        prompt: The task to execute.
        **kwargs: Forwarded to SPMindAgent (path, model, permission_mode, etc.).

    Returns:
        The agent's final text response.
    """
    agent = SPMindAgent(**kwargs)
    return agent.go(prompt)
