#!/usr/bin/env python3
"""
Enable Amazon Bedrock Foundation Models (Text Generation / Multimodal)

This script programmatically enables foundation model access for text generation
and multimodal models in Amazon Bedrock. It handles:
  1. One-time use case submission (required for Anthropic models)
  2. Agreement creation (required for 3rd-party/marketplace models)
  3. Access status verification

Prerequisites:
  - AWS credentials configured (CLI profile, env vars, or IAM role)
  - IAM permissions required:
      * bedrock:ListFoundationModels
      * bedrock:ListFoundationModelAgreementOffers
      * bedrock:CreateFoundationModelAgreement
      * bedrock:GetFoundationModelAvailability
      * bedrock:PutUseCaseForModelAccess
      * bedrock:GetUseCaseForModelAccess
      * aws-marketplace:Subscribe
      * aws-marketplace:ViewSubscriptions
  - boto3 >= 1.35.0

Usage:
  # Enable specific models by model ID
  python enable_foundation_models.py amazon.nova-2-lite-v1:0 amazon.nova-2-sonic-v1:0

  # Enable using shorthand aliases
  python enable_foundation_models.py nova2-lite nova2-sonic claude-sonnet-4.6

  # Specify region and AWS profile
  python enable_foundation_models.py --region us-east-1 --profile my-profile nova2-lite

  # Dry run - check status without making changes
  python enable_foundation_models.py --dry-run nova2-lite claude-sonnet-4.6

  # List all available foundation models in the region
  python enable_foundation_models.py --list

  # List models filtered by provider
  python enable_foundation_models.py --list --provider anthropic
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime

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
# Model alias map — shorthand names to official Bedrock model IDs
# Update this map as new models are released
# ---------------------------------------------------------------------------
MODEL_ALIASES = {
    # Amazon Nova 2 family
    "nova2-lite":       "amazon.nova-2-lite-v1:0",
    "nova2-sonic":      "amazon.nova-2-sonic-v1:0",
    "nova2-premier":    "us.amazon.nova-2-premier-v1:0",
    # Amazon Nova 1 family
    "nova-pro":         "amazon.nova-pro-v1:0",
    "nova-lite":        "amazon.nova-lite-v1:0",
    "nova-micro":       "amazon.nova-micro-v1:0",
    "nova-premier":     "us.amazon.nova-premier-v1:0",
    # Anthropic Claude
    "claude-sonnet-4.6":"anthropic.claude-sonnet-4-6-v1:0",
    "claude-opus-4.6":  "anthropic.claude-opus-4-6-v1:0",
    "claude-sonnet-4.5":"us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "claude-opus-4":    "us.anthropic.claude-opus-4-1-20250805-v1:0",
    "claude-sonnet-4":  "anthropic.claude-sonnet-4-20250514-v1:0",
    "claude-sonnet-3.5":"anthropic.claude-3-5-sonnet-20241022-v2:0",
    "claude-haiku-3.5":  "anthropic.claude-3-5-haiku-20241022-v1:0",
    # Meta Llama
    "llama3.3-70b":     "us.meta.llama3-3-70b-instruct-v1:0",
    "llama3.1-405b":    "meta.llama3-1-405b-instruct-v1:0",
    "llama3.1-70b":     "meta.llama3-1-70b-instruct-v1:0",
    # Mistral
    "mistral-large":    "mistral.mistral-large-2407-v1:0",
    "mixtral-8x7b":     "mistral.mixtral-8x7b-instruct-v0:1",
    # Cohere
    "command-r-plus":   "cohere.command-r-plus-v1:0",
    "command-r":        "cohere.command-r-v1:0",
    # AI21
    "jamba-1.5-large":  "ai21.jamba-1-5-large-v1:0",
    "jamba-1.5-mini":   "ai21.jamba-1-5-mini-v1:0",
}


def resolve_model_id(alias_or_id: str) -> str:
    """Resolve a shorthand alias to a full Bedrock model ID, or pass through as-is."""
    return MODEL_ALIASES.get(alias_or_id.lower(), alias_or_id)


def get_bedrock_client(region: str, profile: str = None):
    """Create a Bedrock control-plane client."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)
    return session.client("bedrock")


