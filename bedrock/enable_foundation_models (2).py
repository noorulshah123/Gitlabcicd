#!/usr/bin/env python3
"""
Enable Amazon Bedrock Foundation Models (Text Generation / Multimodal)

Replicates the console workflow using INFERENCE PROFILE IDs:
  - For most models: invoke with a test prompt (auto-enables on first call)
  - For Anthropic/Claude: submit use case form first, then invoke
  - Supports geographic prefixes: au (Australia), us, eu, ap, global

The modelId field accepts: inference profile IDs, model IDs, or ARNs.
  - Inference profile ID: au.anthropic.claude-sonnet-4-6    (recommended)
  - Model ID:             anthropic.claude-sonnet-4-6-v1:0  (fails for newer models)
  - ARN:                  arn:aws:bedrock:...                (only needed in IAM policies)

Prerequisites:
  - AWS credentials configured (CLI profile, env vars, or IAM role)
  - IAM permissions: bedrock:InvokeModel, bedrock:PutUseCaseForModelAccess,
                     aws-marketplace:Subscribe, aws-marketplace:ViewSubscriptions
  - pip install boto3 (>= 1.35.0)

Usage:
  # Default: ap-southeast-2, Australia (au.) prefix
  python enable_foundation_models.py nova2-lite claude-sonnet-4.6 mistral-large

  # Use global prefix (routes to any region, ~10% cheaper)
  python enable_foundation_models.py --prefix global claude-sonnet-4.6

  # Specify region and profile
  python enable_foundation_models.py --region us-east-1 --prefix us nova2-lite

  # Enable a whole provider family
  python enable_foundation_models.py claude-all mistral-all

  # List all aliases and groups
  python enable_foundation_models.py --list-aliases
  python enable_foundation_models.py --list-groups
"""

