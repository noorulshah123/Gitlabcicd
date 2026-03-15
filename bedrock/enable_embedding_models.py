#!/usr/bin/env python3
"""
Enable Amazon Bedrock Embedding Models

This script programmatically enables embedding model access in Amazon Bedrock.
Embedding models convert text into numerical vectors used for:
  - Semantic search / RAG (Retrieval Augmented Generation)
  - Document similarity matching
  - Knowledge base indexing

It handles:
  1. Agreement creation (required for 3rd-party/marketplace models)
  2. Access status verification
  3. Batch enablement of multiple embedding models

Prerequisites:
  - AWS credentials configured (CLI profile, env vars, or IAM role)
  - IAM permissions required:
      * bedrock:ListFoundationModels
      * bedrock:ListFoundationModelAgreementOffers
      * bedrock:CreateFoundationModelAgreement
      * bedrock:GetFoundationModelAvailability
      * aws-marketplace:Subscribe
      * aws-marketplace:ViewSubscriptions
  - boto3 >= 1.35.0

Usage:
  # Enable specific embedding models by model ID
  python enable_embedding_models.py amazon.titan-embed-text-v2:0 cohere.embed-english-v3

  # Enable using shorthand aliases
  python enable_embedding_models.py titan-embed-v2 cohere-embed-en cohere-embed-multi

  # Specify region and AWS profile
  python enable_embedding_models.py --region us-east-1 --profile my-profile titan-embed-v2

  # Dry run - check status without making changes
  python enable_embedding_models.py --dry-run titan-embed-v2 cohere-embed-en

  # List all available embedding models in the region
  python enable_embedding_models.py --list

  # Enable ALL available embedding models in the region
  python enable_embedding_models.py --enable-all

  # Enable all embedding models from a specific provider
  python enable_embedding_models.py --enable-all --provider amazon
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
# Embedding model alias map
# Update this map as new embedding models are released
# ---------------------------------------------------------------------------
EMBEDDING_ALIASES = {
    # Amazon Titan Embeddings
    "titan-embed-v2":       "amazon.titan-embed-text-v2:0",
    "titan-embed-v1":       "amazon.titan-embed-text-v1",
    "titan-embed-image":    "amazon.titan-embed-image-v1",
    "titan-multimodal-embed": "amazon.titan-embed-image-v1",
    # Cohere Embed
    "cohere-embed-en":      "cohere.embed-english-v3",
    "cohere-embed-multi":   "cohere.embed-multilingual-v3",
    # Amazon Nova Embed (if available)
    "nova-embed":           "amazon.nova-embed-v1:0",
}


def resolve_model_id(alias_or_id: str) -> str:
    """Resolve a shorthand alias to a full Bedrock model ID, or pass through as-is."""
    return EMBEDDING_ALIASES.get(alias_or_id.lower(), alias_or_id)


def get_bedrock_client(region: str, profile: str = None):
    """Create a Bedrock control-plane client."""
    session_kwargs = {"region_name": region}
    if profile:
        session_kwargs["profile_name"] = profile
    session = boto3.Session(**session_kwargs)
    return session.client("bedrock")


# ---------------------------------------------------------------------------
# List embedding models
# ---------------------------------------------------------------------------
def list_embedding_models(client, provider_filter: str = None) -> list:
    """List all embedding models available in the region."""
    kwargs = {}
    if provider_filter:
        kwargs["byProvider"] = provider_filter

    try:
        response = client.list_foundation_models(
            byOutputModality="EMBEDDING", **kwargs
        )
        models = response.get("modelSummaries", [])

        print(f"\n{'Model ID':<55} {'Provider':<20} {'Name':<40} {'Input Modalities'}")
        print("-" * 140)
        for m in sorted(models, key=lambda x: x["modelId"]):
            input_mods = ", ".join(m.get("inputModalities", []))
            print(
                f"{m['modelId']:<55} "
                f"{m.get('providerName', 'N/A'):<20} "
                f"{m.get('modelName', 'N/A'):<40} "
                f"{input_mods}"
            )

        print(f"\nTotal embedding models: {len(models)}")
        return models

    except ClientError as e:
        logger.error(f"Failed to list models: {e}")
        return []


# ---------------------------------------------------------------------------
# Model agreement creation
# ---------------------------------------------------------------------------
def create_model_agreement(client, model_id: str) -> bool:
    """
    Create a foundation model agreement (accept EULA/terms).
    Amazon-owned models typically don't require agreements.
    """
    try:
        response = client.list_foundation_model_agreement_offers(modelId=model_id)
        offers = response.get("offers", [])

        if not offers:
            logger.info(f"  No agreement required for {model_id}.")
            return True

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
    """Check the current access/availability status of an embedding model."""
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
# Embedding dimension info (helpful for KB configuration)
# ---------------------------------------------------------------------------
EMBEDDING_DIMENSIONS = {
    "amazon.titan-embed-text-v2:0":     {"dimensions": 1024, "max_tokens": 8192, "notes": "Configurable: 256, 512, 1024"},
    "amazon.titan-embed-text-v1":       {"dimensions": 1536, "max_tokens": 8192, "notes": "Fixed dimensions"},
    "amazon.titan-embed-image-v1":      {"dimensions": 1024, "max_tokens": 128,  "notes": "Text + image multimodal"},
    "cohere.embed-english-v3":          {"dimensions": 1024, "max_tokens": 512,  "notes": "English optimized"},
    "cohere.embed-multilingual-v3":     {"dimensions": 1024, "max_tokens": 512,  "notes": "100+ languages"},
    "amazon.nova-embed-v1:0":           {"dimensions": 1024, "max_tokens": 8192, "notes": "Nova embedding model"},
}


def show_embedding_info(model_id: str):
    """Display embedding-specific configuration info for a model."""
    info = EMBEDDING_DIMENSIONS.get(model_id)
    if info:
        logger.info(f"  Embedding info:")
        logger.info(f"    Dimensions: {info['dimensions']}")
        logger.info(f"    Max tokens: {info['max_tokens']}")
        logger.info(f"    Notes:      {info['notes']}")


# ---------------------------------------------------------------------------
# Main enable workflow
# ---------------------------------------------------------------------------
def enable_model(client, model_id: str, dry_run: bool = False) -> dict:
    """
    Full workflow to enable a single embedding model:
      1. Check current status
      2. Create agreement if needed
      3. Verify final status
    """
    result = {"model_id": model_id, "status": "UNKNOWN", "action_taken": "none"}

    logger.info(f"\nProcessing: {model_id}")
    logger.info("-" * 60)

    # Show embedding-specific info
    show_embedding_info(model_id)

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
    time.sleep(2)
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
        description="Enable Bedrock embedding models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s amazon.titan-embed-text-v2:0 cohere.embed-english-v3
  %(prog)s titan-embed-v2 cohere-embed-en cohere-embed-multi
  %(prog)s --region us-west-2 --profile ops-role titan-embed-v2
  %(prog)s --dry-run titan-embed-v2 cohere-embed-en
  %(prog)s --list
  %(prog)s --enable-all
  %(prog)s --enable-all --provider amazon

Available aliases:
""" + "\n".join(f"  {alias:<25} -> {mid}" for alias, mid in sorted(EMBEDDING_ALIASES.items())),
    )

    parser.add_argument(
        "models",
        nargs="*",
        help="Embedding model IDs or aliases to enable",
    )
    parser.add_argument("--region", default="us-east-1", help="AWS region (default: us-east-1)")
    parser.add_argument("--profile", default=None, help="AWS CLI profile name")
    parser.add_argument("--dry-run", action="store_true", help="Check status without making changes")
    parser.add_argument("--list", action="store_true", help="List available embedding models")
    parser.add_argument("--enable-all", action="store_true", help="Enable ALL embedding models in region")
    parser.add_argument("--provider", default=None, help="Filter by provider (e.g., amazon, cohere)")
    parser.add_argument("--show-dimensions", action="store_true", help="Show embedding dimension reference table")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Show dimension reference
    if args.show_dimensions:
        print(f"\n{'Model ID':<45} {'Dimensions':<12} {'Max Tokens':<12} {'Notes'}")
        print("-" * 110)
        for mid, info in sorted(EMBEDDING_DIMENSIONS.items()):
            print(f"{mid:<45} {info['dimensions']:<12} {info['max_tokens']:<12} {info['notes']}")
        return

    # Create client
    client = get_bedrock_client(args.region, args.profile)

    # List mode
    if args.list:
        list_embedding_models(client, args.provider)
        return

    # Enable-all mode
    if args.enable_all:
        logger.info("Fetching all available embedding models...")
        response = client.list_foundation_models(byOutputModality="EMBEDDING")
        all_models = response.get("modelSummaries", [])

        if args.provider:
            all_models = [
                m for m in all_models
                if m.get("providerName", "").lower() == args.provider.lower()
            ]

        if not all_models:
            logger.warning("No embedding models found matching criteria.")
            return

        resolved_models = [m["modelId"] for m in all_models]
        logger.info(f"Found {len(resolved_models)} embedding models to process.")
    else:
        # Validate models provided
        if not args.models:
            parser.error("Provide model IDs/aliases, use --list, --enable-all, or --show-dimensions.")

        # Resolve aliases
        resolved_models = []
        for m in args.models:
            resolved = resolve_model_id(m)
            if resolved != m:
                logger.info(f"Resolved alias '{m}' -> '{resolved}'")
            resolved_models.append(resolved)

    print(f"\n{'='*60}")
    print(f"Bedrock Embedding Model Enablement")
    print(f"Region:  {args.region}")
    print(f"Models:  {len(resolved_models)}")
    print(f"Dry Run: {args.dry_run}")
    print(f"{'='*60}")

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

    # Embedding-specific reminder
    print(f"\n{'='*60}")
    print("REMINDER: After enabling embedding models, update your")
    print("Terraform module's allowed_foundation_model_ids if needed.")
    print("For Knowledge Base configs, ensure the embedding_model_name")
    print("field in knowledge_base_configurations matches the model ID.")
    print(f"{'='*60}")

    # Exit code
    failures = [r for r in results if r["status"] in ("NOT_AVAILABLE_IN_REGION", "ERROR")]
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
