#!/usr/bin/env python3
"""
Generate additional SP-Bench benchmark queries using an LLM.

Reads existing queries from sp_bench.jsonl as few-shot examples, prompts the
LLM to generate new queries for a given category, and appends them to the
benchmark file.

Usage:
    python create_benchmark.py --category SIGNAL_CALIBRATION --num 5
    python create_benchmark.py --category GRAND_PIPELINE --num 3 --provider gemini
    python create_benchmark.py --category SEGMENTATION --num 4 --provider openai --model gpt-5
    python create_benchmark.py --list-categories
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

BENCH_PATH = Path(__file__).parent / "sp_bench.jsonl"

SYSTEM_PROMPT = """\
You are an expert in spatial proteomics analysis pipelines. Your task is to \
generate realistic natural language benchmark queries that a researcher might \
use to instruct an AI agent to orchestrate fluorescence-based spatial \
proteomics analysis tools.

Rules:
1. Each query must be a plausible instruction a bioinformatician would give.
2. Use {input_dir} for input data paths, {output_dir} for output paths, \
{markers_csv} for marker metadata files, and {illum_profiles_dir} for \
illumination profile directories.
3. Include a mix of general queries (default parameters) and context-specific \
queries (specifying non-default parameter values, channel indices, methods).
4. Vary the phrasing, tone, and level of detail across queries — avoid \
repetitive sentence structures.
5. Return ONLY a valid JSON array of objects. Each object must have exactly \
these fields: "query" (str), "context_specific" (bool).
6. Do NOT include any text outside the JSON array — no markdown fences, no \
commentary."""


def load_bench() -> list[dict]:
    records = []
    with open(BENCH_PATH) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def get_category_examples(records: list[dict], category: str) -> list[dict]:
    return [r for r in records if r["category"] == category]


def get_category_meta(examples: list[dict]) -> dict:
    first = examples[0]
    return {
        "tier": first["tier"],
        "stages": first["stages"],
        "num_stages": first["num_stages"],
    }


def list_categories(records: list[dict]) -> None:
    cats: dict[str, dict] = {}
    for r in records:
        c = r["category"]
        if c not in cats:
            cats[c] = {
                "tier": r["tier"],
                "stages": r["stages"],
                "num_stages": r["num_stages"],
                "count": 0,
            }
        cats[c]["count"] += 1

    print(f"{'Category':<35} {'Tier':<15} {'Stages':<6} {'Queries':<7}")
    print("-" * 70)
    for cat, info in cats.items():
        print(
            f"{cat:<35} {info['tier']:<15} {info['num_stages']:<6} {info['count']:<7}"
        )


def build_prompt(examples: list[dict], num_queries: int) -> str:
    meta = get_category_meta(examples)
    example_queries = []
    for ex in examples:
        example_queries.append(
            json.dumps(
                {"query": ex["query"], "context_specific": ex["context_specific"]},
                ensure_ascii=False,
            )
        )

    return f"""\
Generate {num_queries} new benchmark queries for the following spatial \
proteomics task category.

Category: {examples[0]["category"]}
Tier: {meta["tier"]}
Pipeline stages involved: {", ".join(meta["stages"])}
Number of stages: {meta["num_stages"]}

Here are the existing queries for this category (use these as style and \
content references, but do NOT duplicate them):

{chr(10).join(example_queries)}

Now generate {num_queries} NEW and DIVERSE queries for this same category. \
Return a JSON array of {num_queries} objects, each with "query" and \
"context_specific" fields."""


def parse_llm_json(raw: str) -> list[dict]:
    """Extract and parse a JSON array from LLM output, tolerating markdown fences."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    results = json.loads(cleaned)
    if not isinstance(results, list):
        raise ValueError("LLM output is not a JSON array")

    for item in results:
        if "query" not in item or "context_specific" not in item:
            raise ValueError(
                f"Missing required fields in generated item: {list(item.keys())}"
            )

    return results


