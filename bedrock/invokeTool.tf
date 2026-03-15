variable "allow_invoke_tool" {
  description = "Allow bedrock:InvokeTool action for consumer/developer roles. Requires risk assessment approval."
  type        = bool
  default     = false
}


######
data "aws_iam_policy_document" "invoke_tool" {
  count = var.allow_invoke_tool ? 1 : 0

  statement {
    sid       = "AllowInvokeTool"
    effect    = "Allow"
    actions   = ["bedrock:InvokeTool"]
    resources = [
      "arn:aws:bedrock:${local.aws_region_name}:${local.aws_caller_identity_account_id}:*"
    ]
  }
}

resource "aws_iam_policy" "invoke_tool" {
  for_each = var.allow_invoke_tool ? var.namespaces : {}
  name     = "${each.key}-invoke-tool"
  policy   = data.aws_iam_policy_document.invoke_tool[0].json
  tags     = var.custom_tags
}

###############
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


###########
allow_invoke_tool = true

allow_invoke_tool = var.allow_invoke_tool

variable "allow_invoke_tool" {
  description = "Allow bedrock:InvokeTool for this team's namespace roles"
  type        = bool
  default     = false
}


############
#V1:
# Foundation models — using aliases
python enable_foundation_models.py nova2-lite nova2-sonic claude-sonnet-4.6

# Foundation models — using full model IDs
python enable_foundation_models.py amazon.nova-2-lite-v1:0 anthropic.claude-sonnet-4-6-v1:0

# Embedding models
python enable_embedding_models.py titan-embed-v2 cohere-embed-en cohere-embed-multi

# Check status before making changes
python enable_foundation_models.py --dry-run nova2-lite claude-sonnet-4.6

# Different region / AWS profile
python enable_foundation_models.py --region us-west-2 --profile ops-account nova2-lite


#V2
# Foundation models — mix of providers
python enable_foundation_models.py nova2-lite nova2-sonic claude-sonnet-4.6 mistral-large command-r-plus

# Embedding models
python enable_embedding_models.py titan-embed-v2 cohere-embed-en cohere-embed-multi

# With retries (if subscription takes time)
python enable_foundation_models.py --retries 5 --retry-delay 60 nova2-lite

# Different region/profile
python enable_foundation_models.py --region us-west-2 --profile ops-account nova2-lite
