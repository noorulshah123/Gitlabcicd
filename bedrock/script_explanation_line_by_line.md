# Line-by-Line Explanation of Bedrock Model Enablement Scripts

This document explains every section of both Python scripts for someone completely new to programming.

---

# SCRIPT 1: enable_foundation_models.py

## The Top Section — What is this file?

```python
#!/usr/bin/env python3
```
This is called a "shebang" line. It tells your computer "run this file using Python 3." On Linux/Mac, this lets you run the script directly without typing `python` first.

```python
"""
Enable Amazon Bedrock Foundation Models...
"""
```
This is a "docstring" — a multi-line comment wrapped in triple quotes. It describes what the script does. Python ignores this text when running the code. It exists purely for humans reading the code.

---

## Imports — Loading External Tools

```python
import argparse
```
`argparse` is Python's built-in library for reading command-line arguments. When you type `python script.py nova2-lite --region us-west-2`, argparse is what parses `nova2-lite` and `--region us-west-2` into usable variables.

```python
import json
```
`json` lets Python convert between Python dictionaries (like `{"key": "value"}`) and JSON text strings. We need this because AWS APIs send and receive data in JSON format.

```python
import logging
```
`logging` is Python's built-in system for printing status messages. It is more professional than `print()` — it adds timestamps, severity levels (INFO, ERROR, WARNING), and can be configured to write to files.

```python
import sys
```
`sys` gives access to system-level functions. We use `sys.exit(1)` at the end to tell the operating system "this script finished with errors" (exit code 1 = failure, 0 = success).

```python
import time
```
`time` provides the `time.sleep(30)` function — it pauses the script for 30 seconds. We use this to wait between retries when AWS is still processing a subscription.

```python
import boto3
```
`boto3` is the official AWS SDK (Software Development Kit) for Python. It is how Python talks to AWS services. Every AWS API call in both scripts goes through boto3.

```python
from botocore.exceptions import ClientError
```
`ClientError` is the specific error type that boto3 throws when an AWS API call fails. For example, if you try to invoke a model you do not have access to, AWS returns an `AccessDeniedException`, which boto3 wraps in a `ClientError`. We catch these to handle errors gracefully.

---

## Logging Setup

```python
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
```

- `level=logging.INFO` — show INFO and above (INFO, WARNING, ERROR). DEBUG messages are hidden unless `--verbose` is used.
- `format=...` — each log line looks like: `2026-03-15 10:30:00 [INFO] Model responded!`
- `datefmt=...` — the date/time format (year-month-day hour:minute:second)
- `logger = logging.getLogger(__name__)` — creates a logger named after this file. We call `logger.info("message")` throughout the script.

---

## Model Alias Map

```python
MODEL_ALIASES = {
    "nova2-lite":           "amazon.nova-2-lite-v1:0",
    "nova2-sonic":          "amazon.nova-2-sonic-v1:0",
    ...
    "claude-sonnet-4.6":    "anthropic.claude-sonnet-4-6-v1:0",
    ...
    "mistral-large":        "mistral.mistral-large-2407-v1:0",
    ...
}
```

This is a Python dictionary — a lookup table. The left side (key) is a human-friendly shorthand. The right side (value) is the official AWS model ID.

Instead of typing `amazon.nova-2-lite-v1:0` every time, you can type `nova2-lite` and the script translates it for you.

---

## resolve_model_id function

```python
def resolve_model_id(alias_or_id: str) -> str:
    return MODEL_ALIASES.get(alias_or_id.lower(), alias_or_id)
```

- `def` — defines a function (a reusable block of code)
- `alias_or_id: str` — this function takes one input, which should be a string (text)
- `-> str` — the function returns a string
- `.lower()` — converts input to lowercase so "Nova2-Lite" matches "nova2-lite"
- `.get(key, default)` — looks up `key` in the dictionary. If found, returns the value. If not found, returns `default` (the original input, assuming it is already a full model ID)

Example: `resolve_model_id("nova2-lite")` returns `"amazon.nova-2-lite-v1:0"`.
Example: `resolve_model_id("amazon.nova-2-lite-v1:0")` returns `"amazon.nova-2-lite-v1:0"` (unchanged).