import argparse
import json
import logging
import sys
import time

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Base model IDs (without prefix) — prefix is applied at resolve time
# Models marked "needs_profile=True" MUST use an inference profile prefix
# Models marked "needs_profile=False" use the direct ID as-is (older models)
# ---------------------------------------------------------------------------
MODEL_CATALOG = {
    # Amazon Nova 2
    "nova2-lite":           {"id": "amazon.nova-2-lite-v1:0",                       "needs_profile": True,  "provider": "amazon"},
    "nova2-sonic":          {"id": "amazon.nova-2-sonic-v1:0",                      "needs_profile": True,  "provider": "amazon"},
    "nova2-premier":        {"id": "amazon.nova-2-premier-v1:0",                    "needs_profile": True,  "provider": "amazon"},
    # Amazon Nova 1
    "nova-pro":             {"id": "amazon.nova-pro-v1:0",                          "needs_profile": True,  "provider": "amazon"},
    "nova-lite":            {"id": "amazon.nova-lite-v1:0",                         "needs_profile": True,  "provider": "amazon"},
    "nova-micro":           {"id": "amazon.nova-micro-v1:0",                        "needs_profile": True,  "provider": "amazon"},
    # Amazon Titan (older — direct ID works)
    "titan-text-express":   {"id": "amazon.titan-text-express-v1",                  "needs_profile": False, "provider": "amazon"},
    "titan-text-lite":      {"id": "amazon.titan-text-lite-v1",                     "needs_profile": False, "provider": "amazon"},
    "titan-text-premier":   {"id": "amazon.titan-text-premier-v1:0",                "needs_profile": False, "provider": "amazon"},
    # Anthropic Claude
    "claude-sonnet-4.6":    {"id": "anthropic.claude-sonnet-4-6",                   "needs_profile": True,  "provider": "anthropic"},
    "claude-opus-4.6":      {"id": "anthropic.claude-opus-4-6-v1",                  "needs_profile": True,  "provider": "anthropic"},
    "claude-sonnet-4.5":    {"id": "anthropic.claude-sonnet-4-5-20250929-v1:0",     "needs_profile": True,  "provider": "anthropic"},
    "claude-opus-4":        {"id": "anthropic.claude-opus-4-1-20250805-v1:0",       "needs_profile": True,  "provider": "anthropic"},
    "claude-sonnet-4":      {"id": "anthropic.claude-sonnet-4-20250514-v1:0",       "needs_profile": True,  "provider": "anthropic"},
    "claude-haiku-4.5":     {"id": "anthropic.claude-haiku-4-5-20251001-v1:0",      "needs_profile": True,  "provider": "anthropic"},
    "claude-sonnet-3.5":    {"id": "anthropic.claude-3-5-sonnet-20241022-v2:0",     "needs_profile": True,  "provider": "anthropic"},
    "claude-haiku-3":       {"id": "anthropic.claude-3-haiku-20240307-v1:0",        "needs_profile": True,  "provider": "anthropic"},
    # Meta Llama
    "llama3.3-70b":         {"id": "meta.llama3-3-70b-instruct-v1:0",              "needs_profile": True,  "provider": "meta"},
    "llama3.1-405b":        {"id": "meta.llama3-1-405b-instruct-v1:0",             "needs_profile": True,  "provider": "meta"},
    "llama3.1-70b":         {"id": "meta.llama3-1-70b-instruct-v1:0",              "needs_profile": True,  "provider": "meta"},
    "llama3.1-8b":          {"id": "meta.llama3-1-8b-instruct-v1:0",               "needs_profile": True,  "provider": "meta"},
    # Mistral
    "mistral-large":        {"id": "mistral.mistral-large-2407-v1:0",               "needs_profile": False, "provider": "mistral"},
    "mistral-small":        {"id": "mistral.mistral-small-2402-v1:0",               "needs_profile": False, "provider": "mistral"},
    "mixtral-8x7b":         {"id": "mistral.mixtral-8x7b-instruct-v0:1",            "needs_profile": False, "provider": "mistral"},
    "mistral-7b":           {"id": "mistral.mistral-7b-instruct-v0:2",              "needs_profile": False, "provider": "mistral"},
    # Cohere
    "command-r-plus":       {"id": "cohere.command-r-plus-v1:0",                    "needs_profile": False, "provider": "cohere"},
    "command-r":            {"id": "cohere.command-r-v1:0",                         "needs_profile": False, "provider": "cohere"},
    # AI21
    "jamba-1.5-large":      {"id": "ai21.jamba-1-5-large-v1:0",                    "needs_profile": False, "provider": "ai21"},
    "jamba-1.5-mini":       {"id": "ai21.jamba-1-5-mini-v1:0",                     "needs_profile": False, "provider": "ai21"},
}

# ---------------------------------------------------------------------------
# Group aliases — expand to multiple models
# ---------------------------------------------------------------------------
MODEL_GROUPS = {
    "nova2-all":        ["nova2-lite", "nova2-sonic", "nova2-premier"],
    "nova1-all":        ["nova-pro", "nova-lite", "nova-micro"],
    "nova-all":         ["nova2-lite", "nova2-sonic", "nova2-premier", "nova-pro", "nova-lite", "nova-micro"],
    "claude-latest":    ["claude-sonnet-4.6", "claude-opus-4.6"],
    "claude-all":       ["claude-sonnet-4.6", "claude-opus-4.6", "claude-sonnet-4.5", "claude-haiku-4.5"],
    "mistral-all":      ["mistral-large", "mistral-small", "mixtral-8x7b", "mistral-7b"],
    "llama-all":        ["llama3.3-70b", "llama3.1-405b", "llama3.1-70b", "llama3.1-8b"],
    "cohere-all":       ["command-r-plus", "command-r"],
    "ai21-all":         ["jamba-1.5-large", "jamba-1.5-mini"],
    "amazon-all":       ["nova2-lite", "nova2-sonic", "nova-pro", "nova-lite", "nova-micro",
                         "titan-text-express", "titan-text-lite"],
}

