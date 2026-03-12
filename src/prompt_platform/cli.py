from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich import print

from prompt_platform.abtesting import ABTestSimulator
from prompt_platform.config import load_environment_config
from prompt_platform.demo import run_demo
from prompt_platform.evaluation import EvaluationEngine
from prompt_platform.experiments import ExperimentRunner
from prompt_platform.logging_utils import configure_logging
from prompt_platform.model_backends import build_model_client
from prompt_platform.promotion import PromotionManager
from prompt_platform.regression import RegressionDetector
from prompt_platform.registry import PromptRegistry
from prompt_platform.reports import ReportBuilder
from prompt_platform.runtime import PromptResolver
from prompt_platform.storage import FileArtifactStore, SQLiteMetadataStore
from prompt_platform.utils import dump_json, load_json, load_yaml

app = typer.Typer(help="Prompt lifecycle and experimentation platform.")
registry_app = typer.Typer()
eval_app = typer.Typer()
experiment_app = typer.Typer()
regress_app = typer.Typer()
abtest_app = typer.Typer()
demo_app = typer.Typer()
app.add_typer(registry_app, name="registry")
app.add_typer(eval_app, name="eval")
app.add_typer(experiment_app, name="experiment")
app.add_typer(regress_app, name="regress")
app.add_typer(abtest_app, name="abtest")
app.add_typer(demo_app, name="demo")


def build_services(profile: str) -> tuple[PromptRegistry, PromptResolver, SQLiteMetadataStore, FileArtifactStore, dict, str]:
    cfg = load_environment_config(profile)
    metadata = SQLiteMetadataStore(Path(cfg.db_path))
    artifacts = FileArtifactStore(Path(cfg.storage_dir))
    registry = PromptRegistry(metadata, artifacts)
    resolver = PromptResolver(registry)
    return registry, resolver, metadata, artifacts, cfg.backend_configs, cfg.mode


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose")) -> None:
    configure_logging(verbose)


@registry_app.command("create")
def registry_create(name: str = typer.Option(...), file: Path = typer.Option(...), profile: str = typer.Option("local-demo")) -> None:
    registry, _, _, _, _, _ = build_services(profile)
    record = registry.create_or_version(file, created_by="cli-user")
    print({"action": "create", "name": name, "version": record.version})


@registry_app.command("version")
def registry_version(name: str = typer.Option(...), file: Path = typer.Option(...), profile: str = typer.Option("local-demo")) -> None:
    registry, _, _, _, _, _ = build_services(profile)
    record = registry.create_or_version(file, created_by="cli-user")
    print({"action": "version", "name": name, "version": record.version})


@registry_app.command("alias")
def registry_alias(name: str = typer.Option(...), alias: str = typer.Option(...), version: int = typer.Option(...), profile: str = typer.Option("local-demo")) -> None:
    registry, _, _, _, _, _ = build_services(profile)
    print(registry.assign_alias(name, alias, version, "cli-user", "manual alias").model_dump(mode="json"))


@registry_app.command("diff")
def registry_diff(name: str = typer.Option(...), from_version: int = typer.Option(...), to_version: int = typer.Option(...), profile: str = typer.Option("local-demo")) -> None:
    registry, _, _, _, _, _ = build_services(profile)
    print(registry.diff(name, from_version, to_version))


@registry_app.command("list")
def registry_list(query: str = typer.Option(""), profile: str = typer.Option("local-demo")) -> None:
    registry, _, _, _, _, _ = build_services(profile)
    print([item.__dict__ for item in registry.search(query)])


@eval_app.command("run")
def eval_run(
    prompt: str = typer.Option(...),
    dataset: Path = typer.Option(...),
    output: Optional[Path] = typer.Option(None),
    backend: str = typer.Option("mock"),
    profile: str = typer.Option("local-demo"),
) -> None:
    _, resolver, metadata, artifacts, backend_configs, mode = build_services(profile)
    engine = EvaluationEngine(resolver)
    prompt_version = resolver.fetch(prompt)
    client = build_model_client(backend, backend_configs[backend], model=prompt_version.definition.default_model.get("model", "mock-model"))
    result = engine.run(prompt, dataset, backend, client, mode=mode, metrics=["exact_match", "token_f1", "bleu", "rouge_l"])
    metadata.write_evaluation_result(result)
    target = output or Path(f"{artifacts.root}/evaluations/{prompt_version.name}_v{prompt_version.version}.json")
    dump_json(target, result.model_dump(mode="json"))
    print(result.model_dump(mode="json"))