# ---------------------------------------------------------------------------
# Use case submission (one-time, required for Anthropic models)
# ---------------------------------------------------------------------------
def ensure_use_case_submitted(client, region: str, profile: str = None):
    """
    Check if a use case form has been submitted for this account.
    If not, submit a generic one. Required for Anthropic models.
    """
    try:
        client.get_use_case_for_model_access()
        logger.info("Use case already submitted for this account.")
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code in ("ResourceNotFoundException", "ValidationException"):
            logger.info("No use case found. Submitting use case form...")
        else:
            logger.warning(f"Unexpected error checking use case: {e}")
            return False

    # Submit use case form
    form_data = {
        "industry": "Technology",
        "useCase": "Internal AI-powered applications and data analysis",
        "targetEndUsers": "Internal employees and developers",
        "expectedUsage": "Development and production workloads",
        "country": "United States",
    }

    try:
        client.put_use_case_for_model_access(formData=json.dumps(form_data))
        logger.info("Use case submitted successfully.")
        return True
    except ClientError as e:
        # If current region fails, try us-east-1 (use case may be global)
        if region != "us-east-1":
            logger.info(f"Use case submission failed in {region}, trying us-east-1...")
            try:
                fallback_client = get_bedrock_client("us-east-1", profile)
                fallback_client.put_use_case_for_model_access(
                    formData=json.dumps(form_data)
                )
                logger.info("Use case submitted successfully in us-east-1.")
                return True
            except ClientError as e2:
                logger.error(f"Use case submission failed in both regions: {e2}")
                return False
        else:
            logger.error(f"Use case submission failed: {e}")
            return False


# ---------------------------------------------------------------------------
# Model agreement creation
# ---------------------------------------------------------------------------
def create_model_agreement(client, model_id: str) -> bool:
    """
    Create a foundation model agreement (accept EULA/terms).
    Some models (Amazon's own) don't require agreements — this handles that.
    """
    try:
        response = client.list_foundation_model_agreement_offers(modelId=model_id)
        offers = response.get("offers", [])

        if not offers:
            logger.info(f"  No agreement required for {model_id} (likely Amazon-owned model).")
            return True

        # Use the first available offer
        offer = offers[0]
        offer_token = offer.get("offerToken")
        offer_id = offer.get("offerId")

        if not offer_token:
            logger.error(f"  No offer token found for {model_id}.")
            return False

        logger.info(f"  Found offer: {offer_id}. Creating agreement...")
        client.create_foundation_model_agreement(
            offerToken=offer_token, modelId=model_id
        )
        logger.info(f"  Agreement created for {model_id}.")
        return True

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"].get("Message", "")

        if "already" in error_msg.lower() or "conflict" in error_code.lower():
            logger.info(f"  Agreement already exists for {model_id}.")
            return True
        elif "not supported" in error_msg.lower():
            logger.info(f"  Agreement not supported for {model_id} (no EULA needed).")
            return True
        elif error_code == "ResourceNotFoundException":
            logger.error(f"  Model {model_id} not found in this region.")
            return False
        else:
            logger.error(f"  Failed to create agreement for {model_id}: {e}")
            return False


# ---------------------------------------------------------------------------
# Access status check
# ---------------------------------------------------------------------------
def check_model_availability(client, model_id: str) -> dict:
    """Check the current access/availability status of a model."""
    try:
        response = client.get_foundation_model_availability(modelId=model_id)
        return {
            "model_id": response.get("modelId", model_id),
            "agreement_status": response.get("agreementAvailability", {}).get("status", "UNKNOWN"),
            "authorization_status": response.get("authorizationStatus", "UNKNOWN"),
            "entitlement_status": response.get("entitlementAvailability", "UNKNOWN"),
            "region_status": response.get("regionAvailability", "UNKNOWN"),
        }
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "ResourceNotFoundException":
            return {
                "model_id": model_id,
                "agreement_status": "NOT_FOUND",
                "authorization_status": "NOT_FOUND",
                "entitlement_status": "NOT_FOUND",
                "region_status": "NOT_AVAILABLE_IN_REGION",
            }
        else:
            logger.warning(f"  Could not check availability for {model_id}: {e}")
            return {
                "model_id": model_id,
                "agreement_status": "ERROR",
                "authorization_status": "ERROR",
                "entitlement_status": "ERROR",
                "region_status": "ERROR",
            }


# ---------------------------------------------------------------------------
# List available models
# ---------------------------------------------------------------------------
def list_available_models(client, provider_filter: str = None):
    """List all foundation models available in the region."""
    kwargs = {}
    if provider_filter:
        kwargs["byProvider"] = provider_filter

    try:
        response = client.list_foundation_models(**kwargs)
        models = response.get("modelSummaries", [])

        # Filter to text/multimodal output (exclude pure embedding models)
        text_models = [
            m for m in models
            if "TEXT" in m.get("outputModalities", [])
        ]

        print(f"\n{'Model ID':<60} {'Provider':<20} {'Name'}")
        print("-" * 120)
        for m in sorted(text_models, key=lambda x: x["modelId"]):
            print(f"{m['modelId']:<60} {m.get('providerName', 'N/A'):<20} {m.get('modelName', 'N/A')}")

        print(f"\nTotal text/multimodal models: {len(text_models)}")
        return text_models

    except ClientError as e:
        logger.error(f"Failed to list models: {e}")
        return []


