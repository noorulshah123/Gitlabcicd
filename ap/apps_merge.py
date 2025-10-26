def merge_apps_into_proxy_config(appproxy_application_config, team_name, cluster_name, region_name):
    # Small local helpers so you don't have to add globals elsewhere
    def _ensure_proxy_defaults(cfg: dict) -> None:
        cfg.setdefault('proxy', {}).setdefault('specs', [])

    def _parse_s3_uri(uri: str):
        # expects s3://bucket/key...
        if not uri or not uri.startswith("s3://"):
            return (None, None)
        p = uri[5:]
        bucket, _, key = p.partition("/")
        if not bucket or not key:
            return (None, None)
        return (bucket, key)

    try:
        print("Configuring Apps")
        team_apps_s3_uri = os.getenv('TEAM_APPS_S3')
        print("TEAM_APPS_S3:", team_apps_s3_uri)

        # make sure we always have a proxy/specs list so we can safely continue with 0 apps
        _ensure_proxy_defaults(appproxy_application_config)

        # ---- 1) No env var?  Continue with 0 apps (do NOT raise) ----
        if not team_apps_s3_uri:
            print("TEAM_APPS_S3 not set; continuing with 0 apps (OAuth and other config will still be written).")
            return

        # ---- 2) Bad S3 URI format?  Continue with 0 apps ----
        bucket, key = _parse_s3_uri(team_apps_s3_uri)
        if not bucket or not key:
            print(f"Invalid TEAM_APPS_S3 value '{team_apps_s3_uri}'; continuing with 0 apps.")
            return

        # ---- 3) Try to read apps.yml; handle common S3 errors without aborting ----
        s3 = boto3.client('s3')
        try:
            obj = s3.get_object(Bucket=bucket, Key=key)
            body = obj['Body'].read().decode('utf-8')
        except botocore.exceptions.ClientError as e:
            code = e.response.get('Error', {}).get('Code')
            if code in ('NoSuchBucket', 'NoSuchKey', 'AccessDenied'):
                print(f"Apps config not found/inaccessible ({code}) at s3://{bucket}/{key}; continuing with 0 apps.")
                return
            else:
                # unexpected S3 error -> keep previous behavior
                raise

        # ---- 4) Parse YAML safely; if invalid, continue with 0 apps ----
        try:
            apps_cfg = yaml.safe_load(body) or {}
        except yaml.YAMLError as e:
            print(f"apps.yml is not valid YAML ({e}); continuing with 0 apps.")
            return

        # support either {specs: [...]} or a raw list
        specs = apps_cfg.get('specs', apps_cfg if isinstance(apps_cfg, list) else [])
        if not isinstance(specs, list):
            print("apps.yml did not yield a list of specs; continuing with 0 apps.")
            return

        # ------------------------------------------------------------------
        # KEEP YOUR EXISTING NORMALIZATION CODE BELOW, UNCHANGED.
        # (ports, defaults, cpu/mem resolution, image tag mapping,
        #  task role/env injection, tags, sanitize_preinit, etc.)
        #
        # Example skeleton showing where your existing loop lives:
        #
        # new_specs = []
        # for app_spec in specs:
        #     ... your current logic exactly as in your file ...
        #     new_specs.append(app_spec)
        #
        # appproxy_application_config['proxy']['specs'] = new_specs
        # ------------------------------------------------------------------

        # If you don't modify the loop above, at least make sure specs are assigned
        # so application.yml still gets written when apps.yml is present.
        appproxy_application_config['proxy']['specs'] = specs

    except Exception as e:
        # retain existing top-level behavior for truly unexpected errors
        print(f"Unexpected error configuring apps: {e}")
        raise
