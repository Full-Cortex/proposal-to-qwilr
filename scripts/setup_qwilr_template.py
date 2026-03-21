"""Setup guide and helper for creating the Qwilr template.

This script documents the manual steps needed in the Qwilr UI
and can verify that the template and block IDs are correctly configured.
"""
import asyncio
import sys

from proposal_qwilr.schemas import QwilrConfig
from proposal_qwilr.client import QwilrClient


TEMPLATE_SETUP_GUIDE = """
╔══════════════════════════════════════════════════════════════╗
║           Qwilr Template Setup Guide                        ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  1. Log into Qwilr at https://app.qwilr.com                ║
║                                                              ║
║  2. Create a new page called "Agency Proposal"              ║
║                                                              ║
║  3. Add blocks in this order:                                ║
║     a. Splash block (hero) with tokens:                     ║
║        - {{title}}                                           ║
║        - {{client_company}}                                  ║
║     b. Text block with token: {{executive_summary}}         ║
║     c. Text block with token: {{understanding}}             ║
║     d. Text block with token: {{approach}}                  ║
║     e. Text block with token: {{scope_html}}                ║
║     f. Text block with token: {{timeline_html}}             ║
║     g. (Leave space for Quote block)                        ║
║     h. Text block with token: {{why_us_html}}               ║
║     i. Text block with token: {{next_steps_html}}           ║
║     j. Text block with token: {{valid_until}}               ║
║     k. Accept block (e-signature)                           ║
║                                                              ║
║  4. Save as template                                        ║
║                                                              ║
║  5. Copy the template ID from the URL:                      ║
║     https://app.qwilr.com/#/page/<TEMPLATE_ID>              ║
║                                                              ║
║  6. Create a Quote block, configure as side-by-side cards   ║
║     and save it to your block library                       ║
║                                                              ║
║  7. Copy the saved block ID                                 ║
║                                                              ║
║  8. Add both IDs to your .env:                              ║
║     QWILR_TEMPLATE_ID=<template_id>                         ║
║     QWILR_QUOTE_BLOCK_ID=<block_id>                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""


async def verify_setup():
    """Verify that the Qwilr API key and template ID are configured."""
    try:
        config = QwilrConfig()  # type: ignore[call-arg]
    except Exception as e:
        print(f"\n[ERROR] Could not load config from .env: {e}")
        print("Make sure you have a .env file with QWILR_API_KEY set.")
        return False

    client = QwilrClient(config)
    try:
        healthy = await client.health_check()
        if healthy:
            print("\n[OK] Qwilr API connection successful")
        else:
            print("\n[ERROR] Qwilr API connection failed - check your API key")
            return False

        if config.template_id:
            print(f"[OK] Template ID configured: {config.template_id}")
        else:
            print("[WARN] No QWILR_TEMPLATE_ID set in .env")

        if config.quote_block_id:
            print(f"[OK] Quote block ID configured: {config.quote_block_id}")
        else:
            print("[WARN] No QWILR_QUOTE_BLOCK_ID set in .env (quote blocks will be skipped)")

        templates = await client.list_templates()
        print(f"\n[INFO] Found {len(templates)} templates in your account:")
        for t in templates:
            print(f"  - {t.get('name', 'Unnamed')} (ID: {t.get('id', 'N/A')})")

        return True
    finally:
        await client.close()


if __name__ == "__main__":
    print(TEMPLATE_SETUP_GUIDE)
    print("\nVerifying your setup...\n")
    success = asyncio.run(verify_setup())
    sys.exit(0 if success else 1)
