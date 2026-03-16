# COMPLETE LINE-BY-LINE CODE EXPLANATION
# For Absolute Beginners — No Programming Knowledge Assumed

This document explains EVERY SINGLE LINE of both Python scripts.
It covers what each line does, why it exists, and how the whole workflow connects.

================================================================================
BEFORE WE START — KEY CONCEPTS YOU NEED TO KNOW
================================================================================

WHAT IS A VARIABLE?
  A named container that holds a value.
  Example: region = "ap-southeast-2"
  The name is "region". The value is "ap-southeast-2".
  You can change the value later: region = "us-east-1"

WHAT IS A FUNCTION?
  A reusable block of code with a name.
  You "define" it once, then "call" it many times.
  Like a recipe — written once, used whenever you cook.
  Example:
    def add(a, b):       ← definition (the recipe)
        return a + b
    result = add(3, 5)   ← call (cooking the recipe) → result is 8

WHAT IS A DICTIONARY?
  A lookup table. You give it a "key", it gives back a "value".
  Like a phone book: look up a name (key), get a number (value).
  Example:
    phonebook = {"Alice": "555-1234", "Bob": "555-5678"}
    phonebook["Alice"]  → "555-1234"

WHAT IS A LIST?
  An ordered collection of items.
  Example: fruits = ["apple", "banana", "cherry"]
  fruits[0] is "apple", fruits[1] is "banana"

WHAT IS A BOOLEAN?
  A value that is either True or False. Nothing else.
  Used for yes/no decisions.

WHAT DOES "return" DO?
  Sends a value back from a function to whoever called it.
  Example:
    def double(x):
        return x * 2
    answer = double(5)   ← answer is now 10

WHAT IS try/except?
  Error handling. "Try this code. If it crashes, run the except code instead."
  Without it, one error kills the entire script.


================================================================================
================================================================================
SCRIPT 1: enable_foundation_models.py — LINE BY LINE
================================================================================
================================================================================


LINE 1:
  #!/usr/bin/env python3

  WHAT: The "shebang" line.
  WHY:  Tells the operating system "use Python 3 to run this file."
  WHEN: Only matters on Linux/Mac. Windows ignores it.
  WITHOUT IT: You must always type "python3 script.py" instead of "./script.py"


LINES 2-37:
  """
  Enable Amazon Bedrock Foundation Models...
  ...
  """

  WHAT: A docstring (documentation string). Everything between triple quotes.
  WHY:  Describes the script for humans. Python ignores it completely.
  CONTAINS: What the script does, prerequisites, and usage examples.
  WHEN USEFUL: When you or a colleague opens this file months later.


LINE 39:
  import argparse

  WHAT: Loads Python's built-in "argument parser" library.
  WHY:  We need to read command-line arguments.
  EXAMPLE: When you type "python script.py nova2-lite --region us-east-1"
           argparse is what understands:
             - "nova2-lite" is a model name
             - "--region" is a flag
             - "us-east-1" is the value for that flag
  WITHOUT IT: We'd have to manually parse sys.argv (much harder).


LINE 40:
  import json

  WHAT: Loads Python's built-in JSON library.
  WHY:  AWS APIs communicate in JSON format (a text format for structured data).
  WHAT IT DOES:
    - json.dumps({"key": "value"})  → converts Python dict to JSON text string
    - json.loads('{"key": "value"}') → converts JSON text string to Python dict
  EXAMPLE: When we send data to AWS, we convert our Python dictionary to a JSON
           string. When AWS sends data back, we convert the JSON string back.


LINE 41:
  import logging

  WHAT: Loads Python's built-in logging library.
  WHY:  Better than print() for status messages.
  DIFFERENCE FROM print():
    - print("hello")         → just outputs "hello"
    - logger.info("hello")   → outputs "2026-03-16 10:30:00 [INFO] hello"
    - Adds timestamp, severity level, can write to files


LINE 42:
  import sys

  WHAT: Loads Python's built-in system library.
  WHY:  We need sys.exit(1) at the end.
  WHAT sys.exit(1) DOES: Tells the operating system "this script had failures."
    - Exit code 0 = success (everything worked)
    - Exit code 1 = failure (something went wrong)
    - CI/CD pipelines use this to decide if the next step should run.


LINE 43:
  import time

  WHAT: Loads Python's built-in time library.
  WHY:  We need time.sleep(30) to pause between retries.
  WHAT time.sleep(30) DOES: Pauses the script for exactly 30 seconds.
    The program does nothing during this time — just waits.
  WHY WE WAIT: When AWS is processing a model subscription, calling the API
    immediately again would just get another error. We wait to give AWS time.


LINE 45:
  import boto3

  WHAT: Loads the AWS SDK (Software Development Kit) for Python.
  WHY:  This is HOW Python talks to AWS. Every single AWS API call goes through
        boto3. Without it, Python has no way to communicate with AWS services.
  INSTALL: pip install boto3  (not built into Python — must be installed separately)
  NOTE: boto3 uses your AWS credentials (~/.aws/credentials or environment variables)
        to authenticate. If credentials are wrong, every API call fails.