@experiment_app.command("run")
def experiment_run(config: Path = typer.Option(...), profile: str = typer.Option("local-demo")) -> None:
    _, resolver, metadata, artifacts, backend_configs, mode = build_services(profile)
    engine = EvaluationEngine(resolver)
    runner = ExperimentRunner(engine, metadata, artifacts, backend_configs, mode)
    print(runner.run(config))


@regress_app.command("check")
def regress_check(
    baseline: Path = typer.Option(...),
    candidate: Path = typer.Option(...),
    threshold_config: Path = typer.Option(...),
    output: Optional[Path] = typer.Option(None),
) -> None:
    detector = RegressionDetector.from_file(threshold_config)
    result = detector.check(detector.load_result(baseline), detector.load_result(candidate))
    if output:
        dump_json(output, result.model_dump(mode="json"))
    print(result.model_dump(mode="json"))


@abtest_app.command("simulate")
def abtest_simulate(config: Path = typer.Option(...), output: Optional[Path] = typer.Option(None)) -> None:
    result = ABTestSimulator().simulate(config)
    if output:
        dump_json(output, result)
    print(result)


@app.command("promote")
def promote(
    name: str = typer.Option(...),
    from_version: int = typer.Option(...),
    alias: str = typer.Option(...),
    profile: str = typer.Option("local-demo"),
    requested_by: str = typer.Option("platform-bot"),
) -> None:
    registry, _, metadata, _, _, _ = build_services(profile)
    policy = load_yaml(Path("configs/policies/promotion.yaml"))
    manager = PromotionManager(registry, metadata, policy)
    print(manager.promote(name, alias, from_version, requested_by, alias).model_dump(mode="json"))


@app.command("rollback")
def rollback(
    name: str = typer.Option(...),
    alias: str = typer.Option(...),
    to_version: int = typer.Option(...),
    profile: str = typer.Option("local-demo"),
    requested_by: str = typer.Option("platform-bot"),
) -> None:
    registry, _, metadata, _, _, _ = build_services(profile)
    policy = load_yaml(Path("configs/policies/promotion.yaml"))
    manager = PromotionManager(registry, metadata, policy)
    print(manager.rollback(name, alias, to_version, requested_by, alias).model_dump(mode="json"))


@app.command("report")
def report(input: Path = typer.Option(...), format: str = typer.Option("html"), output_dir: Path = typer.Option(Path("artifacts/generated/reports"))) -> None:
    builder = ReportBuilder(output_dir)
    payload = load_json(input)
    path = builder.write(input.stem, payload, format)
    print({"report": str(path)})


@app.command("doctor")
def doctor(profile: str = typer.Option("local-demo")) -> None:
    cfg = load_environment_config(profile)
    print({"profile": cfg.name, "mode": cfg.mode, "storage_dir": cfg.storage_dir, "db_path": cfg.db_path, "backends": list(cfg.backend_configs.keys())})


@demo_app.command("run")
def demo_run(profile: str = typer.Option("local-demo"), output_dir: Path = typer.Option(Path("artifacts/generated/demo"))) -> None:
    registry, resolver, metadata, artifacts, backend_configs, mode = build_services(profile)
    engine = EvaluationEngine(resolver)
    runner = ExperimentRunner(engine, metadata, artifacts, backend_configs, mode)
    policy = load_yaml(Path("configs/policies/promotion.yaml"))
    manager = PromotionManager(registry, metadata, policy)
    payload = run_demo(Path.cwd(), registry, engine, runner, manager, backend_configs, mode, output_dir)
    artifacts.write_json("generated/demo/summary.json", payload)
    artifacts.write_json("generated/demo/evaluations/support_classifier_baseline.json", payload["baseline"])
    artifacts.write_json("generated/demo/evaluations/support_classifier_candidate.json", payload["candidate"])
    print(payload["decision"])


if __name__ == "__main__":
    app()
