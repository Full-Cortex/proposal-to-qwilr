"""CLI for creating Qwilr pages from proposal JSON."""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def load_config():
    """Load QwilrConfig from .env with helpful error messages."""
    from proposal_qwilr.schemas import QwilrConfig
    try:
        return QwilrConfig()  # type: ignore[call-arg]
    except Exception as e:
        console.print(
            f"[red]Configuration error: {e}[/red]\n\n"
            "[dim]Make sure you have a .env file. See .env.example for required variables.\n"
            "At minimum you need: QWILR_API_KEY, QWILR_TEMPLATE_ID[/dim]"
        )
        raise SystemExit(1)


def load_proposal(source: str) -> dict:
    """Load proposal JSON from a file path or stdin."""
    if source == "-":
        return json.load(sys.stdin)
    path = Path(source)
    if not path.exists():
        console.print(f"[red]File not found: {source}[/red]")
        raise SystemExit(1)
    return json.loads(path.read_text())


def _get_db(config):
    """Try to get a database connection, or None if Supabase not configured."""
    if not config.supabase_configured:
        return None
    try:
        from proposal_qwilr.database import ProposalDatabase
        return ProposalDatabase(config)
    except Exception as e:
        console.print(f"[yellow]Warning: Supabase not available: {e}[/yellow]")
        return None


@click.group()
def cli():
    """Proposal-to-Qwilr: Convert proposals into interactive Qwilr pages."""
    pass


@cli.command()
@click.argument("source", default="-")
@click.option("--publish", is_flag=True, help="Publish the page immediately")
@click.option("--no-quote", is_flag=True, help="Skip the interactive quote block")
@click.option("--no-db", is_flag=True, help="Skip Supabase save (Qwilr-only mode)")
@click.option("--dry-run", is_flag=True, help="Validate and preview only, don't create page")
@click.option("--update", is_flag=True, help="Update existing Qwilr page instead of creating new")
def create(source: str, publish: bool, no_quote: bool, no_db: bool, dry_run: bool, update: bool):
    """Create a Qwilr page from proposal JSON.

    SOURCE can be a file path or '-' for stdin.
    """
    from proposal_qwilr.schemas import ProposalSchema
    from proposal_qwilr.mapper import ProposalToQwilrMapper
    from proposal_qwilr.client import QwilrClient, QwilrProposalService

    # Load and validate
    raw = load_proposal(source)
    try:
        proposal = ProposalSchema(**raw)
    except Exception as e:
        console.print(f"[red]Invalid proposal data: {e}[/red]")
        raise SystemExit(1)

    # Preview
    table = Table(title="Proposal Preview")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Proposal ID", proposal.proposal_id)
    table.add_row("Title", proposal.title)
    table.add_row("Client", f"{proposal.client.company} ({proposal.client.contact})")
    table.add_row("Starter", f"{proposal.investment.good.name} — {proposal.investment.good.price}")
    table.add_row("Professional", f"{proposal.investment.better.name} — {proposal.investment.better.price}")
    table.add_row("Enterprise", f"{proposal.investment.best.name} — {proposal.investment.best.price}")
    table.add_row("Valid Until", proposal.valid_until)
    table.add_row("Mode", "DRY RUN" if dry_run else ("Update" if update else "Create"))
    table.add_row("Publish", "Yes" if publish else "No (draft)")
    console.print(table)

    if dry_run:
        console.print("[bold green]Validation passed. No page created (dry-run mode).[/bold green]")
        return

    # Check for existing page
    config = load_config()
    db = None if no_db else _get_db(config)

    if db and not update:
        try:
            existing = db.get_proposal(proposal.proposal_id)
            if existing and existing.get("qwilr_page_id"):
                console.print(Panel(
                    f"[yellow]Proposal already has a Qwilr page.[/yellow]\n\n"
                    f"Page ID: {existing['qwilr_page_id']}\n"
                    f"URL: {existing.get('qwilr_url', 'N/A')}\n\n"
                    f"[dim]Use --update to update the existing page.[/dim]",
                    title="Already Published",
                    border_style="yellow",
                ))
                return
        except Exception:
            pass

    # Build payloads
    mapper = ProposalToQwilrMapper()
    page_request = mapper.build_create_page_request(proposal, config.template_id)
    quote_sections = None if no_quote else mapper.build_quote_sections(proposal.investment)

    # Create or update page
    async def _create():
        client = QwilrClient(config)
        service = QwilrProposalService(client, config)
        try:
            if update and db:
                existing = db.get_proposal(proposal.proposal_id)
                if existing and existing.get("qwilr_page_id"):
                    # Update existing page substitutions
                    subs = mapper.build_substitutions(proposal)
                    await client.update_page(existing["qwilr_page_id"], substitutions=subs)
                    return QwilrPageResult(
                        page_id=existing["qwilr_page_id"],
                        url=existing.get("qwilr_url", ""),
                        share_url=existing.get("qwilr_share_url", ""),
                        status=existing.get("qwilr_status", "published"),
                    )
            # Create new page
            return await service.create_proposal_page(
                page_request, quote_sections, publish=publish
            )
        finally:
            await client.close()

    try:
        from proposal_qwilr.schemas import QwilrPageResult  # noqa: F811
        with console.status("[bold green]Creating Qwilr page..."):
            result = asyncio.run(_create())
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled by user.[/yellow]")
        raise SystemExit(130)

    # Output
    action = "updated" if update else "created"
    console.print(Panel(
        f"[bold green]Qwilr page {action}![/bold green]\n\n"
        f"Page ID: {result.page_id}\n"
        f"URL: {result.url}\n"
        f"Share URL: {result.share_url}\n"
        f"Status: {result.status}",
        title="Success",
        border_style="green",
    ))

    # Save to database
    if db:
        try:
            db.upsert_proposal(
                proposal_id=proposal.proposal_id,
                title=proposal.title,
                client_company=proposal.client.company,
                client_contact=proposal.client.contact,
                client_email=proposal.client.email,
                proposal_data=raw,
                valid_until=proposal.valid_until,
            )
            db.update_qwilr_info(proposal.proposal_id, result)
            console.print("[dim]Saved to Supabase[/dim]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not save to database: {e}[/yellow]")