LINE 46:
  from botocore.exceptions import ClientError

  WHAT: Imports one specific error type from botocore (boto3's underlying library).
  WHY:  When an AWS API call fails, boto3 throws a ClientError.
  EXAMPLE: If you try to invoke a model you don't have permission for, AWS returns
           "AccessDeniedException". Boto3 wraps this in a ClientError.
  HOW WE USE IT:
    try:
        client.some_api_call()        ← might fail
    except ClientError as e:          ← catch the error
        print(e.response["Error"]["Code"])   ← "AccessDeniedException"
        print(e.response["Error"]["Message"]) ← "User is not authorized..."


LINES 48-53:
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s [%(levelname)s] %(message)s",
      datefmt="%Y-%m-%d %H:%M:%S",
  )
  logger = logging.getLogger(__name__)

  LINE 48: logging.basicConfig( — Start configuring the logging system.
  LINE 49: level=logging.INFO — Only show messages with importance INFO or higher.
           Importance levels (low to high): DEBUG < INFO < WARNING < ERROR < CRITICAL
           With INFO, DEBUG messages are hidden. With --verbose we change to DEBUG.
  LINE 50: format="%(asctime)s [%(levelname)s] %(message)s"
           This is a template for each log line:
             %(asctime)s   → replaced with current date/time
             %(levelname)s → replaced with INFO, WARNING, or ERROR
             %(message)s   → replaced with your actual message
           Result example: "2026-03-16 10:30:00 [INFO] Model responded!"
  LINE 51: datefmt="%Y-%m-%d %H:%M:%S"
           How to format the date/time:
             %Y = 4-digit year (2026)
             %m = 2-digit month (03)
             %d = 2-digit day (16)
             %H = hour (10), %M = minute (30), %S = second (00)
  LINE 52: ) — Close the basicConfig call.
  LINE 53: logger = logging.getLogger(__name__)
           Creates a logger object named after this file.
           __name__ is a special Python variable. When you run the file directly,
           it equals "__main__". When imported, it equals the filename.
           We use this logger throughout: logger.info("message"), logger.error("message")


LINES 60-98: MODEL_CATALOG dictionary

  LINE 60: MODEL_CATALOG = {
           Creates a dictionary (lookup table) called MODEL_CATALOG.

  LINE 62: "nova2-lite": {"id": "amazon.nova-2-lite-v1:0", "needs_profile": True, "provider": "amazon"},

           This is ONE entry in the dictionary.
           KEY:   "nova2-lite"  — the shorthand name humans type
           VALUE: a nested dictionary with three pieces of information:
             "id":            "amazon.nova-2-lite-v1:0"  — the official AWS model ID
             "needs_profile": True   — this model REQUIRES a geographic prefix (au., us., etc.)
             "provider":      "amazon" — which company made this model

           When the script sees "nova2-lite", it looks up this entry and gets all three values.

  LINES 63-97: Same pattern for every other model. Each line is one model entry.

           Models with "needs_profile": True  → NEWER models that need au.xxx prefix
           Models with "needs_profile": False → OLDER models that accept direct ID

  LINE 98: }  — Closes the MODEL_CATALOG dictionary.


LINES 103-115: MODEL_GROUPS dictionary

  LINE 103: MODEL_GROUPS = {

  LINE 104: "nova2-all": ["nova2-lite", "nova2-sonic", "nova2-premier"],

            KEY:   "nova2-all" — the group name
            VALUE: a LIST of alias names that this group expands to

            When user types "nova2-all", the script replaces it with all three aliases.

  LINES 105-114: Same pattern for other groups.

  LINE 115: }


LINES 120-126: PREFIX_MAP dictionary

  LINE 120: PREFIX_MAP = {
  LINE 121: "au": "au",  — When user types --prefix au, the prefix string is "au"
                           This gets prepended to model IDs: "au" + "." + "model-id"
                           au = Australia (routes between Sydney and Melbourne)
  LINE 122: "us": "us",  — US regions
  LINE 123: "eu": "eu",  — EU regions
  LINE 124: "ap": "ap",  — Asia-Pacific regions
  LINE 125: "global": "global", — Any commercial region worldwide (~10% cheaper)
  LINE 126: }


================================================================================
FUNCTION: resolve_model_ids (Lines 129-174)
PURPOSE: Convert what the user typed into final AWS-ready model IDs
================================================================================

LINE 129: def resolve_model_ids(inputs: list, prefix: str) -> list:

  def          — "I am defining a function"
  resolve_model_ids — the function's name
  (inputs: list, prefix: str) — two parameters (inputs to the function):
    inputs: list  — a list of strings the user typed (e.g., ["nova2-all", "mistral-large"])
    prefix: str   — the geographic prefix (e.g., "au")
  -> list        — this function returns a list

LINES 130-133: Docstring explaining what the function does.

LINE 135: expanded = []
  Creates an empty list called "expanded". We will fill it with individual model aliases.
  Think of it as an empty shopping bag we'll put items into.

