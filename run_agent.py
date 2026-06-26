#!/usr/bin/env python3
"""
Direct agent runner script for SP-Mind using Claude SDK Agent.

Usage:
    # With native Anthropic API:
    python run_agent.py "Your prompt here" --api-key sk-ant-...
    
    # With proxy API:
    python run_agent.py "Your prompt here" --base-url http://proxy:3888/ --auth-token sk-...
    
    # Using environment variables:
    export ANTHROPIC_API_KEY=sk-ant-...  # Native API
    # OR
    export ANTHROPIC_BASE_URL=http://proxy:3888/
    export ANTHROPIC_AUTH_TOKEN=sk-...
    python run_agent.py "Your prompt here"
    
    # Other options:
    python run_agent.py "Your prompt here" --output-dir ./output_logs
    python run_agent.py --prompt-file prompt.txt --output-dir ./output_logs
    
The script will automatically save logs with timestamps.
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Run SP-Mind agent with Claude SDK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
API Configuration:
  Native Anthropic API:
    --api-key KEY           or set ANTHROPIC_API_KEY env var
    
  Proxy API:
    --base-url URL          or set ANTHROPIC_BASE_URL env var
    --auth-token TOKEN      or set ANTHROPIC_AUTH_TOKEN env var
    
  Priority: Command-line args > Environment variables
        """,
    )
    
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt to send to the agent",
    )
    
    parser.add_argument(
        "--prompt-file", "-f",
        type=str,
        help="Read prompt from a file instead of command line",
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=str,
        default="./agent_logs",
        help="Directory to save logs (default: ./agent_logs)",
    )
    
    parser.add_argument(
        "--log-prefix",
        type=str,
        default="agent",
        help="Prefix for log filename (default: agent)",
    )
    
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="claude-sonnet-4-5",
        help="Model to use (default: claude-sonnet-4-5)",
    )
    
    parser.add_argument(
        "--skip-permissions",
        action="store_true",
        default=True,
        help="Skip permission prompts (--dangerously-skip-permissions). Default: True for automated runs.",
    )
    
    parser.add_argument(
        "--require-permissions",
        action="store_true",
        help="Require permission prompts (overrides --skip-permissions)",
    )
    
    parser.add_argument(
        "--no-skill",
        action="store_true",
        dest="no_skill",
        help="Disable skill injection (except quantification basic skill for quantification tasks)",
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=True,
        help="Show detailed progress (default: True)",
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress verbose output",
    )
    
    # API Configuration
    api_group = parser.add_argument_group("API Configuration")
    
    api_group.add_argument(
        "--api-key",
        type=str,
        help="Native Anthropic API key (overrides ANTHROPIC_API_KEY env var)",
    )
    
    api_group.add_argument(
        "--base-url",
        type=str,
        help="Custom API base URL for proxy (overrides ANTHROPIC_BASE_URL env var)",
    )
    
    api_group.add_argument(
        "--auth-token",
        type=str,
        help="Auth token for proxy API (overrides ANTHROPIC_AUTH_TOKEN env var)",
    )
    
    args = parser.parse_args()
    
    # Get the prompt
    if args.prompt_file:
        with open(args.prompt_file, "r") as f:
            prompt = f.read().strip()
    elif args.prompt:
        prompt = args.prompt
    else:
        print("Error: Please provide a prompt or use --prompt-file")
        parser.print_help()
        sys.exit(1)
    
    # Configure API environment
    api_mode = "unknown"
    env = os.environ.copy()
    
    # Priority: command-line args > environment variables
    if args.api_key:
        # Native Anthropic API via command-line
        env["ANTHROPIC_API_KEY"] = args.api_key
        # Clear proxy settings if using native API
        env.pop("ANTHROPIC_BASE_URL", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)
        api_mode = "native"
    elif args.base_url or args.auth_token:
        # Proxy API via command-line
        if args.base_url:
            env["ANTHROPIC_BASE_URL"] = args.base_url
        if args.auth_token:
            env["ANTHROPIC_AUTH_TOKEN"] = args.auth_token
        # Clear native API key if using proxy
        env.pop("ANTHROPIC_API_KEY", None)
        api_mode = "proxy"
    elif os.environ.get("ANTHROPIC_API_KEY"):
        # Native API via environment variable
        api_mode = "native (env)"
    elif os.environ.get("ANTHROPIC_BASE_URL") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        # Proxy API via environment variables
        api_mode = "proxy (env)"
    else:
        print("⚠️  Warning: No API credentials configured.")
        print("   Set ANTHROPIC_API_KEY for native API, or")
        print("   Set ANTHROPIC_BASE_URL + ANTHROPIC_AUTH_TOKEN for proxy API.")
        print()
    
    # Create output directory
    output_dir = Path(args.output_dir)
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate log filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = output_dir / f"{args.log_prefix}_{timestamp}.log"
    
    # Build the command
    cmd = [sys.executable, "-m", "spmind.cli"]
    
    # Add options
    if args.verbose and not args.quiet:
        cmd.append("-v")
    
    if args.model:
        cmd.extend(["--model", args.model])
    
    if args.skip_permissions and not args.require_permissions:
        cmd.append("--dangerously-skip-permissions")
    
    if args.no_skill:
        cmd.append("--no-skill")
    
    # Add the prompt
    cmd.append(prompt)
    
    # Determine API info for display (hide actual keys)
    api_info = api_mode
    if api_mode == "native" or api_mode == "native (env)":
        key = env.get("ANTHROPIC_API_KEY", os.environ.get("ANTHROPIC_API_KEY", ""))
        if key:
            api_info = f"native API (key: {key[:10]}...{key[-4:]})"
    elif api_mode == "proxy" or api_mode == "proxy (env)":
        url = env.get("ANTHROPIC_BASE_URL", os.environ.get("ANTHROPIC_BASE_URL", ""))
        api_info = f"proxy API ({url})"
    
    # Print header
    header = f"""{'=' * 70}
SP-MIND AGENT RUNNER
{'=' * 70}
Timestamp: {datetime.now().isoformat()}
Model: {args.model or 'default'}
API: {api_info}
Log file: {log_file}
{'=' * 70}

PROMPT:
{prompt}

{'=' * 70}
"""
    print(header)
        
    # Open log file and run command
    with open(log_file, "w", encoding="utf-8") as log:
        # Write header to log
        log.write(header)
        log.flush()
        
        # Run the CLI and capture output
        try:
            # Force unbuffered output from the child Python process
            env["PYTHONUNBUFFERED"] = "1"
            env["SPMIND_TEMPERATURE"] = "1.0"
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=env,
            )
        
            # Stream output to both console and log file
            for line in iter(process.stdout.readline, ''):
                print(line, end='')
                log.write(line)
                log.flush()
            
            process.wait()
            
            # Write footer
            footer = f"""
{'=' * 70}
EXECUTION COMPLETE
{'=' * 70}
Exit code: {process.returncode}
Log saved to: {log_file}
{'=' * 70}
"""
            print(footer)
            log.write(footer)
            
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted by user")
            log.write("\n\n⚠️  Interrupted by user\n")
            process.terminate()
            sys.exit(130)
        except Exception as e:
            error_msg = f"\n\n❌ Error: {e}\n"
            print(error_msg)
            log.write(error_msg)
            sys.exit(1)
    
    print(f"\n✅ Done! Log saved to: {log_file}")


if __name__ == "__main__":
    main()