---

## detect_provider function

```python
def detect_provider(model_id: str) -> str:
    model_lower = model_id.lower()
    if "anthropic" in model_lower or "claude" in model_lower:
        return "anthropic"
    elif "amazon" in model_lower or "titan" in model_lower or "nova" in model_lower:
        return "amazon"
    ...
    return "unknown"
```

Looks at the model ID text and figures out which company made the model. This matters because Anthropic (Claude) models require an extra step (use case form). The function checks if specific words appear in the model ID string.

---

## ensure_use_case_submitted function

This is the function that handles the extra Claude requirement.

```python
def ensure_use_case_submitted(bedrock_client, region: str, profile: str = None):
```
Takes three inputs: the AWS Bedrock client, the region name, and optionally an AWS profile.

```python
    try:
        bedrock_client.get_use_case_for_model_access()
        logger.info("  Use case already submitted for this account.")
        return True
    except ClientError as e:
```

`try/except` is Python's error handling. It tries to call the AWS API `get_use_case_for_model_access`. If the call succeeds, a use case already exists — nothing to do. If the call fails (throws a ClientError), we catch the error and check what went wrong.

```python
        error_code = e.response["Error"]["Code"]
        if error_code not in ("ResourceNotFoundException", "ValidationException"):
            logger.warning(f"  Unexpected error checking use case: {e}")
            return False
```

If the error is `ResourceNotFoundException`, that means "no use case exists yet" — which is expected and we will submit one. Any other error is unexpected, so we log a warning and give up.

```python
    form_data = {
        "industry": "Technology",
        "useCase": "Internal AI-powered applications and data analysis",
        "targetEndUsers": "Internal employees and developers",
        "expectedUsage": "Development and production workloads",
        "country": "United States",
    }
```

This is the use case form data — the same information you would type into the console form. You can customize these values for your organization.

```python
    try:
        bedrock_client.put_use_case_for_model_access(formData=json.dumps(form_data))
```

`json.dumps(form_data)` converts the Python dictionary into a JSON text string (AWS APIs expect JSON). `put_use_case_for_model_access` submits the form to AWS.

The fallback logic that follows tries `us-east-1` if the current region fails, because the use case endpoint may be global.

---

## invoke_model_converse function

This is the core function — it sends a prompt to a model and gets a response.

```python
def invoke_model_converse(runtime_client, model_id: str, prompt: str) -> dict:
```

Takes three inputs: the Bedrock Runtime client (different from the control-plane client), the model ID, and the prompt text. Returns a dictionary with the result.

```python
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
```

- `runtime_client.converse(...)` — calls the AWS Converse API. This is the unified API that works the same way regardless of which model provider (Claude, Nova, Mistral, etc.) you are using.
- `modelId` — which model to talk to
- `messages` — the conversation, formatted as a list of messages. Each message has a `role` (user or assistant) and `content` (list of content blocks). We send one user message.
- `inferenceConfig`:
  - `maxTokens: 100` — limit the response to 100 tokens (roughly 75 words). We do not need a long response; we just want to confirm the model works.
  - `temperature: 0.1` — controls randomness. 0.1 means "be very predictable." Range is 0.0 (deterministic) to 1.0 (very creative).

```python
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        response_text = ""
        for block in content_blocks:
            if "text" in block:
                response_text += block["text"]
```

The Converse API returns a nested structure. We dig into `response["output"]["message"]["content"]` to find the text blocks. The response can contain multiple blocks (text, tool use, etc.), so we loop through and collect only the text.

```python
        usage = response.get("usage", {})
        return {
            "success": True,
            "response_text": response_text[:200],
            "input_tokens": usage.get("inputTokens", 0),
            "output_tokens": usage.get("outputTokens", 0),
        }
```

We return a dictionary with the success flag, a truncated response (first 200 characters), and token counts. Tokens are the billing unit — each token is roughly 0.75 words.

```python
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        error_msg = e.response["Error"].get("Message", "")
        return {
            "success": False,
            "error_code": error_code,
            "error_message": error_msg,
        }
```

If the API call fails, we catch the error and return it in a structured format instead of crashing.

---

## enable_model function

