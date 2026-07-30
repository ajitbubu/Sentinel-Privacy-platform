#!/usr/bin/env python3
"""Bootstrap an API key without an admin account (first-run convenience).

Usage:
  python infrastructure/scripts/create_api_key.py "Salesforce Prod" salesforce --tier premium
"""
import argparse
import hashlib
import os
import secrets

import psycopg2

parser = argparse.ArgumentParser()
parser.add_argument("name")
parser.add_argument("client_system", choices=["salesforce", "hubspot", "outreach", "highspot", "custom"])
parser.add_argument("--tier", default="standard", choices=["standard", "premium", "enterprise"])
parser.add_argument("--scopes", default="consent:write", help="comma-separated")
args = parser.parse_args()

raw = f"sk_live_{secrets.token_urlsafe(32)}"
key_hash = hashlib.sha256(raw.encode()).hexdigest()

dsn = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/consent_db")
with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute(
        """INSERT INTO api_keys (name, client_system, key_hash, key_prefix, tier, scopes)
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id""",
        (args.name, args.client_system, key_hash, raw[:12], args.tier, args.scopes.split(",")),
    )
    key_id = cur.fetchone()[0]

print(f"\n{'=' * 70}\n  API KEY CREATED — store it now, it cannot be retrieved again\n{'=' * 70}")
print(f"  id:     {key_id}\n  name:   {args.name}\n  tier:   {args.tier}\n  key:    {raw}\n{'=' * 70}\n")
