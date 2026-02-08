"""CLI entry point for tf-gate."""

import subprocess
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from tf_gate.phases.phase1_ingest import ingest_plan
from tf_gate.phases.phase2_opa import run_phase2_validation
from tf_gate.phases.phase3_context import run_phase3_context_analysis
from tf_gate.phases.phase4_intent import run_phase4_intent_validation
from tf_gate.utils.blast_radius import BlastRadiusLevel
from tf_gate.utils.config import load_config
from tf_gate.utils.git import get_latest_commit_message
from tf_gate.utils.opa import get_default_policy_dir

console = Console()


class BreakGlassContext:
    """Context object for break glass mode."""

    def __init__(self):
        self.break_glass = False
        self.break_glass_reason: Optional[str] = None
        self.shadow_mode = False


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True),
    help="Path to configuration file",
)
@click.option(
    "--break-glass",
    type=str,
    default=None,
    help="Break glass mode with incident ID (e.g., INCIDENT-2024-001)",
)
@click.option(
    "--shadow-mode",
    is_flag=True,
    help="Run in shadow mode (log but don't block)",
)
@click.pass_context
def cli(
    ctx: click.Context, config: Optional[str], break_glass: Optional[str], shadow_mode: bool
) -> None:
    """tf-gate - Terraform Gatekeeper.

    A multi-layered defense system that gates terraform apply behind
    contextual safety checks, semantic validation, and policy-as-code guardrails.
    """
    ctx.ensure_object(BreakGlassContext)
    ctx.obj.break_glass = break_glass is not None
    ctx.obj.break_glass_reason = break_glass
    ctx.obj.shadow_mode = shadow_mode

    # Load configuration
    ctx.obj.config = load_config(config)


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True), required=False)
@click.option(
    "--policy-dir",
    "-p",
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing Rego policy files",
)
@click.option(
    "--terraform-dir",
    "-d",
    type=click.Path(exists=True, file_okay=False),
    default=".",
    help="Directory containing Terraform configuration",
)
@click.option(
    "--use-llm",
    is_flag=True,
    help="Enable LLM-based intent validation (requires LMStudio running)",
)
@click.option(
    "--generate-report",
    is_flag=True,
    help="Generate detailed impact report for tech managers (requires --use-llm)",
)
@click.pass_context
def validate(
    ctx: click.Context,
    plan_file: Optional[str],
    policy_dir: Optional[str],
    terraform_dir: str,
    use_llm: bool,
    generate_report: bool,
) -> int:
    """Validate a Terraform plan through all 4 phases.

    PLAN_FILE is the path to the Terraform plan JSON file.
    If not provided, will look for tfplan.json in the current directory.
    """
    break_glass_ctx = ctx.obj
    config = break_glass_ctx.config

    # Determine plan file path
    if plan_file is None:
        plan_path = Path(terraform_dir) / "tfplan.json"
        if not plan_path.exists():
            console.print("[red]Error: No plan file specified and tfplan.json not found[/red]")
            return 1
    else:
        plan_path = Path(plan_file)

    # Determine policy directory
    if policy_dir is None:
        policy_dir_path = Path(config.get("opa.policy_dir", get_default_policy_dir()))
    else:
        policy_dir_path = Path(policy_dir)

    console.print(
        Panel.fit(
            "[bold blue]Terraform Gatekeeper - 4-Phase Validation Pipeline[/bold blue]",
            border_style="blue",
        )
    )

    # Phase 1: Ingestion & Blast Radius
    console.print("\n[bold]Phase 1: Ingestion & Blast Radius Calculation[/bold]")
    try:
        changes, blast_radius, metadata = ingest_plan(
            plan_path,
            thresholds=config.get("blast_radius.thresholds"),
        )
        console.print(f"   Total resources: {blast_radius.total_resources}")
        console.print(
            f"   Create: {blast_radius.create_count}, Update: {blast_radius.update_count}"
        )
        console.print(
            f"   Delete: {blast_radius.delete_count}, Replace: {blast_radius.replace_count}"
        )

        level_emoji = {"green": "🟢", "yellow": "🟡", "red": "🔴"}[blast_radius.level.value]
        console.print(f"   {level_emoji} Blast Radius Level: {blast_radius.level.value.upper()}")

        if blast_radius.critical_resources:
            console.print("   [red]⚠️  Critical resources affected:[/red]")
            for resource in blast_radius.critical_resources:
                console.print(f"      - {resource}")
    except Exception as e:
        console.print(f"[red]Phase 1 Failed: {e}[/red]")
        return 1

    # Phase 2: Policy Validation
    console.print("\n[bold]Phase 2: Policy Validation (OPA)[/bold]")
    try:
        validation_results = run_phase2_validation(
            policy_dir=policy_dir_path,
            resource_changes=changes,
            blast_radius=blast_radius,
            metadata=metadata,
            strict_mode=config.get("opa.strict_mode", True),
            emergency_override=break_glass_ctx.break_glass,
        )

        deny_count = len(validation_results.get("deny", []))
        warn_count = len(validation_results.get("warn", []))

        if deny_count > 0:
            console.print(f"   [red]❌ {deny_count} policy violations (deny)[/red]")
            for msg in validation_results["deny"]:
                console.print(f"      - {msg}")
        else:
            console.print("   [green]✅ No policy violations[/green]")

        if warn_count > 0:
            console.print(f"   [yellow]⚠️  {warn_count} warnings[/yellow]")
            for msg in validation_results["warn"]:
                console.print(f"      - {msg}")
    except Exception as e:
        console.print(f"[red]Phase 2 Failed: {e}[/red]")
        return 1

    # Phase 3: Context Engine
    console.print("\n[bold]Phase 3: Context Analysis[/bold]")
    context_results = {}
    try:
        from tf_gate.phases.phase3_context import DriftResult, RiskLevel

        context_results = run_phase3_context_analysis(
            terraform_dir=Path(terraform_dir),
            plan_resources=changes,
            terraform_version=metadata.get("terraform_version", "unknown"),
            base_risk=RiskLevel.LOW,
            friday_cutoff_hour=config.get("phases.phase_3_time_gating.friday_cutoff_hour", 15),
            weekend_blocking=config.get("phases.phase_3_time_gating.weekend_blocking", True),
        )

        temporal = context_results["temporal_context"]
        drift = context_results["drift_result"]

        risk_emoji = {
            1: "🟢",
            2: "🟡",
            3: "🔴",
            4: "🔥",
        }.get(temporal.risk_level.value, "⚪")

        console.print(f"   {risk_emoji} Temporal Risk: {temporal.risk_level.name}")
        if temporal.is_weekend:
            console.print("   ⚠️  Weekend deployment detected")
        if temporal.is_friday_afternoon:
            console.print("   ⚠️  Friday afternoon deployment detected")

        if drift.has_drift:
            console.print(
                f"   [yellow]🔄 Drift detected: {len(drift.drifted_resources)} resources[/yellow]"
            )
            if drift.conflict_resources:
                console.print(
                    f"   [red]⚠️  Conflicts: {len(drift.conflict_resources)} resources[/red]"
                )
        else:
            console.print("   ✅ No drift detected")
    except Exception as e:
        console.print(f"[yellow]Phase 3 Warning: {e}[/yellow]")
        # Initialize with empty drift result to avoid errors later
        from tf_gate.phases.phase3_context import DriftResult

        context_results = {
            "drift_result": DriftResult(
                has_drift=False, drifted_resources=[], conflict_resources=[]
            )
        }

    # Phase 4: Intent Validation
    console.print("\n[bold]Phase 4: Intent Validation[/bold]")
    try:
        commit_msg = get_latest_commit_message(Path(terraform_dir))

        if commit_msg:
            # Enable LLM if --use-llm flag is passed OR if enabled in config
            use_llm_enabled = use_llm or config.get("phases.phase_4_intent.enabled", False)
            llm_provider = config.get("phases.phase_4_intent.provider", "lmstudio")

            if use_llm_enabled:
                console.print("   [dim]🤖 Using LLM for intent validation...[/dim]")
                if generate_report:
                    console.print("   [dim]📋 Generating impact report...[/dim]")

            intent_result = run_phase4_intent_validation(
                commit_message=commit_msg,
                resource_changes=changes,
                use_llm=use_llm_enabled,
                llm_provider=llm_provider,
                generate_report=generate_report,
            )

            if intent_result.aligned:
                console.print("   [green]✅ Intent aligned with changes[/green]")
            else:
                console.print("   [yellow]⚠️  Intent mismatch detected[/yellow]")
                console.print(f"   {intent_result.explanation}")

            if intent_result.action_required:
                console.print(
                    f"   [yellow]Action required: {intent_result.action_required}[/yellow]"
                )
            
            # Display impact report if generated
            if intent_result.report:
                console.print("\n   [bold blue]📊 Infrastructure Impact Report[/bold blue]")
                console.print(Panel(intent_result.report, border_style="blue", title="AI Analysis"))
        else:
            console.print("   [yellow]⚠️  No git commit message found[/yellow]")
            console.print("   [dim]💡 Tip: Ensure you're running from a git repository with commits[/dim]")
    except Exception as e:
        console.print(f"[yellow]Phase 4 Warning: {e}[/yellow]")

    # Summary & Decision
    console.print("\n" + "=" * 60)

    should_block = False
    reasons = []

    # Check policy violations
    if deny_count > 0:
        should_block = True
        reasons.append(f"{deny_count} policy violations")

    # Check blast radius
    if blast_radius.level == BlastRadiusLevel.RED:
        should_block = True
        reasons.append("RED blast radius level")

    # Check drift conflicts
    drift_result = context_results.get("drift_result")
    if (
        drift_result
        and hasattr(drift_result, "conflict_resources")
        and drift_result.conflict_resources
    ):
        should_block = True
        reasons.append("Drift conflicts detected")

    # Handle break glass
    if break_glass_ctx.break_glass:
        console.print(f"[red]🔥 BREAK GLASS ACTIVATED: {break_glass_ctx.break_glass_reason}[/red]")
        console.print("[yellow]   This will be audited. Proceeding despite violations.[/yellow]")

        if break_glass_ctx.shadow_mode:
            console.print("   (Shadow mode - would proceed anyway)")

        return 42  # Break glass exit code

    # Handle shadow mode
    if break_glass_ctx.shadow_mode:
        if should_block:
            console.print("[yellow]🎭 SHADOW MODE: Would have blocked for:[/yellow]")
            for reason in reasons:
                console.print(f"   - {reason}")
        else:
            console.print("[green]✅ SHADOW MODE: Would allow apply[/green]")
        return 0

    # Normal decision
    if should_block:
        console.print("[red]❌ VALIDATION FAILED - Apply Blocked[/red]")
        console.print("[red]Reasons:[/red]")
        for reason in reasons:
            console.print(f"   - {reason}")
        console.print("\n[yellow]Use --break-glass=INCIDENT-XXX to bypass in emergencies[/yellow]")
        return 1

    console.print("[green]✅ All 4 phases passed - Apply allowed[/green]")
    return 0