LINE 136: for item in inputs:
  A "for loop". It takes each item from the inputs list, one at a time,
  and runs the indented code below for each one.
  If inputs = ["nova2-all", "mistral-large"], the loop runs twice:
    First time: item = "nova2-all"
    Second time: item = "mistral-large"

LINE 137: lower = item.lower()
  .lower() converts text to all lowercase letters.
  "Nova2-Lite" becomes "nova2-lite"
  WHY: So the user can type "Nova2-Lite" or "NOVA2-LITE" or "nova2-lite" and all work.

LINE 140: if lower in MODEL_GROUPS:
  "in" checks if the key exists in the dictionary.
  If lower is "nova2-all" and MODEL_GROUPS has a key "nova2-all", this is True.

LINE 141: logger.info(f"Expanded group '{item}' -> {len(MODEL_GROUPS[lower])} models")
  Prints a log message. The f"..." is an "f-string" — Python replaces {expressions}
  with their values.
  f"Expanded group '{item}' -> {len(MODEL_GROUPS[lower])} models"
  becomes: "Expanded group 'nova2-all' -> 3 models"
  len() counts how many items are in a list.

LINE 142-143: for alias in MODEL_GROUPS[lower]:
                  expanded.append(alias)
  MODEL_GROUPS["nova2-all"] returns ["nova2-lite", "nova2-sonic", "nova2-premier"]
  This inner loop takes each alias and adds it to our expanded list.
  .append(item) adds one item to the end of a list.

LINE 144: continue
  "Skip the rest of the loop body and go to the next item."
  Since we already handled this item as a group, we don't want to also add it
  as a single alias on line 147.

LINE 147: expanded.append(item)
  If the item is NOT a group (the "if" on line 140 was False), add it as-is.
  This handles single aliases like "mistral-large" and raw IDs.


LINE 150: resolved = []
  Another empty list. This will hold the FINAL model IDs with prefixes applied.

LINE 151: for item in expanded:
  Loop through the expanded list. At this point, all groups have been broken into
  individual aliases. So this list might be:
  ["nova2-lite", "nova2-sonic", "nova2-premier", "mistral-large"]

LINE 152: lower = item.lower()
  Convert to lowercase again (same reason as before).

LINE 154: if lower in MODEL_CATALOG:
  Check if this alias exists in our model catalog.

LINE 155: entry = MODEL_CATALOG[lower]
  Get the full model info. Example:
  entry = {"id": "amazon.nova-2-lite-v1:0", "needs_profile": True, "provider": "amazon"}

LINE 156: if entry["needs_profile"]:
  Check if this model needs a geographic prefix.

LINE 157: final_id = f"{prefix}.{entry['id']}"
  Build the inference profile ID by combining prefix + "." + base model ID.
  Example: f"au.amazon.nova-2-lite-v1:0"
  The f"..." is an f-string. {prefix} becomes "au", {entry['id']} becomes
  "amazon.nova-2-lite-v1:0".

LINE 158: logger.info(f"  '{item}' -> '{final_id}' (inference profile)")
  Log what happened so the user can see the resolution.

LINE 159-161: else block — model does NOT need a profile
  final_id = entry["id"]   — just use the raw ID as-is, no prefix
  logger.info(...)         — log it

LINE 162: resolved.append(final_id)
  Add the final ID to our resolved list.

LINE 163-165: else block — item NOT in MODEL_CATALOG
  The user passed something that isn't in our catalog.
  Assume it's a raw model ID or inference profile ID and pass it through unchanged.
  This lets users type "au.anthropic.claude-sonnet-4-6" directly.


LINES 167-174: Deduplication

LINE 168: seen = set()
  Creates an empty "set". A set is like a list but it cannot contain duplicates.
  It's very fast at checking "have I seen this before?"

LINE 169: unique = []
  Empty list for the deduplicated results.

LINE 170: for mid in resolved:
  Loop through every resolved model ID.

LINE 171: if mid not in seen:
  "Have I seen this model ID before?" If NO:

LINE 172: seen.add(mid)
  Add it to the "seen" set so we know we've processed it.

LINE 173: unique.append(mid)
  Add it to the unique list.

  If the same ID appears again later, line 171 will be False and we skip it.

LINE 174: return unique
  Send the deduplicated list back to whoever called this function.


================================================================================
FUNCTION: detect_provider (Lines 177-192)
PURPOSE: Figure out which company made a model by looking at its ID text
================================================================================

LINE 177: def detect_provider(model_id: str) -> str:
  Takes a model ID string, returns a provider name string.

LINE 179: ml = model_id.lower()
  Convert to lowercase for case-insensitive matching.

LINE 180: if "anthropic" in ml or "claude" in ml:
  "in" checks if a substring exists anywhere in the string.
  "anthropic" in "au.anthropic.claude-sonnet-4-6" → True
  The "or" means: if EITHER word is found, it's Anthropic.

