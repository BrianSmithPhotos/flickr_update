#!/usr/bin/env python3
"""Two-step OAuth authorization for Flickr (no interactive input needed).

Step 1 — generate the authorization URL:
    python auth.py

Step 2 — complete the exchange with the verifier code Flickr shows you:
    python auth.py <verifier-code>

The request token is saved to .oauth_request_token between the two steps.
"""

import json
import os
import sys
from pathlib import Path

import flickrapi

REQUEST_TOKEN_FILE = Path(__file__).parent / ".oauth_request_token"

env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

api_key = os.environ["FLICKR_API_KEY"]
api_secret = os.environ["FLICKR_API_SECRET"]

flickr = flickrapi.FlickrAPI(api_key, api_secret, format="parsed-json")

if len(sys.argv) == 1:
    # Step 1: get request token and print authorization URL
    if flickr.token_valid(perms="write"):
        print("Token is already valid — no action needed.")
        sys.exit(0)

    flickr.get_request_token(oauth_callback="oob")
    authorize_url = flickr.auth_url(perms="write")

    # Save the request token/secret so step 2 can complete the exchange
    REQUEST_TOKEN_FILE.write_text(json.dumps({
        "oauth_token": flickr.flickr_oauth.resource_owner_key,
        "oauth_token_secret": flickr.flickr_oauth.resource_owner_secret,
        "requested_permissions": flickr.flickr_oauth.requested_permissions,
    }))

    print(f"\nOpen this URL in your browser and authorize write access:\n\n  {authorize_url}\n")
    print("Then run:\n\n  python auth.py <verifier-code>\n")

elif len(sys.argv) == 2:
    # Step 2: complete exchange using saved request token
    if not REQUEST_TOKEN_FILE.exists():
        print("No pending request token found. Run 'python auth.py' first (step 1).")
        sys.exit(1)

    saved = json.loads(REQUEST_TOKEN_FILE.read_text())
    flickr.flickr_oauth.resource_owner_key = saved["oauth_token"]
    flickr.flickr_oauth.resource_owner_secret = saved["oauth_token_secret"]
    flickr.flickr_oauth.requested_permissions = saved["requested_permissions"]

    verifier = sys.argv[1].replace("-", "")  # accept with or without dashes
    flickr.get_access_token(verifier)
    REQUEST_TOKEN_FILE.unlink(missing_ok=True)
    print("Authorization successful. Token stored in ~/.flickr/oauth-tokens.sqlite")

else:
    print("Usage: python auth.py [verifier-code]")
    sys.exit(1)