@cli.command()
@click.argument("page_id")
def status(page_id: str):
    """Check the status of a Qwilr page."""
    config = load_config()

    async def _status():
        from proposal_qwilr.client import QwilrClient
        client = QwilrClient(config)
        try:
            return await client.get_page(page_id)
        finally:
            await client.close()

    try:
        data = asyncio.run(_status())
        console.print_json(json.dumps(data, indent=2))
    except KeyboardInterrupt:
        raise SystemExit(130)


@cli.command(name="list")
@click.option("--limit", default=10, help="Number of pages to list")
def list_pages(limit: int):
    """List recent Qwilr pages."""
    config = load_config()

    async def _list():
        from proposal_qwilr.client import QwilrClient
        client = QwilrClient(config)
        try:
            return await client.list_pages(limit=limit)
        finally:
            await client.close()

    try:
        pages = asyncio.run(_list())
        table = Table(title=f"Recent Qwilr Pages (showing {len(pages)})")
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Status", style="green")
        for page in pages:
            table.add_row(
                page.get("id", "N/A"),
                page.get("name", "Untitled"),
                page.get("status", "unknown"),
            )
        console.print(table)
    except KeyboardInterrupt:
        raise SystemExit(130)


@cli.command()
def health():
    """Verify Qwilr API connectivity."""
    config = load_config()

    async def _health():
        from proposal_qwilr.client import QwilrClient
        client = QwilrClient(config)
        try:
            return await client.health_check()
        finally:
            await client.close()

    try:
        ok = asyncio.run(_health())
    except KeyboardInterrupt:
        raise SystemExit(130)

    if ok:
        console.print("[bold green]Qwilr API is reachable and authenticated.[/bold green]")
    else:
        console.print("[bold red]Qwilr API connection failed. Check your API key.[/bold red]")
        raise SystemExit(1)

    # Check Supabase if configured
    if config.supabase_configured:
        db = _get_db(config)
        if db:
            console.print("[bold green]Supabase connection OK.[/bold green]")
        else:
            console.print("[yellow]Supabase configured but connection failed.[/yellow]")
    else:
        console.print("[dim]Supabase not configured (Qwilr-only mode).[/dim]")


@cli.command(name="setup-check")
def setup_check():
    """Verify template and block IDs are configured."""
    import subprocess
    subprocess.run([sys.executable, "scripts/setup_qwilr_template.py"], check=False)


if __name__ == "__main__":
    cli()