LINE 181: return "anthropic"
  Found it. Return the provider name and exit the function immediately.

LINES 182-191: Same pattern for each provider. Checks for keywords:
  - amazon, titan, nova → "amazon"
  - meta, llama → "meta"
  - mistral, mixtral → "mistral"
  - cohere, command → "cohere"
  - ai21, jamba → "ai21"

LINE 192: return "unknown"
  If no keywords matched, we don't know the provider.


================================================================================
FUNCTION: ensure_use_case_submitted (Lines 198-239)
PURPOSE: Submit the Anthropic use case form (one-time per AWS account)
ONLY CALLED FOR: Claude/Anthropic models
================================================================================

LINE 198: def ensure_use_case_submitted(bedrock_client, region: str, profile: str = None):
  Three parameters:
    bedrock_client — the AWS Bedrock control-plane connection
    region — which AWS region we're using (e.g., "ap-southeast-2")
    profile = None — optional AWS CLI profile. "= None" means if not provided,
                     it defaults to None (nothing).

LINE 200: try:
  Start of error handling block. "Try the code below. If it fails, jump to except."

LINE 201: bedrock_client.get_use_case_for_model_access()
  Calls the AWS API to check: "Has a use case form been submitted for this account?"
  If YES: the call succeeds, and we move to line 202.
  If NO:  the call throws a ClientError, and we jump to line 204.

LINE 202: logger.info("  Use case already submitted.")
  The call succeeded — form already exists. Print a message.

LINE 203: return True
  Return True (meaning "use case is handled, proceed") and exit the function.

LINE 204: except ClientError as e:
  The API call on line 201 failed. Catch the error in variable "e".
  "e" contains all the details about what went wrong.

LINE 205: error_code = e.response["Error"]["Code"]
  Extract the error code from the error object.
  e.response is a dictionary. We dig into ["Error"]["Code"] to get a string
  like "ResourceNotFoundException" or "ValidationException".

