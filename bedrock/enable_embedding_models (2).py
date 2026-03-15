#!/usr/bin/env python3
"""
Enable Amazon Bedrock Embedding Models

Replicates the console workflow:
  - Invoke each embedding model with a test text input
  - First invocation triggers auto-subscribe/enable

Embedding models convert text into numerical vectors (lists of numbers).
They are used for semantic search, RAG, and knowledge base indexing.

Prerequisites:
  - AWS credentials configured (CLI profile, env vars, or IAM role)
  - IAM permissions required:
      * bedrock:InvokeModel
      * aws-marketplace:Subscribe         (for 3rd-party models like Cohere)
      * aws-marketplace:ViewSubscriptions  (for 3rd-party models like Cohere)
  - pip install boto3 (>= 1.35.0)

Usage:
  # Enable specific embedding models using aliases
  python enable_embedding_models.py titan-embed-v2 cohere-embed-en cohere-embed-multi

  # Enable using full model IDs
  python enable_embedding_models.py amazon.titan-embed-text-v2:0 cohere.embed-english-v3

  # Specify region and profile
  python enable_embedding_models.py --region us-west-2 --profile ops-role titan-embed-v2

  # List available aliases
  python enable_embedding_models.py --list-aliases

  # Show embedding dimensions reference
  python enable_embedding_models.py --show-dimensions
"""

import argparse
import json
import logging
import sys
import time

import boto3
from botocore.exceptions import ClientError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Embedding model alias map
# ---------------------------------------------------------------------------
EMBEDDING_ALIASES = {
    # Amazon Titan Embeddings
    "titan-embed-v2":           "amazon.titan-embed-text-v2:0",
    "titan-embed-v1":           "amazon.titan-embed-text-v1",
    "titan-embed-image":        "amazon.titan-embed-image-v1",
    "titan-multimodal-embed":   "amazon.titan-embed-image-v1",
    # Cohere Embed
    "cohere-embed-en":          "cohere.embed-english-v3",
    "cohere-embed-multi":       "cohere.embed-multilingual-v3",
    # Amazon Nova Embed (if available in your region)
    "nova-embed":               "amazon.nova-embed-v1:0",
}

# ---------------------------------------------------------------------------
# Embedding dimensions reference (useful for KB config)
# ---------------------------------------------------------------------------
EMBEDDING_INFO = {
    "amazon.titan-embed-text-v2:0":  {"dims": 1024, "max_tokens": 8192, "notes": "Configurable: 256, 512, 1024"},
    "amazon.titan-embed-text-v1":    {"dims": 1536, "max_tokens": 8192, "notes": "Fixed 1536 dimensions"},
    "amazon.titan-embed-image-v1":   {"dims": 1024, "max_tokens": 128,  "notes": "Text + image multimodal"},
    "cohere.embed-english-v3":       {"dims": 1024, "max_tokens": 512,  "notes": "English optimized"},
    "cohere.embed-multilingual-v3":  {"dims": 1024, "max_tokens": 512,  "notes": "100+ languages"},
    "amazon.nova-embed-v1:0":       {"dims": 1024, "max_tokens": 8192, "notes": "Nova embedding model"},
}


def resolve_model_id(alias_or_id: str) -> str:
    """Resolve shorthand alias to full model ID, or pass through as-is."""
    return EMBEDDING_ALIASES.get(alias_or_id.lower(), alias_or_id)


def detect_provider(model_id: str) -> str:
    """Detect provider from model ID."""
    model_lower = model_id.lower()
    if "amazon" in model_lower or "titan" in model_lower or "nova" in model_lower:
        return "amazon"
    elif "cohere" in model_lower:
        return "cohere"
    return "unknown"


