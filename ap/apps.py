
############################################


except botocore.exceptions.ClientError as e:
    code = e.response.get('Error', {}).get('Code')
    if code in ('NoSuchBucket', 'NoSuchKey'):
        print(f"No apps.yml found; continuing with 0 apps.")
        specs = []          # <- continue, don’t raise
    else:
        raise


##################################################################

(Optional) Make the “invalid apps config” non-fatal:
if not isinstance(specs, list):
    print("apps.yml did not parse to a list under 'specs'; continuing with 0 apps.")
    specs = []

###############################


# ADD this helper near the top (after imports)
def ensure_proxy_defaults(cfg: dict) -> None:
    proxy = cfg.setdefault('proxy', {})
    proxy.setdefault('authentication', 'oauth2')
    proxy.setdefault('oauth2', {})
    proxy.setdefault('specs', [])
#################

# REPLACE your current function body with this safer version
def setup_oauth_proxy_config(appproxy_application_config: dict, team_name: str, throw_exception: bool = True) -> None:
    """
    Always set proxy.authentication=oauth2 and apply oauth2 settings from Secrets Manager.
    Never print secret values.
    """
    try:
        client = boto3.client('secretsmanager')
        team_sms_secret_name = f"/sap/app-proxy/{team_name}/oauth"
        response = client.get_secret_value(SecretId=team_sms_secret_name)
        secret = json.loads(response['SecretString'])

        # make sure base keys exist
        ensure_proxy_defaults(appproxy_application_config)
        proxy = appproxy_application_config['proxy']

        # build oauth2 block (no prints!)
        oauth2_cfg = {
            'client-id':       secret.get('client_id'),
            'client-secret':   secret.get('client_secret'),
            'authorization-url': secret.get('authorization_url'),
            'token-url':         secret.get('token_url'),
            'logout-url':        secret.get('logout_url', ''),    # optional
            'scopes':            secret.get('scope', ['openid', 'profile', 'email']),
            # if you use these:
            'redirect-url':      secret.get('redirect_url', None),
            'user-name-attribute': secret.get('user_name_attribute', 'preferred_username'),
            'roles-claim':       secret.get('roles_claim', None),
        }
        # drop Nones so we don't write empty keys
        oauth2_cfg = {k: v for k, v in oauth2_cfg.items() if v}

        proxy['authentication'] = 'oauth2'
        proxy['oauth2'] = oauth2_cfg
        # do NOT print secrets here
        print("OAuth configured.")  # generic, safe
    except botocore.exceptions.ClientError as e:
        # If you prefer to continue without OAuth when secret is missing:
        if e.response.get('Error', {}).get('Code') in ('ResourceNotFoundException', 'AccessDeniedException'):
            msg = f"OAuth secret not found/inaccessible for team {team_name}; continuing without OAuth."
            if throw_exception:
                raise RuntimeError(msg) from e
            else:
                print(msg)
                return
        raise