LINE 206: if error_code not in ("ResourceNotFoundException", "ValidationException"):
  "not in" checks if the error code is NOT one of these two expected errors.
  ResourceNotFoundException = "no use case exists" (expected — we'll submit one)
  ValidationException = "form not supported in this region" (also expected)
  ANYTHING ELSE = unexpected problem → log a warning and give up.

LINE 207: logger.warning(f"  Unexpected error: {e}")
LINE 208: return False
  Unexpected error. Return False (meaning "use case not handled, problem occurred").

LINE 210: logger.info("  Submitting use case form...")
  If we got here, the error was expected (no form exists). Proceed to submit.

LINES 211-217: form_data = {...}
  A Python dictionary containing the form fields. Same data you'd type into
  the AWS console form. Customize these for your organization.
  json.dumps() on line 220 will convert this to a JSON text string.

LINE 220: bedrock_client.put_use_case_for_model_access(formData=json.dumps(form_data))
  Calls the AWS API to submit the form.
  json.dumps(form_data) converts the Python dictionary to a JSON string because
  the AWS API expects JSON text, not a Python dictionary.

LINE 221: logger.info("  Use case submitted.")
LINE 222: return True
  Success! Form submitted. Return True.

LINES 223-239: Error handling for the submission.
  If submission fails in the current region (e.g., ap-southeast-2),
  try again in us-east-1 (because the use case endpoint might be global).
  This is a "fallback" pattern — try the primary, if it fails, try the backup.

LINE 224: if region != "us-east-1":
  Only try the fallback if we're not already in us-east-1.

LINE 227-228: kw = {"region_name": "us-east-1"}
              if profile: kw["profile_name"] = profile
  Build a dictionary of keyword arguments for creating a new client in us-east-1.
  If the user specified an AWS profile, include it.

LINE 230: boto3.Session(**kw).client("bedrock").put_use_case_for_model_access(...)
  The ** unpacks the dictionary into keyword arguments.
  This is equivalent to: boto3.Session(region_name="us-east-1").client("bedrock").put_...
  Creates a new session → new client → calls the API. All in one line.


================================================================================
FUNCTION: invoke_model_converse (Lines 245-267)
PURPOSE: Send a prompt to an AI model and get a text response
THIS IS THE CORE FUNCTION — where the actual model invocation happens
================================================================================

LINE 245: def invoke_model_converse(runtime_client, model_id: str, prompt: str) -> dict:
  Three inputs:
    runtime_client — AWS Bedrock Runtime client (different from the control-plane client)
    model_id — which model to talk to (e.g., "au.anthropic.claude-sonnet-4-6")
    prompt — the text to send to the model
  Returns: a dictionary with the result

LINE 247: try:
  Start error handling. The API call might fail.

LINES 248-252: The Converse API call.

  LINE 248: response = runtime_client.converse(
    Call the AWS Converse API. This is the UNIFIED API — same format works for
    Claude, Nova, Mistral, Llama, Cohere. The response is stored in "response".

  LINE 249: modelId=model_id,
    Which model to invoke. Accepts inference profile IDs, model IDs, or ARNs.

  LINE 250: messages=[{"role": "user", "content": [{"text": prompt}]}],
    The conversation. A list of messages. Each message has:
      "role": "user" — this message is from the user (you)
                        Other option: "assistant" (the AI's response, for multi-turn chats)
      "content": [{"text": prompt}] — the content is a list of content blocks.
                  Each block can be: {"text": "..."} for text,
                  {"image": ...} for images, {"document": ...} for documents.
                  We send one text block containing our prompt.

  LINE 251: inferenceConfig={"maxTokens": 100, "temperature": 0.1},
    Controls HOW the model generates its response:
      "maxTokens": 100 — Maximum 100 tokens in the response.
                          A token ≈ 3/4 of a word. 100 tokens ≈ 75 words.
                          We keep this small — we just need to verify the model works.
      "temperature": 0.1 — Controls randomness/creativity.
                           0.0 = completely deterministic (same input → same output every time)
                           1.0 = very creative/random
                           0.1 = almost deterministic. We want predictable results.

LINE 253: output = response.get("output", {}).get("message", {})
  The API returns a deeply nested structure. This line digs into it safely.
  response.get("output", {}) — Get the "output" key. If it doesn't exist, return {}.
  .get("message", {})        — From that, get "message". If missing, return {}.
  The .get() method is SAFE — it never crashes. If a key is missing, it returns the default.
  Compare with response["output"]["message"] which would CRASH if "output" doesn't exist.

LINE 254: text = "".join(b.get("text", "") for b in output.get("content", []))
  This line is dense. Breaking it down:
    output.get("content", [])  — Get the "content" list. Default to empty list.
    for b in ...               — Loop through each content block
    b.get("text", "")          — Get the "text" from each block. Default to "".
    "".join(...)               — Concatenate all text pieces into one string.
  The content might have multiple blocks (text, tool_use, etc.). We only want text blocks.

LINE 255: usage = response.get("usage", {})
  Get the usage statistics (how many tokens were consumed). Used for billing info.

LINES 256-261: Return a success dictionary.
  "success": True     — The API call worked
  "response_text": text[:200] — First 200 characters of the response.
                                text[:200] is "slicing" — take characters 0 through 199.
  "input_tokens": ... — How many tokens the prompt consumed
  "output_tokens": ...— How many tokens the response consumed

LINES 262-267: Error handling.
  If the API call fails (except ClientError as e):
  Return a failure dictionary with the error code and message.
  The calling function will decide what to do based on the error code.


================================================================================
FUNCTION: enable_model (Lines 273-347)
PURPOSE: The main orchestrator — enables ONE model by:
  1. Submitting use case form if Anthropic
  2. Invoking the model (triggers auto-enablement)
  3. Retrying on failure
================================================================================

LINE 273-276: Function definition with many parameters.
  bedrock_client  — control-plane client (for use case form)
  runtime_client  — data-plane client (for invoking models)
  model_id        — the resolved model ID (e.g., "au.amazon.nova-2-lite-v1:0")
  prompt          — test prompt to send
  region          — AWS region
  profile=None    — optional AWS CLI profile
  max_retries=3   — try up to 3 times. "=3" means default value.
  retry_delay=30  — wait 30 seconds between retries

LINE 278: provider = detect_provider(model_id)
  Call our detect_provider function to figure out who made this model.

LINE 279: result = {"model_id": model_id, "provider": provider, "status": "UNKNOWN", "response_preview": ""}
  Create a result dictionary. This will be returned at the end.
  Starts with status "UNKNOWN" — will be updated as we go.

LINES 281-284: Print a header banner for this model.
  f"{'='*60}" creates a string of 60 equal signs: "============..."

LINE 287: if provider == "anthropic":
  Decision point. Is this a Claude model?

LINE 288-291: If YES, run the use case submission function.
  If it fails (returns False), set status to "USE_CASE_FAILED" and give up.
  return result — exits the function immediately.

LINE 292-293: If provider is NOT anthropic, skip the use case step.

LINE 296: logger.info(f"  [Step 2] Invoking: \"{prompt[:60]}\"")
  Print the first 60 characters of the prompt. prompt[:60] is slicing.

LINE 298: for attempt in range(1, max_retries + 1):
  The retry loop. range(1, 4) generates: 1, 2, 3.
  So: attempt=1 (first try), attempt=2 (second try), attempt=3 (last try).

LINE 300: r = invoke_model_converse(runtime_client, model_id, prompt)
  Call our invoke function. Store the result in "r".
  "r" will be either {"success": True, ...} or {"success": False, "error_code": ...}

LINE 302: if r["success"]:
  Did it work?

LINES 303-307: YES — Success path.
  Log the response text, token counts.
  Set result status to "ENABLED".
  return result — exit the function. We're done. Model is enabled.

LINE 309: ec = r.get("error_code", "")
  Get the error code. "ec" is short for "error code".

LINE 310: em = r.get("error_message", "")
  Get the error message. "em" is short for "error message".

LINE 312: if ec == "AccessDeniedException":
  Most common error during first-time enablement.
  AWS is still processing the subscription in the background.

LINE 313: if attempt < max_retries:
  Are we still allowed to retry? (attempt 1 or 2 out of 3)

LINE 314-315: logger.info(...) then time.sleep(retry_delay)
  Log that we're waiting, then pause for 30 seconds.

LINE 316: continue
  Jump back to the TOP of the for loop. Start the next attempt.

LINE 317-319: If we've exhausted all retries (attempt == max_retries):
  Log the final error, set status to "ACCESS_DENIED", return.

LINE 321-324: ResourceNotFoundException
  Model doesn't exist in this region. No point retrying. Return immediately.

LINE 326-330: ValidationException with "on-demand throughput"
  This is the specific error you get when you pass a direct model ID for a model
  that REQUIRES an inference profile. The script catches this and gives a helpful message:
  "Try: --prefix au or --prefix global"
  Much better than the raw AWS error which is confusing.

LINE 326: ec == "ValidationException" and "on-demand throughput" in em.lower()
  Two conditions combined with "and". BOTH must be true:
    1. Error code is ValidationException
    2. Error message (lowercased) contains "on-demand throughput"
  This distinguishes this specific error from other ValidationExceptions.

LINE 332-339: ModelNotReadyException or ThrottlingException
  ec in ("ModelNotReadyException", "ThrottlingException")
  "in" checks if ec is one of these two strings.
  Both are temporary — worth retrying.
  For throttling, we wait DOUBLE the normal delay (line 334):
    wait = retry_delay * (2 if ec == "ThrottlingException" else 1)
  This is a "ternary expression": if throttled, multiply by 2. Otherwise multiply by 1.

LINE 341-344: Any other error.
  Unexpected error. Log it and return immediately.

LINE 346-347: If the for loop finishes without returning (all retries exhausted):
  Set status to "FAILED_AFTER_RETRIES" and return.


================================================================================
FUNCTION: main (Lines 353-456)
PURPOSE: The entry point. Runs when you execute the script.
  1. Parse command-line arguments
  2. Handle utility commands (--list-aliases, --list-groups)
  3. Resolve model names to IDs
  4. Create AWS clients
  5. Process each model
  6. Print summary
================================================================================

LINES 354-365: Create the argument parser.

LINE 354: parser = argparse.ArgumentParser(...)
  Creates the parser object.
  description=... — shown when user types --help
  formatter_class=argparse.RawDescriptionHelpFormatter — preserves our formatting in the epilog
  epilog=... — example commands shown after --help output

LINE 366: parser.add_argument("models", nargs="*", help="...")
  Defines a POSITIONAL argument (no -- prefix).
  "models" — the variable name to access it later: args.models
  nargs="*" — accept ZERO or more values. Returns a list.
  Example: "nova2-lite mistral-large" → args.models = ["nova2-lite", "mistral-large"]
  Example: (nothing) → args.models = []

LINE 367: parser.add_argument("--region", default="ap-southeast-2", help="...")
  Defines a NAMED argument with -- prefix.
  default="ap-southeast-2" — if user doesn't specify --region, use this value.
  args.region will be "ap-southeast-2" unless overridden.

LINE 368: parser.add_argument("--profile", default=None, help="...")
  AWS CLI profile name. Defaults to None (use default credentials).

LINE 369-370: parser.add_argument("--prefix", default="au", choices=["au","us","eu","ap","global"],...)
  choices=[...] — ONLY these values are allowed. If user types --prefix xyz, argparse
  shows an error: "invalid choice: 'xyz' (choose from au, us, eu, ap, global)"

LINE 371-372: parser.add_argument("--prompt", default="Reply with exactly: Hello, model enabled successfully.", ...)
  The test prompt. Can be overridden.

LINE 373: parser.add_argument("--retries", type=int, default=3, ...)
  type=int — the value must be an integer (whole number).
  "3" from the command line becomes the integer 3, not the string "3".

LINE 374: parser.add_argument("--retry-delay", type=int, default=30, ...)
  Seconds between retries.

LINE 375: parser.add_argument("--list-aliases", action="store_true", ...)
  action="store_true" — This is a FLAG with no value.
  Present → True:  python script.py --list-aliases → args.list_aliases = True
  Absent → False:  python script.py nova2-lite     → args.list_aliases = False

LINE 379: args = parser.parse_args()
  PARSE the command line. Returns an object where each argument is an attribute.
  After this line: args.models, args.region, args.prefix, etc. are all available.

LINE 380-381: if args.verbose: logging.getLogger().setLevel(logging.DEBUG)
  If --verbose was passed, change logging level to DEBUG (show everything).

LINES 383-391: Handle --list-aliases
  If the flag is set, print a formatted table of all aliases and exit.
  LINE 384: f"{'Alias':<22}" — Left-align "Alias" in a field 22 characters wide.
  LINE 386: for alias, info in sorted(MODEL_CATALOG.items()):
    .items() returns all key-value pairs. sorted() puts them in alphabetical order.
    Each iteration: alias = "claude-haiku-3", info = {"id": "...", "needs_profile": ...}
  LINE 391: return — Exit main(). Don't process any models.

LINES 393-398: Handle --list-groups (same pattern).

LINE 400-401: if not args.models: parser.error(...)
  If no models were provided AND we're not in list mode, show an error.
  parser.error() prints the help message and exits.

LINE 403: prefix = PREFIX_MAP[args.prefix]
  Look up the prefix string. PREFIX_MAP["au"] → "au"

LINE 404: resolved = resolve_model_ids(args.models, prefix)
  Call our resolver function. Gets back the final list of model IDs.

LINE 405: providers = set(detect_provider(m) for m in resolved)
  Figure out which providers are involved.
  set(...) removes duplicates. If 3 models are from "anthropic", the set has just one "anthropic".
  "detect_provider(m) for m in resolved" is a "generator expression" — it runs detect_provider
  on each item and collects the results.

LINES 407-413: Create AWS clients.

LINE 408: skw = {"region_name": args.region}
  Build a dictionary of session keyword arguments. "skw" is short for "session kwargs".

LINE 409-410: if args.profile: skw["profile_name"] = args.profile
  If user specified --profile, add it to the dictionary.

LINE 411: session = boto3.Session(**skw)
  ** unpacks the dictionary into keyword arguments.
  Equivalent to: boto3.Session(region_name="ap-southeast-2")
  or: boto3.Session(region_name="ap-southeast-2", profile_name="my-profile")

LINE 412: bedrock_client = session.client("bedrock")
  Create the CONTROL-PLANE client. Used for management operations (use case form).
  Think of it as the restaurant's front desk.

LINE 413: runtime_client = session.client("bedrock-runtime")
  Create the DATA-PLANE client. Used for invoking models (sending prompts).
  Think of it as the kitchen. DIFFERENT service from "bedrock".

LINES 415-421: Print the banner showing what we're about to do.

LINE 423: results = []
  Empty list to collect results from each model.

LINE 424-427: The main processing loop.
  for mid in resolved:  — Loop through each resolved model ID
    r = enable_model(...)  — Enable it (use case + invoke + retries)
    results.append(r)      — Save the result

LINES 430-443: Print the summary table.
  LINE 438: icon = "OK" if r["status"] == "ENABLED" else "FAIL"
    Ternary expression. If status is ENABLED, icon = "OK". Otherwise icon = "FAIL".
  LINE 439: f"  {r['model_id']:<50}" — Left-align model ID in 50-character field.
  LINE 441: ok += 1 — Increment the success counter. += means "add to".

LINES 445-452: If any models failed, print troubleshooting tips and exit with code 1.
  sys.exit(1) tells the operating system "this script had failures."


LINE 455-456:
  if __name__ == "__main__":
      main()

  __name__ is a special Python variable.
  When you run the file directly: __name__ == "__main__" → True → calls main()
  When you import the file: __name__ == "enable_foundation_models" → False → doesn't call main()
  This lets other scripts import functions from this file without running the whole thing.


================================================================================
================================================================================
SCRIPT 2: enable_embedding_models.py — DIFFERENCES ONLY
================================================================================
================================================================================

The embedding script has the same structure. Below are ONLY the parts that differ.


LINES 48-64: EMBED_CATALOG (instead of MODEL_CATALOG)

  Same concept but with extra fields for embedding-specific info:
    "dims": 1024      — the number of dimensions in the output vector
    "max_tokens": 8192 — maximum input text length in tokens
    "notes": "..."     — human-readable notes about the model


LINES 131-142: invoke_titan_embed_v2 — Titan V2 specific invoke

  LINE 132: body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
    Titan V2 request format:
      "inputText" — the text to convert into a vector
      "dimensions" — how many numbers in the output vector. Titan V2 supports 256, 512, or 1024.
      "normalize" — if True, the vector is normalized (length = 1.0).
                    Important for cosine similarity calculations in search.

  LINE 134-135: resp = client.invoke_model(modelId=model_id, contentType="application/json",
                                           accept="application/json", body=body)
    Uses invoke_model API (NOT converse). Embedding models don't support Converse.
    contentType — tells AWS the format of our request body (JSON)
    accept — tells AWS what format we want the response in (JSON)
    body — the actual request data

  LINE 136: result = json.loads(resp["body"].read())
    resp["body"] is a StreamingBody object. .read() reads all bytes.
    json.loads() converts the JSON bytes to a Python dictionary.

  LINE 137: emb = result.get("embedding", [])
    Extract the embedding vector. It's a list of floating-point numbers:
    [0.0234, -0.1456, 0.0891, -0.0321, 0.1567, ...]

  LINE 138-139: Return success with dimensions, sample values, and token count.
    len(emb) — how many numbers in the vector (should be 1024)
    emb[:5]  — first 5 values as a sample


LINES 145-156: invoke_titan_embed — Older Titan V1
  Same as V2 but simpler request body — no dimensions or normalize options.


LINES 159-170: invoke_cohere_embed — Cohere's DIFFERENT format

  LINE 160: body = json.dumps({"texts": [text], "input_type": "search_document"})
    Cohere uses DIFFERENT field names:
      "texts" — a LIST of texts (Cohere can embed multiple texts in one call)
      "input_type" — tells Cohere how this text will be used:
        "search_document" = text being indexed for search
        "search_query"    = the search query itself
      This affects how the embedding is generated (they're optimized differently).

  LINE 165: embs = result.get("embeddings", [[]])
    Cohere returns a LIST OF LISTS (one embedding per input text).

  LINE 166: emb = embs[0] if embs else []
    Since we sent one text, take the first (and only) embedding.
    "if embs else []" — safety check. If the list is empty, use an empty list.


LINES 187-200: invoke_embedding — The Router Function

  This function looks at the model ID and decides WHICH invoke function to call.
  Each provider has a different request format, so we need different functions.

  LINE 190: if "titan-embed-text-v2" in ml:
    If the model ID contains "titan-embed-text-v2", use the V2 function.
  LINE 192: elif "titan-embed" in ml:
    Otherwise if it contains "titan-embed" (V1 or image), use the generic Titan function.
  LINE 194: elif "cohere.embed" in ml:
    Cohere models use the Cohere-specific function.
  LINE 196: elif "nova" in ml and "embed" in ml:
    Nova embed uses the Nova function.
  LINE 198-200: else — Unknown model. Try Titan format as a fallback.


LINES 206-263: enable_model — Same as Script 1 but simpler
  No Anthropic use case step (embedding models don't need it).
  Calls invoke_embedding() instead of invoke_model_converse().
  Checks dimensions instead of response text.

  LINE 223: logger.info(f"  Sample: {[round(v, 6) for v in r['sample'][:3]]}...")
    round(v, 6) rounds each number to 6 decimal places.
    r['sample'][:3] takes the first 3 values.
    Result: "[0.023456, -0.145678, 0.089123]..."


================================================================================
COMPLETE WORKFLOW — WHAT HAPPENS WHEN YOU RUN THE SCRIPT
================================================================================

Command:
  python enable_foundation_models.py claude-all --prefix au --region ap-southeast-2

Step-by-step execution:

  1. Python reads the file top to bottom
     - Executes all import statements (loads libraries)
     - Executes all variable assignments (MODEL_CATALOG, MODEL_GROUPS, PREFIX_MAP)
     - Reads all function definitions (but does NOT run them yet)
     - Reaches line 455: if __name__ == "__main__": → True → calls main()

  2. main() starts
     - argparse parses: models=["claude-all"], prefix="au", region="ap-southeast-2"

  3. resolve_model_ids(["claude-all"], "au")
     - "claude-all" is in MODEL_GROUPS → expands to:
       ["claude-sonnet-4.6", "claude-opus-4.6", "claude-sonnet-4.5", "claude-haiku-4.5"]
     - For each alias, look up MODEL_CATALOG and apply prefix:
       "claude-sonnet-4.6" → needs_profile=True → "au.anthropic.claude-sonnet-4-6"
       "claude-opus-4.6"   → needs_profile=True → "au.anthropic.claude-opus-4-6-v1"
       "claude-sonnet-4.5" → needs_profile=True → "au.anthropic.claude-sonnet-4-5-20250929-v1:0"
       "claude-haiku-4.5"  → needs_profile=True → "au.anthropic.claude-haiku-4-5-20251001-v1:0"

  4. Create AWS clients for ap-southeast-2

  5. Process Model 1: "au.anthropic.claude-sonnet-4-6"
     a. detect_provider → "anthropic"
     b. IS Anthropic → call ensure_use_case_submitted()
        → get_use_case_for_model_access() → form exists → OK
     c. Attempt 1/3: converse(modelId="au.anthropic.claude-sonnet-4-6", ...)
     d. AWS routes request to Sydney or Melbourne (au prefix)
     e. Claude responds: "Hello, model enabled successfully."
     f. Status: ENABLED

  6. Process Model 2: "au.anthropic.claude-opus-4-6-v1"
     a. detect_provider → "anthropic"
     b. IS Anthropic → ensure_use_case_submitted()
        → form already exists (checked in step 5b) → OK
     c. Attempt 1/3: converse(modelId="au.anthropic.claude-opus-4-6-v1", ...)
     d. Claude responds: "Hello, model enabled successfully."
     e. Status: ENABLED

  7. Process Model 3 and 4: Same pattern.

  8. Print summary:
     au.anthropic.claude-sonnet-4-6                anthropic    [OK] ENABLED
     au.anthropic.claude-opus-4-6-v1               anthropic    [OK] ENABLED
     au.anthropic.claude-sonnet-4-5-20250929-v1:0  anthropic    [OK] ENABLED
     au.anthropic.claude-haiku-4-5-20251001-v1:0   anthropic    [OK] ENABLED

     Enabled: 4/4

  9. All succeeded → script exits with code 0 (success)
