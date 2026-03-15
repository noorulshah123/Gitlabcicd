#!/usr/bin/env python3
"""
Enable Amazon Bedrock Foundation Models (Text Generation / Multimodal)

Replicates the console workflow:
  - For most models: invoke with a test prompt (auto-enables on first call)
  - For Anthropic/Claude: submit use case form first, then invoke

The first invocation triggers AWS to auto-subscribe/enable the model.
Subsequent invocations work normally.

Prerequisites:
  - AWS credentials configured (CLI profile, env vars, or IAM role)
  - IAM permissions required:
      * bedrock:InvokeModel
      * bedrock:InvokeModelWithResponseStream (optional)
      * bedrock:PutUseCaseForModelAccess  (for Anthropic models)
      * bedrock:GetUseCaseForModelAccess  (for Anthropic models)
      * aws-marketplace:Subscribe
      * aws-marketplace:ViewSubscriptions
  - pip install boto3 (>= 1.35.0)

Usage:
  # Enable specific models using aliases
  python enable_foundation_models.py nova2-lite nova2-sonic claude-sonnet-4.6

  # Enable using full model IDs
  python enable_foundation_models.py amazon.nova-2-lite-v1:0 mistral.mistral-large-2407-v1:0

  # Specify region and profile
  python enable_foundation_models.py --region us-west-2 --profile ops-role nova2-lite

  # Custom test prompt
  python enable_foundation_models.py --prompt "What is 2+2?" nova2-lite

  # List available aliases
  python enable_foundation_models.py --list-aliases
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
# Model alias map — shorthand to official Bedrock model IDs
# Run --list-aliases to see all, update as new models are released
# ---------------------------------------------------------------------------
MODEL_ALIASES = {
    # Amazon Nova 2
    "nova2-lite":           "amazon.nova-2-lite-v1:0",
    "nova2-sonic":          "amazon.nova-2-sonic-v1:0",
    "nova2-premier":        "us.amazon.nova-2-premier-v1:0",
    # Amazon Nova 1
    "nova-pro":             "amazon.nova-pro-v1:0",
    "nova-lite":            "amazon.nova-lite-v1:0",
    "nova-micro":           "amazon.nova-micro-v1:0",
    "nova-premier":         "us.amazon.nova-premier-v1:0",
    # Amazon Titan
    "titan-text-express":   "amazon.titan-text-express-v1",
    "titan-text-lite":      "amazon.titan-text-lite-v1",
    "titan-text-premier":   "amazon.titan-text-premier-v1:0",
    # Anthropic Claude
    "claude-sonnet-4.6":    "anthropic.claude-sonnet-4-6-v1:0",
    "claude-opus-4.6":      "anthropic.claude-opus-4-6-v1:0",
    "claude-sonnet-4.5":    "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-opus-4":        "us.anthropic.claude-opus-4-1-20250805-v1:0",
    "claude-sonnet-4":      "anthropic.claude-sonnet-4-20250514-v1:0",
    "claude-sonnet-3.5":    "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-haiku-3.5":     "anthropic.claude-3-5-haiku-20241022-v1:0",
    "claude-haiku-3":       "anthropic.claude-3-haiku-20240307-v1:0",
    # Meta Llama
    "llama3.3-70b":         "us.meta.llama3-3-70b-instruct-v1:0",
    "llama3.1-405b":        "meta.llama3-1-405b-instruct-v1:0",
    "llama3.1-70b":         "meta.llama3-1-70b-instruct-v1:0",
    "llama3.1-8b":          "meta.llama3-1-8b-instruct-v1:0",
    # Mistral
    "mistral-large":        "mistral.mistral-large-2407-v1:0",
    "mistral-small":        "mistral.mistral-small-2402-v1:0",
    "mixtral-8x7b":         "mistral.mixtral-8x7b-instruct-v0:1",
    "mistral-7b":           "mistral.mistral-7b-instruct-v0:2",
    # Cohere
    "command-r-plus":       "cohere.command-r-plus-v1:0",
    "command-r":            "cohere.command-r-v1:0",
    # AI21
    "jamba-1.5-large":      "ai21.jamba-1-5-large-v1:0",
    "jamba-1.5-mini":       "ai21.jamba-1-5-mini-v1:0",
}


def resolve_model_id(alias_or_id: str) -> str:
    """Resolve shorthand alias to full model ID, or pass through as-is."""
    return MODEL_ALIASES.get(alias_or_id.lower(), alias_or_id)


def detect_provider(model_id: str) -> str:
    """Detect the provider from the model ID."""
    model_lower = model_id.lower()
    if "anthropic" in model_lower or "claude" in model_lower:
        return "anthropic"
    elif "amazon" in model_lower or "titan" in model_lower or "nova" in model_lower:
        return "amazon"
    elif "meta" in model_lower or "llama" in model_lower:
        return "meta"
    elif "mistral" in model_lower or "mixtral" in model_lower:
        return "mistral"
    elif "cohere" in model_lower or "command" in model_lower:
        return "cohere"
    elif "ai21" in model_lower or "jamba" in model_lower:
        return "ai21"
    return "unknown"


# ---------------------------------------------------------------------------
# Use case submission (one-time, required for Anthropic/Claude)
# ---------------------------------------------------------------------------
def ensure_use_case_submitted(bedrock_client, region: str, profile: str = None):
    """
    Check if use case form has been submitted. If not, submit it.
    This is a one-time requirement per AWS account for Anthropic models.
    """
    try:
        bedrock_client.get_use_case_for_model_access()
        logger.info("  Use case already submitted for this account.")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code not in ("ResourceNotFoundException", "ValidationException"):
            logger.warning(f"  Unexpected error checking use case: {e}")
            return False

    logger.info("  No use case found. Submitting use case form...")

    form_data = {
        "industry": "Technology",
        "useCase": "Internal AI-powered applications and data analysis",
        "targetEndUsers": "Internal employees and developers",
        "expectedUsage": "Development and production workloads",
        "country": "United States",
    }

    try:
        bedrock_client.put_use_case_for_model_access(formData=json.dumps(form_data))
        logger.info("  Use case submitted successfully.")
        return True
    except ClientError as e:
        if region != "us-east-1":
            logger.info(f"  Failed in {region}, trying us-east-1...")
            try:
                session_kwargs = {"region_name": "us-east-1"}
                if profile:
                    session_kwargs["profile_name"] = profile
                fallback = boto3.Session(**session_kwargs).client("bedrock")
                fallback.put_use_case_for_model_access(formData=json.dumps(form_data))
                logger.info("  Use case submitted in us-east-1.")
                return True
            except ClientError as e2:
                logger.error(f"  Use case failed in both regions: {e2}")
                return False
        logger.error(f"  Use case submission failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Invoke model using Converse API (unified across all providers)
# ---------------------------------------------------------------------------
def invoke_model_converse(runtime_client, model_id: str, prompt: str) -> dict:
    """
    Invoke a model using the Converse API.
    This is the unified API that works the same across all providers.
    First invocation auto-enables/subscribes the model.
    """
    try:
        response = runtime_client.converse(
            modelId=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ],
            inferenceConfig={
                "maxTokens": 100,
                "temperature": 0.1,
            },
        )

        # Extract response text
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        response_text = ""
        for block in content_blocks:
            if "text" in block:
                response_text += block["text"]

        stop_reason = response.get("stopReason", "unknown")
        usage = response.get("usage", {})

        return {
            "success": True,
            "response_text": response_text[:200],
            "stop_reason": stop_reason,
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        }

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"].get("Message", "")
        return {
            "success": False,
            "error_code": error_code,
            "error_message": error_msg,
        }


# ---------------------------------------------------------------------------
# Main enable workflow per model
# ---------------------------------------------------------------------------
def enable_model(
    bedrock_client,
    runtime_client,
    model_id: str,
    prompt: str,
    region: str,
    profile: str = None,
    max_retries: int = 3,
    retry_delay: int = 30,
) -> dict:
    """
    Enable a model by invoking it (replicates console workflow):
      1. For Claude: submit use case first
      2. Invoke with test prompt (triggers auto-enablement)
      3. Retry if AccessDenied (subscription may take up to 15 min)
    """
    result = {
        "model_id": model_id,
        "provider": detect_provider(model_id),
        "status": "UNKNOWN",
        "response_preview": "",
    }

    logger.info(f"\n{'='*60}")
    logger.info(f"Model:    {model_id}")
    logger.info(f"Provider: {result['provider']}")
    logger.info(f"{'='*60}")

    # Step 1 — Use case submission for Anthropic models
    if result["provider"] == "anthropic":
        logger.info("  [Step 1] Anthropic model — checking use case form...")
        use_case_ok = ensure_use_case_submitted(bedrock_client, region, profile)
        if not use_case_ok:
            logger.error("  Use case submission failed. Cannot proceed with Claude models.")
            result["status"] = "USE_CASE_FAILED"
            return result
        logger.info("  [Step 1] Use case OK. Proceeding to invoke.")
    else:
        logger.info("  [Step 1] Non-Anthropic model — no use case needed.")

    # Step 2 — Invoke with test prompt (with retries)
    logger.info(f"  [Step 2] Invoking model with test prompt...")
    logger.info(f"  Prompt: \"{prompt[:80]}\"")

    for attempt in range(1, max_retries + 1):
        logger.info(f"  Attempt {attempt}/{max_retries}...")

        invoke_result = invoke_model_converse(runtime_client, model_id, prompt)

        if invoke_result["success"]:
            logger.info(f"  SUCCESS — Model responded!")
            logger.info(f"  Response: {invoke_result['response_text'][:150]}")
            logger.info(f"  Tokens:   {invoke_result['input_tokens']} in / {invoke_result['output_tokens']} out")
            result["status"] = "ENABLED"
            result["response_preview"] = invoke_result["response_text"][:100]
            return result

        # Handle specific errors
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
                logger.error(f"    - aws-marketplace:Subscribe permission missing")
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
        description="Enable Bedrock foundation models by invoking them (replicates console workflow)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s nova2-lite nova2-sonic
  %(prog)s claude-sonnet-4.6 claude-haiku-3.5
  %(prog)s mistral-large mixtral-8x7b command-r-plus
  %(prog)s amazon.nova-2-lite-v1:0 anthropic.claude-sonnet-4-6-v1:0
  %(prog)s --region us-west-2 --profile ops-role nova2-lite
  %(prog)s --list-aliases
""",
    )

    parser.add_argument(
        "models", nargs="*",
        help="Model IDs or aliases to enable",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument(
        "--prompt", default="Reply with exactly: Hello, model enabled successfully.",
        help="Test prompt to send to each model",
    )
    parser.add_argument("--retries", type=int, default=3, help="Max retries per model (default: 3)")
    parser.add_argument("--retry-delay", type=int, default=30, help="Seconds between retries (default: 30)")
    parser.add_argument("--list-aliases", action="store_true", help="Show all available shorthand aliases")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # List aliases
    if args.list_aliases:
        print(f"\n{'Alias':<25} {'Model ID':<60} {'Provider'}")
        print("-" * 100)
        for alias, mid in sorted(MODEL_ALIASES.items()):
            print(f"{alias:<25} {mid:<60} {detect_provider(mid)}")
        return

    if not args.models:
        parser.error("Provide model IDs or aliases. Use --list-aliases to see options.")

    # Resolve aliases
    resolved = []
    for m in args.models:
        rid = resolve_model_id(m)
        if rid != m:
            logger.info(f"Resolved '{m}' -> '{rid}'")
        resolved.append(rid)

    # Group by provider for display
    providers = set(detect_provider(m) for m in resolved)

    # Create clients
    session_kwargs = {"region_name": args.region}
    if args.profile:
        session_kwargs["profile_name"] = args.profile
    session = boto3.Session(**session_kwargs)
    bedrock_client = session.client("bedrock")
    runtime_client = session.client("bedrock-runtime")

    print(f"\n{'#'*60}")
    print(f"  Bedrock Foundation Model Enablement")
    print(f"  Region:    {args.region}")
    print(f"  Models:    {len(resolved)}")
    print(f"  Providers: {', '.join(sorted(providers))}")
    print(f"  Retries:   {args.retries} (delay: {args.retry_delay}s)")
    print(f"{'#'*60}")

    # Process each model
    results = []
    for model_id in resolved:
        result = enable_model(
            bedrock_client=bedrock_client,
            runtime_client=runtime_client,
            model_id=model_id,
            prompt=args.prompt,
            region=args.region,
            profile=args.profile,
            max_retries=args.retries,
            retry_delay=args.retry_delay,
        )
        results.append(result)

    # Summary
    print(f"\n{'#'*60}")
    print("  SUMMARY")
    print(f"{'#'*60}")
    print(f"  {'Model ID':<50} {'Provider':<12} {'Status'}")
    print(f"  {'-'*90}")

    success_count = 0
    for r in results:
        status_icon = "OK" if r["status"] == "ENABLED" else "FAIL"
        print(f"  {r['model_id']:<50} {r['provider']:<12} [{status_icon}] {r['status']}")
        if r["status"] == "ENABLED":
            success_count += 1

    print(f"\n  Enabled: {success_count}/{len(results)}")

    if success_count < len(results):
        print(f"\n  Troubleshooting failed models:")
        print(f"    1. Check IAM: bedrock:InvokeModel allowed for the model ARN?")
        print(f"    2. Check SCP: is the model blocked by Service Control Policy?")
        print(f"    3. Check region: is the model available in {args.region}?")
        print(f"    4. Check marketplace: aws-marketplace:Subscribe permission?")
        print(f"    5. For Claude: was the use case form accepted?")
        sys.exit(1)


if __name__ == "__main__":
    main()
