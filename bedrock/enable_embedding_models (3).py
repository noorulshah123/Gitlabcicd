#!/usr/bin/env python3
"""
Enable Amazon Bedrock Embedding Models

Replicates the console workflow using INFERENCE PROFILE IDs where needed:
  - Invoke each embedding model with test text (auto-enables on first call)
  - Supports geographic prefixes: au (Australia), us, eu, ap, global

Prerequisites:
  - AWS credentials configured (CLI profile, env vars, or IAM role)
  - IAM permissions: bedrock:InvokeModel, aws-marketplace:Subscribe,
                     aws-marketplace:ViewSubscriptions
  - pip install boto3 (>= 1.35.0)

Usage:
  # Default: ap-southeast-2, Australia (au.) prefix
  python enable_embedding_models.py titan-embed-v2 cohere-embed-en cohere-embed-multi

  # Use global prefix
  python enable_embedding_models.py --prefix global titan-embed-v2

  # Enable all embedding models
  python enable_embedding_models.py embed-all

  # Show dimensions reference
  python enable_embedding_models.py --show-dimensions
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
# Embedding model catalog
# ---------------------------------------------------------------------------
EMBED_CATALOG = {
    # Amazon Titan Embeddings (older — direct ID works)
    "titan-embed-v2":       {"id": "amazon.titan-embed-text-v2:0",    "needs_profile": False, "provider": "amazon",
                             "dims": 1024, "max_tokens": 8192, "notes": "Configurable: 256, 512, 1024"},
    "titan-embed-v1":       {"id": "amazon.titan-embed-text-v1",      "needs_profile": False, "provider": "amazon",
                             "dims": 1536, "max_tokens": 8192, "notes": "Fixed 1536 dimensions"},
    "titan-embed-image":    {"id": "amazon.titan-embed-image-v1",     "needs_profile": False, "provider": "amazon",
                             "dims": 1024, "max_tokens": 128,  "notes": "Text + image multimodal"},
    # Cohere Embed (marketplace — direct ID works)
    "cohere-embed-en":      {"id": "cohere.embed-english-v3",         "needs_profile": False, "provider": "cohere",
                             "dims": 1024, "max_tokens": 512,  "notes": "English optimized"},
    "cohere-embed-multi":   {"id": "cohere.embed-multilingual-v3",    "needs_profile": False, "provider": "cohere",
                             "dims": 1024, "max_tokens": 512,  "notes": "100+ languages"},
    # Amazon Nova Embed (newer — may need profile)
    "nova-embed":           {"id": "amazon.nova-embed-v1:0",          "needs_profile": True,  "provider": "amazon",
                             "dims": 1024, "max_tokens": 8192, "notes": "Nova embedding model"},
}

# ---------------------------------------------------------------------------
# Group aliases
# ---------------------------------------------------------------------------
EMBED_GROUPS = {
    "titan-embed-all":  ["titan-embed-v2", "titan-embed-v1", "titan-embed-image"],
    "cohere-embed-all": ["cohere-embed-en", "cohere-embed-multi"],
    "embed-all":        ["titan-embed-v2", "titan-embed-v1", "titan-embed-image",
                         "cohere-embed-en", "cohere-embed-multi", "nova-embed"],
}

# ---------------------------------------------------------------------------
# Geographic prefix mapping
# ---------------------------------------------------------------------------
PREFIX_MAP = {
    "au":     "au",
    "us":     "us",
    "eu":     "eu",
    "ap":     "ap",
    "global": "global",
}


def resolve_model_ids(inputs: list, prefix: str) -> list:
    """Resolve aliases/groups to final model IDs with prefix where needed."""
    expanded = []
    for item in inputs:
        lower = item.lower()
        if lower in EMBED_GROUPS:
            logger.info(f"Expanded group '{item}' -> {len(EMBED_GROUPS[lower])} models")
            expanded.extend(EMBED_GROUPS[lower])
        else:
            expanded.append(item)

    resolved = []
    for item in expanded:
        lower = item.lower()
        if lower in EMBED_CATALOG:
            entry = EMBED_CATALOG[lower]
            if entry["needs_profile"]:
                final_id = f"{prefix}.{entry['id']}"
                logger.info(f"  '{item}' -> '{final_id}' (inference profile)")
            else:
                final_id = entry["id"]
                logger.info(f"  '{item}' -> '{final_id}' (direct model ID)")
            resolved.append(final_id)
        else:
            resolved.append(item)

    # Deduplicate
    seen = set()
    return [m for m in resolved if m not in seen and not seen.add(m)]


def detect_provider(model_id: str) -> str:
    ml = model_id.lower()
    if "amazon" in ml or "titan" in ml or "nova" in ml:
        return "amazon"
    elif "cohere" in ml:
        return "cohere"
    return "unknown"


# ---------------------------------------------------------------------------
# Provider-specific invoke functions
# ---------------------------------------------------------------------------
def invoke_titan_embed_v2(client, model_id, text):
    body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    try:
        resp = client.invoke_model(modelId=model_id, contentType="application/json",
                                   accept="application/json", body=body)
        result = json.loads(resp["body"].read())
        emb = result.get("embedding", [])
        return {"success": True, "dimensions": len(emb), "sample": emb[:5],
                "tokens": result.get("inputTextTokenCount", 0)}
    except ClientError as e:
        return {"success": False, "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"].get("Message", "")}


def invoke_titan_embed(client, model_id, text):
    body = json.dumps({"inputText": text})
    try:
        resp = client.invoke_model(modelId=model_id, contentType="application/json",
                                   accept="application/json", body=body)
        result = json.loads(resp["body"].read())
        emb = result.get("embedding", [])
        return {"success": True, "dimensions": len(emb), "sample": emb[:5],
                "tokens": result.get("inputTextTokenCount", 0)}
    except ClientError as e:
        return {"success": False, "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"].get("Message", "")}


def invoke_cohere_embed(client, model_id, text):
    body = json.dumps({"texts": [text], "input_type": "search_document"})
    try:
        resp = client.invoke_model(modelId=model_id, contentType="application/json",
                                   accept="application/json", body=body)
        result = json.loads(resp["body"].read())
        embs = result.get("embeddings", [[]])
        emb = embs[0] if embs else []
        return {"success": True, "dimensions": len(emb), "sample": emb[:5], "tokens": 0}
    except ClientError as e:
        return {"success": False, "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"].get("Message", "")}


def invoke_nova_embed(client, model_id, text):
    body = json.dumps({"inputText": text})
    try:
        resp = client.invoke_model(modelId=model_id, contentType="application/json",
                                   accept="application/json", body=body)
        result = json.loads(resp["body"].read())
        emb = result.get("embedding", [])
        return {"success": True, "dimensions": len(emb), "sample": emb[:5],
                "tokens": result.get("inputTextTokenCount", 0)}
    except ClientError as e:
        return {"success": False, "error_code": e.response["Error"]["Code"],
                "error_message": e.response["Error"].get("Message", "")}


def invoke_embedding(client, model_id, text):
    """Route to correct invoke function based on model ID."""
    ml = model_id.lower()
    if "titan-embed-text-v2" in ml:
        return invoke_titan_embed_v2(client, model_id, text)
    elif "titan-embed" in ml:
        return invoke_titan_embed(client, model_id, text)
    elif "cohere.embed" in ml:
        return invoke_cohere_embed(client, model_id, text)
    elif "nova" in ml and "embed" in ml:
        return invoke_nova_embed(client, model_id, text)
    else:
        logger.info(f"  Unknown format for {model_id}, trying Titan format...")
        return invoke_titan_embed(client, model_id, text)


# ---------------------------------------------------------------------------
# Enable one embedding model
# ---------------------------------------------------------------------------
def enable_model(runtime_client, model_id, text, region, max_retries=3, retry_delay=30):
    provider = detect_provider(model_id)
    result = {"model_id": model_id, "provider": provider, "status": "UNKNOWN", "dimensions": 0}

    logger.info(f"\n{'='*60}")
    logger.info(f"Model:    {model_id}")
    logger.info(f"Provider: {provider}")
    logger.info(f"{'='*60}")
    logger.info(f"  Invoking with: \"{text[:60]}\"")

    for attempt in range(1, max_retries + 1):
        logger.info(f"  Attempt {attempt}/{max_retries}...")
        r = invoke_embedding(runtime_client, model_id, text)

        if r["success"]:
            logger.info(f"  SUCCESS — {r['dimensions']} dimensions")
            logger.info(f"  Tokens: {r['tokens']}")
            logger.info(f"  Sample: {[round(v, 6) for v in r['sample'][:3]]}...")
            result["status"] = "ENABLED"
            result["dimensions"] = r["dimensions"]
            return result

        ec = r.get("error_code", "")
        em = r.get("error_message", "")

        if ec == "AccessDeniedException":
            if attempt < max_retries:
                logger.info(f"  Access denied — waiting {retry_delay}s...")
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
            logger.error(f"  Needs inference profile. Try --prefix au or --prefix global")
            result["status"] = "NEEDS_INFERENCE_PROFILE"
            return result

        elif ec in ("ModelNotReadyException", "ThrottlingException"):
            if attempt < max_retries:
                time.sleep(retry_delay)
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
        description="Enable Bedrock embedding models (with inference profile support)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s titan-embed-v2 cohere-embed-en cohere-embed-multi
  %(prog)s --prefix global embed-all
  %(prog)s --list-aliases
  %(prog)s --show-dimensions
""",
    )
    parser.add_argument("models", nargs="*", help="Embedding model aliases, groups, or raw IDs")
    parser.add_argument("--region", default="ap-southeast-2", help="AWS region (default: ap-southeast-2)")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument("--prefix", default="au", choices=["au", "us", "eu", "ap", "global"],
                        help="Geographic prefix for inference profiles (default: au)")
    parser.add_argument("--text", default="This is a test sentence for embedding model enablement.",
                        help="Test text to embed")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=int, default=30)
    parser.add_argument("--list-aliases", action="store_true")
    parser.add_argument("--list-groups", action="store_true")
    parser.add_argument("--show-dimensions", action="store_true")
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.list_aliases:
        print(f"\n{'Alias':<22} {'Profile?':<14} {'Provider':<10} {'Dims':<8} {'Model ID'}")
        print("-" * 95)
        for alias, info in sorted(EMBED_CATALOG.items()):
            pf = "Yes" if info["needs_profile"] else "No"
            print(f"{alias:<22} {pf:<14} {info['provider']:<10} {info['dims']:<8} {info['id']}")
        return

    if args.list_groups:
        print(f"\n{'Group':<20} {'Expands to'}")
        print("-" * 60)
        for g, aliases in sorted(EMBED_GROUPS.items()):
            print(f"{g:<20} {', '.join(aliases)}")
        return

    if args.show_dimensions:
        print(f"\n{'Model ID':<40} {'Dims':<8} {'Max Tokens':<12} {'Notes'}")
        print("-" * 100)
        for alias, info in sorted(EMBED_CATALOG.items()):
            print(f"{info['id']:<40} {info['dims']:<8} {info['max_tokens']:<12} {info['notes']}")
        return

    if not args.models:
        parser.error("Provide model aliases/groups/IDs. Use --list-aliases, --list-groups, or --show-dimensions.")

    prefix = PREFIX_MAP[args.prefix]
    resolved = resolve_model_ids(args.models, prefix)

    skw = {"region_name": args.region}
    if args.profile:
        skw["profile_name"] = args.profile
    runtime_client = boto3.Session(**skw).client("bedrock-runtime")

    print(f"\n{'#'*60}")
    print(f"  Bedrock Embedding Model Enablement")
    print(f"  Region:  {args.region}")
    print(f"  Prefix:  {prefix}.")
    print(f"  Models:  {len(resolved)}")
    print(f"{'#'*60}")

    results = []
    for mid in resolved:
        r = enable_model(runtime_client, mid, args.text, args.region, args.retries, args.retry_delay)
        results.append(r)

    # Summary
    print(f"\n{'#'*60}")
    print("  SUMMARY")
    print(f"{'#'*60}")
    print(f"  {'Model ID':<40} {'Provider':<10} {'Dims':<8} {'Status'}")
    print(f"  {'-'*80}")

    ok = 0
    for r in results:
        icon = "OK" if r["status"] == "ENABLED" else "FAIL"
        dims = str(r["dimensions"]) if r["dimensions"] > 0 else "-"
        print(f"  {r['model_id']:<40} {r['provider']:<10} {dims:<8} [{icon}] {r['status']}")
        if r["status"] == "ENABLED":
            ok += 1

    print(f"\n  Enabled: {ok}/{len(results)}")
    if ok > 0:
        print(f"\n  REMINDER: Update allowed_foundation_model_ids in Terraform if needed.")
        print(f"  For Knowledge Bases, ensure embedding_model_name matches the model ID.")

    if ok < len(results):
        sys.exit(1)


if __name__ == "__main__":
    main()