@cli.command()
@click.argument("plan_file", type=click.Path(exists=True), required=False)
@click.option(
    "--auto-approve",
    is_flag=True,
    help="Auto-approve without prompting",
)
@click.pass_context
def apply(ctx: click.Context, plan_file: Optional[str], auto_approve: bool) -> int:
    """Run validation and apply Terraform plan if validation passes."""
    # First run validation
    validate_result = ctx.invoke(validate, plan_file=plan_file)

    if validate_result != 0:
        console.print("\n[red]❌ Validation failed - not proceeding with apply[/red]")
        return validate_result

    # Get plan file path
    if plan_file is None:
        plan_path = Path.cwd() / "tfplan"
        if not plan_path.exists():
            plan_path = Path.cwd() / "tfplan.json"
    else:
        plan_path = Path(plan_file)
        # If JSON file provided, we need a binary plan
        if plan_path.suffix == ".json":
            plan_path = plan_path.with_suffix("")
            if not plan_path.exists():
                console.print("[red]Error: Binary plan file not found[/red]")
                return 1

    if not auto_approve:
        click.confirm("\nDo you want to proceed with terraform apply?", abort=True)

    # Run terraform apply
    console.print("\n[bold]Running terraform apply...[/bold]")
    try:
        result = subprocess.run(
            ["terraform", "apply", str(plan_path)],
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        console.print("[red]Error: terraform command not found[/red]")
        return 1


@cli.command()
@click.argument("terraform_dir", type=click.Path(exists=True, file_okay=False), default=".")
@click.option(
    "--out",
    "-o",
    type=click.Path(),
    default="tfplan",
    help="Output plan file name",
)
@click.option(
    "--json-out",
    "-j",
    type=click.Path(),
    default="tfplan.json",
    help="Output JSON plan file name",
)
def plan(terraform_dir: str, out: str, json_out: str) -> int:
    """Run terraform plan and convert to JSON.

    This is a convenience wrapper around 'terraform plan' that also
    generates a JSON version for tf-gate validation.
    """
    terraform_path = Path(terraform_dir)
    plan_file = terraform_path / out
    json_file = terraform_path / json_out

    console.print(f"[bold]Running terraform plan in {terraform_dir}...[/bold]")

    try:
        # Run terraform plan
        result = subprocess.run(
            ["terraform", "plan", "-out", str(plan_file)],
            cwd=terraform_path,
            check=False,
        )

        if result.returncode != 0:
            console.print("[red]terraform plan failed[/red]")
            return result.returncode

        # Convert to JSON
        console.print(f"Converting plan to JSON: {json_file}")
        result = subprocess.run(
            ["terraform", "show", "-json", str(plan_file)],
            cwd=terraform_path,
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            with open(json_file, "w") as f:
                f.write(result.stdout)
            console.print(f"[green]✅ Plan saved to {plan_file} and {json_file}[/green]")
        else:
            console.print(
                f"[yellow]Warning: Could not convert plan to JSON: {result.stderr}[/yellow]"
            )

        return 0

    except FileNotFoundError:
        console.print("[red]Error: terraform command not found[/red]")
        return 1


@cli.command()
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing configuration",
)
def init(force: bool) -> None:
    """Initialize tf-gate in the current directory.

    Creates default configuration file and policies directory.
    """
    config_file = Path("tf-gate.yaml")
    policies_dir = Path("policies")

    # Create config file
    if config_file.exists() and not force:
        console.print(
            f"[yellow]Config file {config_file} already exists. Use --force to overwrite.[/yellow]"
        )
    else:
        config_content = """# tf-gate Configuration
opa:
  policy_dir: "./policies"
  strict_mode: true

phases:
  phase_3_time_gating:
    friday_cutoff_hour: 15
    weekend_blocking: true

  phase_4_intent:
    provider: "lmstudio"  # Options: "ollama", "openai", "lmstudio"
    model: "qwen2.5-coder-7b-instruct"  # Model name for LMStudio
    enabled: false  # Set to true to enable LLM validation by default

blast_radius:
  thresholds:
    green: 5
    yellow: 20
    red: 50

notifications:
  slack_webhook: null
  pagerduty_key: null
"""
        with open(config_file, "w") as f:
            f.write(config_content)
        console.print(f"[green]✅ Created {config_file}[/green]")

    # Create policies directory
    if not policies_dir.exists():
        policies_dir.mkdir()
        console.print(f"[green]✅ Created {policies_dir}/ directory[/green]")

    # Copy default policies from package
    default_policies = get_default_policy_dir()
    if default_policies.exists():
        import shutil

        for policy_file in default_policies.glob("*.rego"):
            dest = policies_dir / policy_file.name
            # Skip if source and dest are the same file
            if policy_file.resolve() == dest.resolve():
                continue
            if not dest.exists() or force:
                shutil.copy2(policy_file, dest)
                console.print(f"[green]✅ Copied {policy_file.name}[/green]")

    console.print("\n[bold]Initialization complete![/bold]")
    console.print("Run 'tf-gate validate' to validate a Terraform plan.")


@cli.command()
@click.option(
    "--policy-dir",
    "-p",
    type=click.Path(exists=True, file_okay=False),
    help="Directory containing Rego policy files",
)
def check_policies(policy_dir: Optional[str]) -> int:
    """Check that all policies compile correctly."""
    from tf_gate.utils.opa import OPAClient

    if policy_dir is None:
        policy_path = get_default_policy_dir()
    else:
        policy_path = Path(policy_dir)

    console.print(f"[bold]Checking policies in {policy_path}...[/bold]")

    try:
        client = OPAClient()
        client.compile_policies(policy_path)
        console.print("[green]✅ All policies compiled successfully[/green]")
        return 0
    except Exception as e:
        console.print(f"[red]❌ Policy check failed: {e}[/red]")
        return 1


@cli.command()
def version() -> None:
    """Show tf-gate version information."""
    from tf_gate import __version__

    console.print(f"[bold]tf-gate[/bold] version {__version__}")

    # Show OPA version if available
    try:
        from tf_gate.utils.opa import OPAClient

        client = OPAClient()
        opa_version = client.check_version()
        console.print(f"OPA: {opa_version}")
    except Exception:
        console.print("[yellow]OPA: not found[/yellow]")


def main() -> int:
    """Main entry point."""
    return cli(standalone_mode=False)


if __name__ == "__main__":
    sys.exit(main())
