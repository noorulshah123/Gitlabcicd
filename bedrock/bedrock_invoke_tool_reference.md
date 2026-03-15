# bedrock:InvokeTool — Complete Reference Documentation

## What is bedrock:InvokeTool

`bedrock:InvokeTool` is an AWS IAM action that controls access to Amazon Bedrock's built-in system tools. These are AWS-managed tools that run server-side, allowing AI models (primarily Amazon Nova) to perform actions beyond text generation — such as searching the live internet or executing Python code.

The default Bedrock role does NOT include InvokeTool. It must be explicitly granted.

---

## System Tools Controlled by InvokeTool

### 1. Web Grounding (nova_grounding)

- **What it does**: Enables Amazon Nova models to search the live internet and return responses with citations
- **How it works**: Model determines if search is needed → performs one or more web searches → synthesizes results into a cited response
- **ARN**: `arn:aws:bedrock::{ACCOUNT_ID}:system-tool/amazon.nova_grounding`
- **Supported models**: Amazon Nova 2 Lite, Nova 2 Sonic, Nova Pro, Nova Lite
- **Regional availability**: Currently available in IAD (us-east-1), PDX (us-west-2), and NRT (ap-northeast-1)
- **API usage**: Passed as a `systemTool` in the `toolConfig` parameter of the Converse API

**Example API call:**
```python
tool_config = {
    "tools": [{
        "systemTool": {
            "name": "nova_grounding"
        }
    }]
}

response = bedrock.converse(
    modelId="us.amazon.nova-2-lite-v1:0",
    messages=[{
        "role": "user",
        "content": [{"text": "What are the latest developments in quantum computing?"}]
    }],
    toolConfig=tool_config
)
```

**IMPORTANT**: Do NOT create a custom `toolSpec` with the name `nova_grounding` — this conflicts with the system tool and causes errors.


### 2. Code Interpreter (nova_code_interpreter)

- **What it does**: Allows Nova models to execute Python code in isolated sandbox environments
- **Use cases**: Mathematical computations, logical operations, iterative algorithms, data analysis
- **ARN**: `arn:aws:bedrock::{ACCOUNT_ID}:system-tool/amazon.nova_code_interpreter`
- **Regional availability**: IAD (us-east-1), PDX (us-west-2), and NRT (ap-northeast-1)
- **Recommendation**: Use Global CRIS (Cross-Region Inference) to ensure requests route to a supported region

---

## IAM Policy Configuration

### Grant InvokeTool for all system tools
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowInvokeTool",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeTool"],
            "Resource": [
                "arn:aws:bedrock::111122223333:system-tool/*"
            ]
        }
    ]
}
```

### Grant InvokeTool for specific tools only
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowWebGroundingOnly",
            "Effect": "Allow",
            "Action": ["bedrock:InvokeTool"],
            "Resource": [
                "arn:aws:bedrock::111122223333:system-tool/amazon.nova_grounding"
            ]
        }
    ]
}
```

