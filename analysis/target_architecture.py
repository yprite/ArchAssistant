from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class TargetUseCaseBlueprint:
    id: str
    name: str
    bounded_context_id: str
    expected_flow_layers: List[str]
    expected_events: List[str]


@dataclass
class TargetBoundedContextSpec:
    id: str
    name: str
    package_patterns: List[str]
    expected_layers: List[str]
    notes: str = ""


@dataclass
class TargetArchitectureSpec:
    name: str
    bounded_contexts: Dict[str, TargetBoundedContextSpec]
    use_case_blueprints: Dict[str, TargetUseCaseBlueprint]
    module_guidelines: Dict[str, bool]


def load_target_architecture_spec(path: str | Path) -> TargetArchitectureSpec:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    name = data.get("name") or Path(path).stem

    bc_specs: Dict[str, TargetBoundedContextSpec] = {}
    for bc in data.get("boundedContexts", []):
        bc_spec = TargetBoundedContextSpec(
            id=bc["id"],
            name=bc.get("name", bc["id"]),
            package_patterns=bc.get("packagePatterns", []),
            expected_layers=bc.get("expectedLayers", []),
            notes=bc.get("notes", ""),
        )
        bc_specs[bc_spec.id] = bc_spec

    uc_specs: Dict[str, TargetUseCaseBlueprint] = {}
    for uc in data.get("useCaseBlueprints", []):
        uc_spec = TargetUseCaseBlueprint(
            id=uc["id"],
            name=uc.get("name", uc["id"]),
            bounded_context_id=uc.get("boundedContextId", ""),
            expected_flow_layers=uc.get("expectedFlowLayers", []),
            expected_events=uc.get("expectedEvents", []),
        )
        uc_specs[uc_spec.id] = uc_spec

    guidelines = data.get("moduleGuidelines", {})
    return TargetArchitectureSpec(
        name=name,
        bounded_contexts=bc_specs,
        use_case_blueprints=uc_specs,
        module_guidelines=guidelines,
    )


def matches_package(pattern: str, package: str) -> bool:
    if not pattern:
        return False
    if pattern.endswith(".*"):
        return package.startswith(pattern[:-2])
    return package.startswith(pattern)