# ---------------------------------------------------------------------------
# Geographic prefix mapping
# ---------------------------------------------------------------------------
PREFIX_MAP = {
    "au":     "au",       # Australia (Sydney ↔ Melbourne)
    "us":     "us",       # US regions
    "eu":     "eu",       # EU regions
    "ap":     "ap",       # APAC regions
    "global": "global",   # Any commercial region worldwide
}


def resolve_model_ids(inputs: list, prefix: str) -> list:
    """
    Resolve a list of aliases/groups/raw IDs to final inference profile IDs.
    Applies geographic prefix to models that require inference profiles.
    Returns deduplicated list.
    """
    expanded = []
    for item in inputs:
        lower = item.lower()

        # Check group first
        if lower in MODEL_GROUPS:
            logger.info(f"Expanded group '{item}' -> {len(MODEL_GROUPS[lower])} models")
            for alias in MODEL_GROUPS[lower]:
                expanded.append(alias)
            continue

        # Single alias or raw ID
        expanded.append(item)

    # Resolve each to final model ID with prefix
    resolved = []
    for item in expanded:
        lower = item.lower()

        if lower in MODEL_CATALOG:
            entry = MODEL_CATALOG[lower]
            if entry["needs_profile"]:
                final_id = f"{prefix}.{entry['id']}"
                logger.info(f"  '{item}' -> '{final_id}' (inference profile)")
            else:
                final_id = entry["id"]
                logger.info(f"  '{item}' -> '{final_id}' (direct model ID)")
            resolved.append(final_id)
        else:
            # Assume raw model ID or inference profile ID — pass through
            resolved.append(item)

    # Deduplicate preserving order
    seen = set()
    unique = []
    for mid in resolved:
        if mid not in seen:
            seen.add(mid)
            unique.append(mid)
    return unique


def detect_provider(model_id: str) -> str:
    """Detect provider from model ID or inference profile ID."""
    ml = model_id.lower()
    if "anthropic" in ml or "claude" in ml:
        return "anthropic"
    elif "amazon" in ml or "titan" in ml or "nova" in ml:
        return "amazon"
    elif "meta" in ml or "llama" in ml:
        return "meta"
    elif "mistral" in ml or "mixtral" in ml:
        return "mistral"
    elif "cohere" in ml or "command" in ml:
        return "cohere"
    elif "ai21" in ml or "jamba" in ml:
        return "ai21"
    return "unknown"


# ---------------------------------------------------------------------------
# Use case submission (one-time for Anthropic)
# ---------------------------------------------------------------------------
def ensure_use_case_submitted(bedrock_client, region: str, profile: str = None):
    """Submit use case form if not already done (required for Anthropic models)."""
    try:
        bedrock_client.get_use_case_for_model_access()
        logger.info("  Use case already submitted.")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code not in ("ResourceNotFoundException", "ValidationException"):
            logger.warning(f"  Unexpected error: {e}")
            return False

    logger.info("  Submitting use case form...")
    form_data = {
        "industry": "Technology",
        "useCase": "Internal AI-powered applications and data analysis",
        "targetEndUsers": "Internal employees and developers",
        "expectedUsage": "Development and production workloads",
        "country": "Australia",
    }

    try:
        bedrock_client.put_use_case_for_model_access(formData=json.dumps(form_data))
        logger.info("  Use case submitted.")
        return True
    except ClientError as e:
        if region != "us-east-1":
            logger.info(f"  Failed in {region}, trying us-east-1...")
            try:
                kw = {"region_name": "us-east-1"}
                if profile:
                    kw["profile_name"] = profile
                boto3.Session(**kw).client("bedrock").put_use_case_for_model_access(
                    formData=json.dumps(form_data)
                )
                logger.info("  Use case submitted in us-east-1.")
                return True
            except ClientError as e2:
                logger.error(f"  Failed in both regions: {e2}")
                return False
        logger.error(f"  Failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Invoke via Converse API
# ---------------------------------------------------------------------------
def invoke_model_converse(runtime_client, model_id: str, prompt: str) -> dict:
    """Invoke a model using the unified Converse API."""
    try:
        response = runtime_client.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 100, "temperature": 0.1},
        )
        output = response.get("output", {}).get("message", {})
        text = "".join(b.get("text", "") for b in output.get("content", []))
        usage = response.get("usage", {})
        return {
            "success": True,
            "response_text": text[:200],
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        }
    except ClientError as e:
        return {
            "success": False,
            "error_code": e.response["Error"]["Code"],
            "error_message": e.response["Error"].get("Message", ""),
        }


