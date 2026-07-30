#!/usr/bin/env python3
"""Create the first admin/DPO account (chicken-and-egg bootstrap).

Usage:
  python infrastructure/scripts/create_admin.py dpo@company.com --role dpo --name "Jane Doe"

Prints an otpauth:// URI — scan it in Google Authenticator / 1Password, then log in
with the 6-digit code. MFA is mandatory for admin and dpo roles.
"""
import argparse
import getpass
import os
import sys

try:
    import psycopg2
    import pyotp
    from passlib.context import CryptContext
except ImportError:
    sys.exit("Run inside the idp-backend venv: pip install -r apps/idp-console/idp-backend/requirements.txt")

parser = argparse.ArgumentParser()
parser.add_argument("email")
parser.add_argument("--role", default="dpo", choices=["admin", "dpo", "auditor", "analyst"])
parser.add_argument("--name", default="")
args = parser.parse_args()

password = getpass.getpass("Password: ")
if len(password) < 12:
    sys.exit("Password must be at least 12 characters.")
if password != getpass.getpass("Confirm: "):
    sys.exit("Passwords do not match.")

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
first, _, last = args.name.partition(" ")
mfa_required = args.role in {"admin", "dpo"}
secret = pyotp.random_base32() if mfa_required else None

dsn = os.getenv("DATABASE_URL", "postgresql://admin:password@localhost:5432/consent_db")
with psycopg2.connect(dsn) as conn, conn.cursor() as cur:
    cur.execute(
        """INSERT INTO users (email, password_hash, first_name, last_name, role,
                              status, email_verified, mfa_enabled, mfa_secret)
           VALUES (%s, %s, %s, %s, %s, 'active', TRUE, %s, %s)
           ON CONFLICT (email) DO NOTHING
           RETURNING id""",
        (args.email.lower(), pwd_context.hash(password), first, last, args.role,
         bool(secret), secret),
    )
    row = cur.fetchone()
    if row is None:
        sys.exit(f"User {args.email} already exists.")
    user_id = row[0]

print(f"\n{'=' * 70}\n  ADMIN CREATED\n{'=' * 70}")
print(f"  id:    {user_id}\n  email: {args.email}\n  role:  {args.role}")
if secret:
    uri = pyotp.TOTP(secret).provisioning_uri(name=args.email,
                                              issuer_name="Sentinel Privacy Platform")
    print(f"\n  MFA is REQUIRED for this role. Add to your authenticator app:\n")
    print(f"  {uri}\n")
    print(f"  (manual entry secret: {secret})")
print(f"{'=' * 70}\n")