# ---------------------------------------------------------------------------
# Main enable workflow
# ---------------------------------------------------------------------------
def enable_model(client, model_id: str, dry_run: bool = False) -> dict:
    """
    Full workflow to enable a single foundation model:
      1. Check current status
      2. Create agreement if needed
      3. Verify final status
    """
    result = {"model_id": model_id, "status": "UNKNOWN", "action_taken": "none"}

    logger.info(f"\nProcessing: {model_id}")
    logger.info("-" * 60)

    # Step 1 — Check current status
    status = check_model_availability(client, model_id)
    logger.info(f"  Current status:")
    logger.info(f"    Agreement:     {status['agreement_status']}")
    logger.info(f"    Authorization: {status['authorization_status']}")
    logger.info(f"    Entitlement:   {status['entitlement_status']}")
    logger.info(f"    Region:        {status['region_status']}")

    if status["region_status"] == "NOT_AVAILABLE_IN_REGION":
        logger.warning(f"  Model {model_id} is not available in this region. Skipping.")
        result["status"] = "NOT_AVAILABLE_IN_REGION"
        return result

    if status["authorization_status"] == "AUTHORIZED" and status["agreement_status"] == "AVAILABLE":
        logger.info(f"  Model {model_id} is already fully enabled.")
        result["status"] = "ALREADY_ENABLED"
        result["action_taken"] = "none"
        return result

    if dry_run:
        logger.info(f"  [DRY RUN] Would attempt to create agreement for {model_id}.")
        result["status"] = "DRY_RUN"
        result["action_taken"] = "would_create_agreement"
        return result

    # Step 2 — Create agreement
    agreement_ok = create_model_agreement(client, model_id)
    result["action_taken"] = "agreement_created" if agreement_ok else "agreement_failed"

    # Step 3 — Verify
    time.sleep(2)  # Brief wait for propagation
    final_status = check_model_availability(client, model_id)
    logger.info(f"  Final status:")
    logger.info(f"    Agreement:     {final_status['agreement_status']}")
    logger.info(f"    Authorization: {final_status['authorization_status']}")
    logger.info(f"    Entitlement:   {final_status['entitlement_status']}")

    if final_status["authorization_status"] == "AUTHORIZED":
        result["status"] = "ENABLED"
    else:
        result["status"] = "PENDING"
        logger.info(f"  Note: Model may take up to 15 minutes to fully activate.")

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Enable Bedrock foundation models (text generation / multimodal)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s amazon.nova-2-lite-v1:0 amazon.nova-2-sonic-v1:0
  %(prog)s nova2-lite nova2-sonic claude-sonnet-4.6
  %(prog)s --region us-west-2 --profile ops-role nova2-lite
  %(prog)s --dry-run nova2-lite claude-sonnet-4.6
  %(prog)s --list
  %(prog)s --list --provider anthropic

Available aliases:
""" + "\n".join(f"  {alias:<25} -> {mid}" for alias, mid in sorted(MODEL_ALIASES.items())),
    )

    parser.add_argument(
        "models",
        nargs="*",
        help="Model IDs or aliases to enable (e.g., nova2-lite, anthropic.claude-sonnet-4-6-v1:0)",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument("--dry-run", action="store_true", help="Check status without making changes")
    parser.add_argument("--list", action="store_true", help="List available foundation models")
    parser.add_argument("--provider", default=None, help="Filter --list by provider (e.g., anthropic, amazon, meta)")
    parser.add_argument("--skip-use-case", action="store_true", help="Skip use case submission step")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Create client
    client = get_bedrock_client(args.region, args.profile)

    # List mode
    if args.list:
        list_available_models(client, args.provider)
        return

    # Validate models provided
    if not args.models:
        parser.error("Provide model IDs/aliases, or use --list to see available models.")

    # Resolve aliases
    resolved_models = []
    for m in args.models:
        resolved = resolve_model_id(m)
        if resolved != m:
            logger.info(f"Resolved alias '{m}' -> '{resolved}'")
        resolved_models.append(resolved)

    print(f"\n{'='*60}")
    print(f"Bedrock Foundation Model Enablement")
    print(f"Region:  {args.region}")
    print(f"Models:  {len(resolved_models)}")
    print(f"Dry Run: {args.dry_run}")
    print(f"{'='*60}")

    # Submit use case (one-time for Anthropic models)
    if not args.skip_use_case and not args.dry_run:
        has_anthropic = any("anthropic" in m.lower() for m in resolved_models)
        if has_anthropic:
            logger.info("\nAnthropic model detected — checking use case submission...")
            ensure_use_case_submitted(client, args.region, args.profile)

    # Process each model
    results = []
    for model_id in resolved_models:
        result = enable_model(client, model_id, args.dry_run)
        results.append(result)

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"{'Model ID':<55} {'Status':<20} {'Action'}")
    print("-" * 100)
    for r in results:
        print(f"{r['model_id']:<55} {r['status']:<20} {r['action_taken']}")

    # Exit code
    failures = [r for r in results if r["status"] in ("NOT_AVAILABLE_IN_REGION", "ERROR")]
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