# ---------------------------------------------------------------------------
# Enable one model
# ---------------------------------------------------------------------------
def enable_model(
    bedrock_client, runtime_client, model_id, prompt, region,
    profile=None, max_retries=3, retry_delay=30,
):
    """Enable a model by invoking it. Handles use case + retries."""
    provider = detect_provider(model_id)
    result = {"model_id": model_id, "provider": provider, "status": "UNKNOWN", "response_preview": ""}

    logger.info(f"\n{'='*60}")
    logger.info(f"Model:    {model_id}")
    logger.info(f"Provider: {provider}")
    logger.info(f"{'='*60}")

    # Use case for Anthropic
    if provider == "anthropic":
        logger.info("  [Step 1] Checking Anthropic use case form...")
        if not ensure_use_case_submitted(bedrock_client, region, profile):
            result["status"] = "USE_CASE_FAILED"
            return result
    else:
        logger.info("  [Step 1] No use case needed.")

    # Invoke
    logger.info(f"  [Step 2] Invoking: \"{prompt[:60]}\"")

    for attempt in range(1, max_retries + 1):
        logger.info(f"  Attempt {attempt}/{max_retries}...")
        r = invoke_model_converse(runtime_client, model_id, prompt)

        if r["success"]:
            logger.info(f"  SUCCESS — {r['response_text'][:120]}")
            logger.info(f"  Tokens: {r['input_tokens']} in / {r['output_tokens']} out")
            result["status"] = "ENABLED"
            result["response_preview"] = r["response_text"][:100]
            return result

        ec = r.get("error_code", "")
        em = r.get("error_message", "")

        if ec == "AccessDeniedException":
            if attempt < max_retries:
                logger.info(f"  Access denied — waiting {retry_delay}s (subscription may be in progress)...")
                time.sleep(retry_delay)
                continue
            logger.error(f"  Access denied after {max_retries} attempts: {em}")
            result["status"] = "ACCESS_DENIED"
            return result

        elif ec == "ResourceNotFoundException":
            logger.error(f"  Not found in {region}: {em}")
            result["status"] = "NOT_FOUND"
            return result

        elif ec == "ValidationException" and "on-demand throughput" in em.lower():
            logger.error(f"  This model requires an inference profile ID (with prefix).")
            logger.error(f"  Try: --prefix au  or  --prefix global")
            result["status"] = "NEEDS_INFERENCE_PROFILE"
            return result

        elif ec in ("ModelNotReadyException", "ThrottlingException"):
            if attempt < max_retries:
                wait = retry_delay * (2 if ec == "ThrottlingException" else 1)
                logger.info(f"  {ec} — waiting {wait}s...")
                time.sleep(wait)
                continue
            result["status"] = ec
            return result

        else:
            logger.error(f"  [{ec}] {em}")
            result["status"] = f"ERROR:{ec}"
            return result

    result["status"] = "FAILED_AFTER_RETRIES"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Enable Bedrock foundation models (with inference profile support)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s nova2-lite claude-sonnet-4.6 mistral-large
  %(prog)s --prefix global claude-all
  %(prog)s --prefix us --region us-east-1 nova2-all
  %(prog)s --list-aliases
  %(prog)s --list-groups