This is the main workflow function that orchestrates everything for one model.

```python
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
```

Takes many inputs: both AWS clients, the model ID, the test prompt, region, profile, and retry configuration. `max_retries=3` and `retry_delay=30` are default values — used if the caller does not specify them.

```python
    if result["provider"] == "anthropic":
        logger.info("  [Step 1] Anthropic model — checking use case form...")
        use_case_ok = ensure_use_case_submitted(bedrock_client, region, profile)
```

If the model is from Anthropic (Claude), run the use case submission step first.

```python
    for attempt in range(1, max_retries + 1):
        logger.info(f"  Attempt {attempt}/{max_retries}...")
        invoke_result = invoke_model_converse(runtime_client, model_id, prompt)
```

`for attempt in range(1, 4)` loops 3 times (attempt = 1, 2, 3). Each iteration tries invoking the model.

```python
        if invoke_result["success"]:
            ...
            result["status"] = "ENABLED"
            return result
```

If the invocation succeeds, the model is enabled. We are done.

```python
        if error_code == "AccessDeniedException":
            if attempt < max_retries:
                logger.info(f"  Access denied (subscription likely in progress). "
                           f"Waiting {retry_delay}s before retry...")
                time.sleep(retry_delay)
                continue
```

If we get `AccessDeniedException`, the subscription may still be processing (takes up to 15 minutes). We wait 30 seconds and try again. `continue` jumps back to the top of the `for` loop.

The other error handlers (`ResourceNotFoundException`, `ModelNotReadyException`, `ThrottlingException`) follow the same pattern — either retry or give up depending on the error type.

---

## main function — CLI entry point

```python
def main():
    parser = argparse.ArgumentParser(...)
```

Creates the command-line argument parser. This is what makes `--region`, `--profile`, `--retries`, etc. work.

```python
    parser.add_argument("models", nargs="*", help="Model IDs or aliases to enable")
```

`nargs="*"` means "accept zero or more positional arguments." These are the model names/IDs you type after the script name.

```python
    parser.add_argument("--region", default="us-east-1", help="AWS region")
```

`--region` is an optional named argument. If not provided, defaults to `us-east-1`.

```python
    session = boto3.Session(**session_kwargs)
    bedrock_client = session.client("bedrock")
    runtime_client = session.client("bedrock-runtime")
```

Creates two AWS clients:
- `bedrock` — the control-plane client (for use case submission, listing models)
- `bedrock-runtime` — the data-plane client (for actually invoking models)

These are different AWS service endpoints. You need both.

```python
    results = []
    for model_id in resolved:
        result = enable_model(...)
        results.append(result)
```

Loops through every model the user specified and enables each one. Results are collected in a list.

```python
if __name__ == "__main__":
    main()
```

This is a Python convention. It means "if this file is run directly (not imported), call the main() function." This lets other scripts import functions from this file without automatically running the whole thing.


---
---


# SCRIPT 2: enable_embedding_models.py

The structure is very similar to Script 1, so this section focuses on the differences.

## Why a Separate Script?

Embedding models cannot use the Converse API. They use `invoke_model` directly, and each provider has a different request body format. The Converse API only works for text generation models.

---

## Embedding-Specific Alias Map

```python
EMBEDDING_ALIASES = {
    "titan-embed-v2":       "amazon.titan-embed-text-v2:0",
    "cohere-embed-en":      "cohere.embed-english-v3",
    "cohere-embed-multi":   "cohere.embed-multilingual-v3",
    ...
}
```

Same concept as Script 1, but for embedding models only.

---

## EMBEDDING_INFO Dictionary

```python
EMBEDDING_INFO = {
    "amazon.titan-embed-text-v2:0": {"dims": 1024, "max_tokens": 8192, "notes": "Configurable: 256, 512, 1024"},
    ...
}
```

Reference data about each embedding model. `dims` is the number of dimensions in the output vector. This matters when configuring knowledge bases or vector databases — the dimensions must match.

---

## Provider-Specific Invoke Functions

This is the biggest difference from Script 1. Each embedding provider expects a different request body format.

### Titan Embed V2