### Deny InvokeTool explicitly (for SCPs or restrictive policies)
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DenyInvokeTool",
            "Effect": "Deny",
            "Action": ["bedrock:InvokeTool"],
            "Resource": ["*"]
        }
    ]
}
```

---

## Key Differences: InvokeTool vs Other Bedrock Permissions

### Invocation permissions (runtime / data-plane)

| Permission | What It Does | Resource Type | Risk Level |
|---|---|---|---|
| `bedrock:InvokeModel` | Send prompt to a model, get text/image/embedding back | `foundation-model/*` | Low — model only returns generated content |
| `bedrock:InvokeModelWithResponseStream` | Same as above but response streams word-by-word | `foundation-model/*` | Low — same as InvokeModel, just streamed |
| `bedrock:Converse` | Multi-turn conversation with unified API | `foundation-model/*` | Low — unified wrapper around InvokeModel |
| `bedrock:ConverseStream` | Streaming version of Converse | `foundation-model/*` | Low — same as Converse, just streamed |
| **`bedrock:InvokeTool`** | **Model calls AWS-managed tools (web search, code execution)** | **`system-tool/*`** | **Medium — model reaches outside to internet/code sandbox** |
| `bedrock:InvokeAgent` | Invoke a Bedrock Agent (multi-step autonomous actions) | `agent/*` | High — agent chains tools and makes decisions autonomously |
| `bedrock:InvokeFlow` | Invoke a Bedrock Flow (orchestrated pipeline) | `flow/*` | Medium — runs a pre-defined pipeline |

### Read permissions (control-plane, read-only)

| Permission | What It Does |
|---|---|
| `bedrock:ListFoundationModels` | List available models in the region |
| `bedrock:GetFoundationModel` | Get details about a specific model |
| `bedrock:GetGuardrail` | Read guardrail configuration |
| `bedrock:GetAgent` | Read agent configuration |
| `bedrock:GetKnowledgeBase` | Read knowledge base configuration |
| `bedrock:ListInferenceProfiles` | List inference profiles |

### Write permissions (control-plane, create/update/delete)

| Permission | What It Does |
|---|---|
| `bedrock:CreateGuardrail` | Create safety guardrails |
| `bedrock:UpdateGuardrail` | Modify guardrails |
| `bedrock:CreateAgent` | Create a Bedrock Agent |
| `bedrock:CreateKnowledgeBase` | Create a knowledge base |
| `bedrock:CreateModelCustomizationJob` | Start fine-tuning a model |
| `bedrock:CreateProvisionedModelThroughput` | Reserve dedicated capacity |

### Administration permissions

| Permission | What It Does |
|---|---|
| `bedrock:PutUseCaseForModelAccess` | Submit use case form (Anthropic models) |
| `bedrock:CreateFoundationModelAgreement` | Accept model EULA/terms |
| `bedrock:DeleteFoundationModelAgreement` | Revoke model access |
| `bedrock:TagResource` / `bedrock:UntagResource` | Manage resource tags |

---

## Why InvokeTool Needs Separate Treatment

1. **Different resource type**: InvokeTool targets `system-tool/*` ARNs, not `foundation-model/*`. A policy granting `InvokeModel` on `foundation-model/*` does NOT grant InvokeTool.

2. **Wildcard danger**: If any existing policy uses `bedrock:Invoke*`, it will match InvokeTool. Always use explicit action names.

3. **Not included by default**: The default Bedrock role does not allow InvokeTool. It must be explicitly added.

4. **External reach**: Unlike InvokeModel (which only generates text), InvokeTool allows the AI model to access the live internet (Web Grounding) or execute code (Code Interpreter). This crosses a security boundary.

5. **SCP interactions**: Web Grounding sets the `aws:requestedRegion` condition key to "unspecified". If your SCPs enforce region conditions, you may need to update them.

---

## Terraform Implementation (for your module)

### inputs.tf — new variable
```hcl
variable "allow_invoke_tool" {
  description = "Allow bedrock:InvokeTool for consumer/developer roles. Requires risk assessment."
  type        = bool
  default     = false
}
```

### data-invoke-tool.tf — conditional policy document
```hcl
data "aws_iam_policy_document" "invoke_tool" {
  count = var.allow_invoke_tool ? 1 : 0

  statement {
    sid       = "AllowInvokeTool"
    effect    = "Allow"
    actions   = ["bedrock:InvokeTool"]
    resources = [
      "arn:aws:bedrock::${local.aws_caller_identity_account_id}:system-tool/*"
    ]
  }
}
```

### iam.tf — conditional policy and attachment
```hcl
resource "aws_iam_policy" "invoke_tool" {
  for_each = var.allow_invoke_tool ? var.namespaces : {}
  name     = "${each.key}-invoke-tool"
  policy   = data.aws_iam_policy_document.invoke_tool[0].json
  tags     = var.custom_tags
}

resource "aws_iam_role_policy_attachment" "bedrock_consumer_invoke_tool" {
  for_each   = var.allow_invoke_tool ? var.namespaces : {}
  policy_arn = aws_iam_policy.invoke_tool[each.key].arn
  role       = aws_iam_role.bedrock_consumer[each.key].id
}

resource "aws_iam_role_policy_attachment" "bedrock_developer_invoke_tool" {
  for_each   = var.allow_invoke_tool ? var.namespaces : {}
  policy_arn = aws_iam_policy.invoke_tool[each.key].arn
  role       = aws_iam_role.bedrock_developer[each.key].id
}
```

---

## Official AWS Documentation Links

1. **Nova Web Grounding (InvokeTool usage + IAM)**
   https://docs.aws.amazon.com/nova/latest/nova2-userguide/web-grounding.html

2. **Nova Tool Use (Code Interpreter + custom tools)**
   https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-tools.html

3. **Nova Troubleshooting (InvokeTool permissions errors)**
   https://docs.aws.amazon.com/nova/latest/nova2-userguide/troubleshooting.html

4. **Bedrock Tool Use Overview (Converse API + tool definitions)**
   https://docs.aws.amazon.com/bedrock/latest/userguide/tool-use.html

5. **IAM Actions defined by Amazon Bedrock (full action list)**
   https://docs.aws.amazon.com/service-authorization/latest/reference/list_amazonbedrock.html

6. **Bedrock IAM identity-based policy examples**
   https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_id-based-policy-examples.html

7. **How Amazon Bedrock works with IAM**
   https://docs.aws.amazon.com/bedrock/latest/userguide/security_iam_service-with-iam.html

8. **Simplified model access (SCP/IAM governance)**
   https://aws.amazon.com/blogs/security/simplified-amazon-bedrock-model-access/

9. **IAM permissions reference (community-maintained)**
   https://aws.permissions.cloud/iam/bedrock

10. **Bedrock API Reference**
    https://docs.aws.amazon.com/bedrock/latest/APIReference/welcome.html

---

## Common Errors and Fixes

| Error | Cause | Fix |
|---|---|---|
| `AccessDeniedException` on Web Grounding | Missing `bedrock:InvokeTool` permission | Add IAM policy with InvokeTool on `system-tool/*` resource |
| Web Grounding blocked by SCP | SCP has `aws:requestedRegion` condition | Allow "unspecified" region in SCP for Web Grounding |
| `malformed_tool_use` error | Custom toolSpec named `nova_grounding` | Remove custom toolSpec; use `systemTool` instead |
| Code Interpreter not working | Missing InvokeTool + wrong region | Add InvokeTool permission + use Global CRIS or supported region |
| `bedrock:Invoke*` wildcard grants too much | Wildcard matches InvokeTool unintentionally | Replace with explicit `bedrock:InvokeModel`, `bedrock:InvokeModelWithResponseStream` |
