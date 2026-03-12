from typer.testing import CliRunner

from prompt_platform.abtesting import ABTestSimulator
from prompt_platform.cli import app


def test_ab_assignment_is_sticky() -> None:
    simulator = ABTestSimulator()
    variants = {"control": {"weight": 50, "version": 1}, "treatment": {"weight": 50, "version": 2}}
    assert simulator.assign_variant("user-42", variants) == simulator.assign_variant("user-42", variants)


def test_cli_doctor_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["doctor", "--profile", "local-demo"])
    assert result.exit_code == 0
    assert "local-demo" in result.stdout