""",
    )
    parser.add_argument("models", nargs="*", help="Model aliases, groups, or raw IDs")
    parser.add_argument("--region", default="ap-southeast-2", help="AWS region (default: ap-southeast-2)")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument("--prefix", default="au", choices=["au", "us", "eu", "ap", "global"],
                        help="Geographic prefix for inference profiles (default: au)")
    parser.add_argument("--prompt", default="Reply with exactly: Hello, model enabled successfully.",
                        help="Test prompt")
    parser.add_argument("--retries", type=int, default=3, help="Max retries (default: 3)")
    parser.add_argument("--retry-delay", type=int, default=30, help="Seconds between retries (default: 30)")
    parser.add_argument("--list-aliases", action="store_true", help="Show all model aliases")
    parser.add_argument("--list-groups", action="store_true", help="Show all group aliases")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_aliases:
        print(f"\n{'Alias':<22} {'Needs Profile':<15} {'Provider':<12} {'Base Model ID'}")
        print("-" * 100)
        for alias, info in sorted(MODEL_CATALOG.items()):
            pf = "Yes" if info["needs_profile"] else "No (direct)"
            print(f"{alias:<22} {pf:<15} {info['provider']:<12} {info['id']}")
        print(f"\nPrefix '{args.prefix}' will be applied to 'Yes' models.")
        print(f"Example: claude-sonnet-4.6 -> {args.prefix}.anthropic.claude-sonnet-4-6")
        return

    if args.list_groups:
        print(f"\n{'Group':<18} {'Expands to'}")
        print("-" * 70)
        for group, aliases in sorted(MODEL_GROUPS.items()):
            print(f"{group:<18} {', '.join(aliases)}")
        return

    if not args.models:
        parser.error("Provide model aliases/groups/IDs. Use --list-aliases or --list-groups.")

    prefix = PREFIX_MAP[args.prefix]
    resolved = resolve_model_ids(args.models, prefix)
    providers = set(detect_provider(m) for m in resolved)

    # Create clients
    skw = {"region_name": args.region}
    if args.profile:
        skw["profile_name"] = args.profile
    session = boto3.Session(**skw)
    bedrock_client = session.client("bedrock")
    runtime_client = session.client("bedrock-runtime")

    print(f"\n{'#'*60}")
    print(f"  Bedrock Foundation Model Enablement")
    print(f"  Region:    {args.region}")
    print(f"  Prefix:    {prefix}. (geographic routing)")
    print(f"  Models:    {len(resolved)}")
    print(f"  Providers: {', '.join(sorted(providers))}")
    print(f"{'#'*60}")

    results = []
    for mid in resolved:
        r = enable_model(bedrock_client, runtime_client, mid, args.prompt,
                         args.region, args.profile, args.retries, args.retry_delay)
        results.append(r)

    # Summary
    print(f"\n{'#'*60}")
    print("  SUMMARY")
    print(f"{'#'*60}")
    print(f"  {'Model ID':<50} {'Provider':<12} {'Status'}")
    print(f"  {'-'*85}")

    ok = 0
    for r in results:
        icon = "OK" if r["status"] == "ENABLED" else "FAIL"
        print(f"  {r['model_id']:<50} {r['provider']:<12} [{icon}] {r['status']}")
        if r["status"] == "ENABLED":
            ok += 1

    print(f"\n  Enabled: {ok}/{len(results)}")

    if ok < len(results):
        print(f"\n  Troubleshooting:")
        print(f"    1. NEEDS_INFERENCE_PROFILE → use --prefix au or --prefix global")
        print(f"    2. ACCESS_DENIED → check IAM: bedrock:InvokeModel + inference-profile/* resource")
        print(f"    3. NOT_FOUND → model may not be available in {args.region}")
        print(f"    4. For Claude → was use case form accepted?")
        print(f"    5. For Cohere/Mistral → aws-marketplace:Subscribe permission?")
        sys.exit(1)


if __name__ == "__main__":
    main()