def generate_queries(
    category: str,
    num_queries: int,
    provider: str,
    model: str | None,
    temperature: float,
    max_tokens: int,
    dry_run: bool,
) -> list[dict]:
    records = load_bench()
    examples = get_category_examples(records, category)
    if not examples:
        available = sorted({r["category"] for r in records})
        print(f"Error: category '{category}' not found.", file=sys.stderr)
        print(f"Available: {', '.join(available)}", file=sys.stderr)
        sys.exit(1)

    meta = get_category_meta(examples)
    prompt = build_prompt(examples, num_queries)

    if dry_run:
        print("=== SYSTEM PROMPT ===")
        print(SYSTEM_PROMPT)
        print("\n=== USER PROMPT ===")
        print(prompt)
        return []

    if provider == "openai":
        import openai
        from llm import get_openai_response

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY not set.", file=sys.stderr)
            sys.exit(1)
        client = openai.OpenAI(api_key=api_key)
        model = model or "gpt-5"
        raw = get_openai_response(
            client,
            prompt,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    elif provider == "gemini":
        from google import genai
        from llm import get_gemini_response

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            print("Error: GOOGLE_API_KEY not set.", file=sys.stderr)
            sys.exit(1)
        client = genai.Client(api_key=api_key)
        model = model or "gemini-3-pro"
        raw = get_gemini_response(
            client,
            prompt,
            system_prompt=SYSTEM_PROMPT,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:
        print(f"Error: unknown provider '{provider}'.", file=sys.stderr)
        sys.exit(1)

    print(f"LLM response received ({len(raw)} chars, model={model})")

    generated = parse_llm_json(raw)

    existing_count = len(examples)
    new_records = []
    for i, item in enumerate(generated, start=existing_count + 1):
        record = {
            "id": f"{category.lower()}_{i:03d}",
            "query": item["query"],
            "tier": meta["tier"],
            "category": category,
            "stages": meta["stages"],
            "num_stages": meta["num_stages"],
            "context_specific": item["context_specific"],
        }
        new_records.append(record)

    return new_records


def append_to_bench(new_records: list[dict]) -> None:
    with open(BENCH_PATH, "a") as f:
        for rec in new_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate additional SP-Bench benchmark queries using an LLM."
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Task category to generate queries for (e.g. SIGNAL_CALIBRATION).",
    )
    parser.add_argument(
        "--num", type=int, default=5, help="Number of queries to generate."
    )
    parser.add_argument(
        "--provider",
        choices=["openai", "gemini"],
        default="openai",
        help="LLM provider to use.",
    )
    parser.add_argument("--model", type=str, default=None, help="Override model name.")
    parser.add_argument(
        "--temperature", type=float, default=0.7, help="Sampling temperature."
    )
    parser.add_argument(
        "--max-tokens", type=int, default=4096, help="Max tokens for LLM response."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the prompt without calling the LLM.",
    )
    parser.add_argument(
        "--no-append",
        action="store_true",
        help="Print generated queries without appending to sp_bench.jsonl.",
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List all available categories and exit.",
    )

    args = parser.parse_args()

    if args.list_categories:
        records = load_bench()
        list_categories(records)
        return

    if not args.category:
        parser.error("--category is required (or use --list-categories)")

    new_records = generate_queries(
        category=args.category,
        num_queries=args.num,
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        dry_run=args.dry_run,
    )

    if args.dry_run or not new_records:
        return

    print(f"\nGenerated {len(new_records)} queries:\n")
    for rec in new_records:
        print(json.dumps(rec, indent=2, ensure_ascii=False))
        print()

    if args.no_append:
        print("(--no-append: not writing to sp_bench.jsonl)")
    else:
        append_to_bench(new_records)
        print(f"Appended {len(new_records)} queries to {BENCH_PATH}")


if __name__ == "__main__":
    main()