# ---------------------------------------------------------------------------
# Invoke embedding model
# Each provider has a slightly different request/response format
# ---------------------------------------------------------------------------
def invoke_titan_embed(runtime_client, model_id: str, text: str) -> dict:
    """Invoke Amazon Titan embedding model."""
    body = json.dumps({"inputText": text})

    try:
        response = runtime_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        embedding = result.get("embedding", [])
        return {
            "success": True,
            "dimensions": len(embedding),
            "sample_values": embedding[:5] if embedding else [],
            "input_tokens": result.get("inputTextTokenCount", 0),
        }
    except ClientError as e:
        return {
            "success": False,
            "error_code": e.response["Error"]["Code"],
            "error_message": e.response["Error"].get("Message", ""),
        }


def invoke_titan_embed_v2(runtime_client, model_id: str, text: str) -> dict:
    """Invoke Amazon Titan Embed V2 (supports configurable dimensions)."""
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,
        "normalize": True,
    })

    try:
        response = runtime_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        embedding = result.get("embedding", [])
        return {
            "success": True,
            "dimensions": len(embedding),
            "sample_values": embedding[:5] if embedding else [],
            "input_tokens": result.get("inputTextTokenCount", 0),
        }
    except ClientError as e:
        return {
            "success": False,
            "error_code": e.response["Error"]["Code"],
            "error_message": e.response["Error"].get("Message", ""),
        }


def invoke_cohere_embed(runtime_client, model_id: str, text: str) -> dict:
    """Invoke Cohere embedding model."""
    body = json.dumps({
        "texts": [text],
        "input_type": "search_document",
    })

    try:
        response = runtime_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        embeddings = result.get("embeddings", [[]])
        embedding = embeddings[0] if embeddings else []
        return {
            "success": True,
            "dimensions": len(embedding),
            "sample_values": embedding[:5] if embedding else [],
            "input_tokens": 0,  # Cohere doesn't return token count the same way
        }
    except ClientError as e:
        return {
            "success": False,
            "error_code": e.response["Error"]["Code"],
            "error_message": e.response["Error"].get("Message", ""),
        }


def invoke_nova_embed(runtime_client, model_id: str, text: str) -> dict:
    """Invoke Amazon Nova embedding model."""
    body = json.dumps({
        "inputText": text,
    })

    try:
        response = runtime_client.invoke_model(
            modelId=model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read())
        embedding = result.get("embedding", [])
        return {
            "success": True,
            "dimensions": len(embedding),
            "sample_values": embedding[:5] if embedding else [],
            "input_tokens": result.get("inputTextTokenCount", 0),
        }
    except ClientError as e:
        return {
            "success": False,
            "error_code": e.response["Error"]["Code"],
            "error_message": e.response["Error"].get("Message", ""),
        }


def invoke_embedding_model(runtime_client, model_id: str, text: str) -> dict:
    """
    Route to the correct invoke function based on model ID.
    Each embedding provider has a different request body format.
    """
    model_lower = model_id.lower()

    if "titan-embed-text-v2" in model_lower:
        return invoke_titan_embed_v2(runtime_client, model_id, text)
    elif "titan-embed" in model_lower:
        return invoke_titan_embed(runtime_client, model_id, text)
    elif "cohere.embed" in model_lower:
        return invoke_cohere_embed(runtime_client, model_id, text)
    elif "nova-embed" in model_lower or "nova.embed" in model_lower:
        return invoke_nova_embed(runtime_client, model_id, text)
    else:
        # Generic fallback — try Titan format
        logger.info(f"  Unknown embedding format for {model_id}, trying Titan format...")
        return invoke_titan_embed(runtime_client, model_id, text)