```python
def invoke_titan_embed_v2(runtime_client, model_id: str, text: str) -> dict:
    body = json.dumps({
        "inputText": text,
        "dimensions": 1024,
        "normalize": True,
    })
```

- `inputText` — the text to convert into a vector
- `dimensions` — Titan V2 lets you choose: 256, 512, or 1024
- `normalize` — if True, the output vector is normalized (all values adjusted so the vector has length 1.0). This is standard for similarity search.

```python
    response = runtime_client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=body,
    )
    result = json.loads(response["body"].read())
    embedding = result.get("embedding", [])
```

Unlike the Converse API, `invoke_model` returns raw bytes. We read the response body and parse the JSON. The `embedding` field contains the vector — a list of 1024 floating-point numbers like `[0.0234, -0.1456, 0.0891, ...]`.

### Cohere Embed

```python
def invoke_cohere_embed(runtime_client, model_id: str, text: str) -> dict:
    body = json.dumps({
        "texts": [text],
        "input_type": "search_document",
    })
```

Cohere's format is different:
- `texts` — a list of texts (Cohere can embed multiple texts in one call)
- `input_type` — tells Cohere how the text will be used. `"search_document"` means "this is a document being indexed for search." The alternative is `"search_query"` for the search query itself. This affects how the embedding is generated.

```python
    embeddings = result.get("embeddings", [[]])
    embedding = embeddings[0] if embeddings else []
```

Cohere returns a list of lists (one embedding per input text). Since we sent one text, we take `embeddings[0]`.

---

## invoke_embedding_model — Router Function

```python
def invoke_embedding_model(runtime_client, model_id: str, text: str) -> dict:
    model_lower = model_id.lower()

    if "titan-embed-text-v2" in model_lower:
        return invoke_titan_embed_v2(runtime_client, model_id, text)
    elif "titan-embed" in model_lower:
        return invoke_titan_embed(runtime_client, model_id, text)
    elif "cohere.embed" in model_lower:
        return invoke_cohere_embed(runtime_client, model_id, text)
    ...
```

This function looks at the model ID and routes to the correct provider-specific function. This is necessary because there is no unified embedding API — each provider uses a different request/response format.

---

## enable_model — Same Pattern, Different Output

The retry logic and error handling are identical to Script 1. The only difference is in what "success" looks like:

```python
if invoke_result["success"]:
    dims = invoke_result["dimensions"]
    sample = invoke_result["sample_values"]
    logger.info(f"  Dimensions: {dims}")
    logger.info(f"  Sample:     {[round(v, 6) for v in sample[:3]]}...")
```

Instead of showing a text response, we show:
- How many dimensions the embedding has (e.g., 1024)
- A sample of the first 3 values from the vector

This confirms the model is working and the output format is correct.

---

## The --show-dimensions Flag

```python
if args.show_dimensions:
    for mid, info in sorted(EMBEDDING_INFO.items()):
        print(f"{mid:<40} {info['dims']:<8} {info['max_tokens']:<12} {info['notes']}")
    return
```

A utility feature that prints a reference table of embedding dimensions. Useful when configuring knowledge bases, because the knowledge base vector index dimensions must match the embedding model dimensions.

---

## Summary: How Both Scripts Work

### Script 1 Flow (Foundation Models)
```
User runs: python enable_foundation_models.py nova2-lite claude-sonnet-4.6 mistral-large

For each model:
  1. Resolve alias -> full model ID
  2. Detect provider (amazon, anthropic, mistral, etc.)
  3. If Anthropic -> submit use case form (one-time)
  4. Call Converse API with test prompt
  5. If AccessDenied -> wait 30s -> retry (up to 3 times)
  6. If success -> model is enabled
  7. Print summary
```

### Script 2 Flow (Embedding Models)
```
User runs: python enable_embedding_models.py titan-embed-v2 cohere-embed-en

For each model:
  1. Resolve alias -> full model ID
  2. Detect provider (amazon, cohere)
  3. Route to correct invoke function (Titan format vs Cohere format)
  4. Call invoke_model API with test text
  5. If AccessDenied -> wait 30s -> retry (up to 3 times)
  6. If success -> print dimensions and sample values
  7. Print summary with Terraform reminder
```
