"""
SP-Mind Command Line Interface.

Mimics Claude Code CLI behavior - starts interactive session by default,
use -p/--print for non-interactive output.

Based on official Claude Agent SDK patterns:
https://platform.claude.com/docs/en/agent-sdk/python
"""

import argparse
import sys

# Ensure UTF-8 encoding
sys.stdin.reconfigure(encoding='utf-8', errors='replace')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def main():
    parser = argparse.ArgumentParser(
        prog="spmind",
        usage="spmind [options] [prompt]",
        description="SP-Mind - starts an interactive session by default, use -p/--print for non-interactive output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )

    parser.add_argument(
        "prompt",
        nargs="?",
        help="Your prompt",
    )

    parser.add_argument(
        "-p", "--print",
        action="store_true",
        dest="print_mode",
        help="Print response and exit (non-interactive)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed progress",
    )

    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress intermediate steps and reasoning (interactive mode shows them by default)",
    )

    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Path to data directory",
    )

    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model to use (e.g., claude-sonnet-4-5)",
    )

    parser.add_argument(
        "--dangerously-skip-permissions",
        action="store_true",
        dest="skip_permissions",
        help="Skip permission prompts (use with caution)",
    )

    parser.add_argument(
        "--no-skill",
        action="store_true",
        dest="no_skill",
        help="Disable skill injection (except quantification basic skill for quantification tasks)",
    )

    parser.add_argument(
        "--version",
        action="store_true",
        help="Output the version number",
    )

    parser.add_argument(
        "-h", "--help",
        action="store_true",
        help="Display help for command",
    )

    args = parser.parse_args()

    if args.help:
        print_help()
        return

    if args.version:
        from spmind.version import __version__
        print(f"{__version__} (SP-Mind)")
        return

    # Determine permission mode
    permission_mode = "bypassPermissions" if args.skip_permissions else "default"

    # Initialize agent silently
    agent = init_agent(
        path=args.path,
        model=args.model,
        permission_mode=permission_mode,
        no_skill=args.no_skill,
    )

    if args.prompt and args.print_mode:
        # Print mode: just output the result and exit
        result = agent.go(args.prompt, verbose=args.verbose)
        print(result)
    else:
        # Interactive mode shows intermediate steps/reasoning by default,
        # unless --quiet is passed.
        verbose = not args.quiet
        run_interactive(agent, initial_prompt=args.prompt, verbose=verbose)


def print_help():
    """Print help in Claude Code style."""
    print("""Usage: spmind [options] [prompt]

SP-Mind - starts an interactive session by default, use -p/--print for
non-interactive output

Arguments:
  prompt                          Your prompt

Options:
  -p, --print                     Print response and exit (non-interactive)
  -v, --verbose                   Show detailed progress
  -q, --quiet                     Suppress intermediate steps/reasoning (interactive shows them by default)
  --path <path>                   Path to data directory
  --model <model>                 Model to use (e.g., claude-sonnet-4-5)
  --dangerously-skip-permissions  Skip permission prompts (use with caution)
  --version                       Output the version number
  -h, --help                      Display help for command
""")


def init_agent(
    path: str | None,
    model: str | None = None,
    permission_mode: str = "default",
    no_skill: bool = False,
):
    """Initialize the agent silently."""
    import io
    import contextlib

    with contextlib.redirect_stdout(io.StringIO()):
        from spmind.agent import SPMindAgent
        agent = SPMindAgent(
            path=path,
            model=model,
            permission_mode=permission_mode,
            no_skill=no_skill,
        )
    return agent


def run_interactive(agent, initial_prompt: str | None = None, verbose: bool = False):
    """Run interactive mode like Claude Code."""
    import shutil
    from spmind.version import __version__

    # Get terminal width
    term_width = shutil.get_terminal_size().columns

    # Print welcome banner
    print()
    print(f"\033[1;36m╭{'─' * (term_width - 2)}╮\033[0m")
    print(f"\033[1;36m│\033[0m{' ' * (term_width - 2)}\033[1;36m│\033[0m")
    title = f"🧬 SP-Mind v{__version__}"
    padding = (term_width - 2 - len(title) + 2) // 2  # +2 for emoji width
    print(f"\033[1;36m│\033[0m{' ' * padding}\033[1m{title}\033[0m{' ' * (term_width - 2 - padding - len(title) + 2)}\033[1;36m│\033[0m")
    subtitle = "Spatial Proteomics AI Agent (Claude Agent SDK)"
    padding2 = (term_width - 2 - len(subtitle)) // 2
    print(f"\033[1;36m│\033[0m{' ' * padding2}\033[90m{subtitle}\033[0m{' ' * (term_width - 2 - padding2 - len(subtitle))}\033[1;36m│\033[0m")
    print(f"\033[1;36m│\033[0m{' ' * (term_width - 2)}\033[1;36m│\033[0m")
    print(f"\033[1;36m╰{'─' * (term_width - 2)}╯\033[0m")
    print()

    # Tips
    print(f"\033[90m  cwd: {agent.path}\033[0m")
    if agent.model:
        print(f"\033[90m  model: {agent.model}\033[0m")
    print()
    print(f"\033[90m  Tips: Use \033[0m\033[33m/help\033[0m\033[90m for commands, \033[0m\033[33mCtrl+C\033[0m\033[90m to exit\033[0m")
    print()

    # Handle initial prompt if provided
    if initial_prompt:
        print(f"\033[1;32m❯\033[0m {initial_prompt}")
        print()
        try:
            result = agent.go(initial_prompt, verbose=verbose)
            print(result)
            print()
        except Exception as e:
            print(f"\033[31mError: {e}\033[0m")
            print()

    # Main loop
    while True:
        try:
            user_input = input(f"\033[1;32m❯\033[0m ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input[1:].lower().split()[0] if user_input[1:] else ""

                if cmd in ("exit", "quit", "q"):
                    break
                elif cmd == "help":
                    print_interactive_help()
                    continue
                elif cmd == "clear":
                    print("\033[2J\033[H", end="")
                    continue
                elif cmd == "new":
                    agent.reset_session()
                    print("\033[90mStarted new conversation.\033[0m")
                    print()
                    continue
                elif cmd == "session":
                    session_id = agent.session_id
                    if session_id:
                        print(f"\033[90mSession ID: {session_id}\033[0m")
                    else:
                        print("\033[90mNo active session.\033[0m")
                    print()
                    continue
                else:
                    print(f"\033[90mUnknown command: /{cmd}. Type /help for available commands.\033[0m")
                    print()
                    continue

            # Execute the task
            print()
            result = agent.go(user_input, verbose=verbose)
            print(result)
            print()

        except KeyboardInterrupt:
            print()
            break
        except EOFError:
            break
        except Exception as e:
            print(f"\n\033[31mError: {e}\033[0m\n")


def print_interactive_help():
    """Print interactive mode help."""
    print("""
\033[1mSlash Commands:\033[0m
  \033[33m/help\033[0m       Show this help message
  \033[33m/clear\033[0m      Clear the screen
  \033[33m/new\033[0m        Start a new conversation
  \033[33m/session\033[0m    Show current session ID
  \033[33m/exit\033[0m       Exit SP-Mind

\033[1mKeyboard Shortcuts:\033[0m
  \033[33mCtrl+C\033[0m      Exit SP-Mind

\033[1mExample Prompts:\033[0m
  \033[90mList files in the data directory\033[0m
  \033[90mWhat tools are available for cell segmentation?\033[0m
  \033[90mQuantify cells from spatial proteomics images\033[0m
  \033[90mCluster cells based on marker expression\033[0m
""")


if __name__ == "__main__":
    main()