# ---------------------------------------------------------------------------
# Main enable workflow per model
# ---------------------------------------------------------------------------
def enable_model(
    runtime_client,
    model_id: str,
    test_text: str,
    region: str,
    max_retries: int = 3,
    retry_delay: int = 30,
) -> dict:
    """
    Enable an embedding model by invoking it:
      1. Invoke with test text (triggers auto-enablement)
      2. Retry if AccessDenied (subscription may take up to 15 min)
      3. Report embedding dimensions on success
    """
    result = {
        "model_id": model_id,
        "provider": detect_provider(model_id),
        "status": "UNKNOWN",
        "dimensions": 0,
    }

    logger.info(f"\n{'='*60}")
    logger.info(f"Model:    {model_id}")
    logger.info(f"Provider: {result['provider']}")

    # Show expected dimensions
    info = EMBEDDING_INFO.get(model_id)
    if info:
        logger.info(f"Expected: {info['dims']} dims, {info['max_tokens']} max tokens")
        logger.info(f"Notes:    {info['notes']}")
    logger.info(f"{'='*60}")

    logger.info(f"  Invoking with test text: \"{test_text[:60]}\"")

    for attempt in range(1, max_retries + 1):
        logger.info(f"  Attempt {attempt}/{max_retries}...")

        invoke_result = invoke_embedding_model(runtime_client, model_id, test_text)

        if invoke_result["success"]:
            dims = invoke_result["dimensions"]
            sample = invoke_result["sample_values"]
            tokens = invoke_result.get("input_tokens", 0)

            logger.info(f"  SUCCESS — Embedding generated!")
            logger.info(f"  Dimensions: {dims}")
            logger.info(f"  Tokens:     {tokens}")
            logger.info(f"  Sample:     {[round(v, 6) for v in sample[:3]]}...")
            result["status"] = "ENABLED"
            result["dimensions"] = dims
            return result

        # Handle errors
        error_code = invoke_result.get("error_code", "")
        error_msg = invoke_result.get("error_message", "")

        if error_code == "AccessDeniedException":
            if attempt < max_retries:
                logger.info(
                    f"  Access denied (subscription likely in progress). "
                    f"Waiting {retry_delay}s before retry..."
                )
                time.sleep(retry_delay)
                continue
            else:
                logger.error(f"  Access denied after {max_retries} attempts.")
                logger.error(f"  Error: {error_msg}")
                logger.error(f"  Possible causes:")
                logger.error(f"    - IAM policy missing bedrock:InvokeModel for this model")
                logger.error(f"    - SCP blocking this model")
                logger.error(f"    - aws-marketplace:Subscribe permission missing (Cohere)")
                logger.error(f"    - Model not available in {region}")
                result["status"] = "ACCESS_DENIED"
                return result

        elif error_code == "ResourceNotFoundException":
            logger.error(f"  Model {model_id} not found in region {region}.")
            result["status"] = "NOT_FOUND_IN_REGION"
            return result

        elif error_code == "ModelNotReadyException":
            if attempt < max_retries:
                logger.info(f"  Model not ready yet. Waiting {retry_delay}s...")
                time.sleep(retry_delay)
                continue
            result["status"] = "NOT_READY"
            return result

        elif error_code == "ThrottlingException":
            if attempt < max_retries:
                wait = retry_delay * attempt
                logger.info(f"  Throttled. Waiting {wait}s...")
                time.sleep(wait)
                continue
            result["status"] = "THROTTLED"
            return result

        elif error_code == "ValidationException":
            logger.error(f"  Validation error (wrong request format?): {error_msg}")
            result["status"] = "VALIDATION_ERROR"
            return result

        else:
            logger.error(f"  Unexpected error: [{error_code}] {error_msg}")
            result["status"] = f"ERROR:{error_code}"
            return result

    result["status"] = "FAILED_AFTER_RETRIES"
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Enable Bedrock embedding models by invoking them (replicates console workflow)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s titan-embed-v2 cohere-embed-en cohere-embed-multi
  %(prog)s amazon.titan-embed-text-v2:0 cohere.embed-english-v3
  %(prog)s --region us-west-2 --profile ops-role titan-embed-v2
  %(prog)s --list-aliases
  %(prog)s --show-dimensions
""",
    )

    parser.add_argument(
        "models", nargs="*",
        help="Embedding model IDs or aliases to enable",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument(
        "--text",
        default="This is a test sentence for embedding model enablement.",
        help="Test text to embed",
    )
    parser.add_argument("--retries", type=int, default=3, help="Max retries per model (default: 3)")
    parser.add_argument("--retry-delay", type=int, default=30, help="Seconds between retries (default: 30)")
    parser.add_argument("--list-aliases", action="store_true", help="Show available shorthand aliases")
    parser.add_argument("--show-dimensions", action="store_true", help="Show embedding dimensions reference")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # List aliases
    if args.list_aliases:
        print(f"\n{'Alias':<25} {'Model ID':<45} {'Provider'}")
        print("-" * 85)
        for alias, mid in sorted(EMBEDDING_ALIASES.items()):
            print(f"{alias:<25} {mid:<45} {detect_provider(mid)}")
        return

    # Show dimensions reference
    if args.show_dimensions:
        print(f"\n{'Model ID':<40} {'Dims':<8} {'Max Tokens':<12} {'Notes'}")
        print("-" * 100)
        for mid, info in sorted(EMBEDDING_INFO.items()):
            print(f"{mid:<40} {info['dims']:<8} {info['max_tokens']:<12} {info['notes']}")
        return

    if not args.models:
        parser.error("Provide model IDs or aliases. Use --list-aliases or --show-dimensions.")

    # Resolve aliases
    resolved = []
    for m in args.models:
        rid = resolve_model_id(m)
        if rid != m:
            logger.info(f"Resolved '{m}' -> '{rid}'")
        resolved.append(rid)

    # Create runtime client
    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    runtime_client = session.client("bedrock-runtime")

    providers = set(detect_provider(m) for m in resolved)

    print(f"\n{'#'*60}")
    print(f"  Bedrock Embedding Model Enablement")
    print(f"  Region:    {args.region}")
    print(f"  Models:    {len(resolved)}")
    print(f"  Providers: {', '.join(sorted(providers))}")
    print(f"  Retries:   {args.retries} (delay: {args.retry_delay}s)")
    print(f"{'#'*60}")

    # Process each model
    results = []
    for model_id in resolved:
        result = enable_model(
            runtime_client=runtime_client,
            model_id=model_id,
            test_text=args.text,
            region=args.region,
            max_retries=args.retries,
            retry_delay=args.retry_delay,
        )
        results.append(result)

    # Summary
    print(f"\n{'#'*60}")
    print("  SUMMARY")
    print(f"{'#'*60}")
    print(f"  {'Model ID':<45} {'Provider':<10} {'Dims':<8} {'Status'}")
    print(f"  {'-'*85}")

    success_count = 0
    for r in results:
        status_icon = "OK" if r["status"] == "ENABLED" else "FAIL"
        dims_str = str(r["dimensions"]) if r["dimensions"] > 0 else "-"
        print(f"  {r['model_id']:<45} {r['provider']:<10} {dims_str:<8} [{status_icon}] {r['status']}")
        if r["status"] == "ENABLED":
            success_count += 1

    print(f"\n  Enabled: {success_count}/{len(results)}")

    # Reminder about Terraform
    if success_count > 0:
        print(f"\n  REMINDER: If these models are new to your environment,")
        print(f"  update allowed_foundation_model_ids in your Terraform")
        print(f"  module's inputs.tf or team tfvars as needed.")

    if success_count < len(results):
        print(f"\n  Troubleshooting failed models:")
        print(f"    1. Check IAM: bedrock:InvokeModel allowed for the model ARN?")
        print(f"    2. Check SCP: is the model blocked by Service Control Policy?")
        print(f"    3. Check region: is the model available in {args.region}?")
        print(f"    4. For Cohere: aws-marketplace:Subscribe permission?")
        sys.exit(1)


if __name__ == "__main__":
    main()
