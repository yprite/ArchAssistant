from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Set

DOMAIN_ANNOTATIONS = {"Entity", "Embeddable", "Value"}
APPLICATION_ANNOTATIONS = {"Service", "Transactional"}
INBOUND_ANNOTATIONS = {"RestController", "Controller", "KafkaListener", "RabbitListener"}
OUTBOUND_ANNOTATIONS = {"Repository"}
OUTBOUND_IMPORT_HINTS = {"JpaRepository", "CrudRepository"}
OUTBOUND_IMPORT_SUFFIXES = {"Template"}


@dataclass
class ClassificationRules:
    domain_annotations: Set[str] = field(default_factory=lambda: set(DOMAIN_ANNOTATIONS))
    application_annotations: Set[str] = field(
        default_factory=lambda: set(APPLICATION_ANNOTATIONS)
    )
    inbound_annotations: Set[str] = field(default_factory=lambda: set(INBOUND_ANNOTATIONS))
    outbound_annotations: Set[str] = field(default_factory=lambda: set(OUTBOUND_ANNOTATIONS))
    outbound_import_hints: Set[str] = field(default_factory=lambda: set(OUTBOUND_IMPORT_HINTS))
    outbound_import_suffixes: Set[str] = field(
        default_factory=lambda: set(OUTBOUND_IMPORT_SUFFIXES)
    )


def classify_component(
    package: str,
    annotations: Iterable[str],
    imports: Iterable[str],
    name: str,
    is_interface: bool,
    rules: ClassificationRules | None = None,
) -> str:
    rules = rules or ClassificationRules()
    annotation_set = {a.strip("@").strip() for a in annotations}
    imports_list = list(imports)
    package_lower = package.lower()
    name_clean = name.strip()
    name_lower = name_clean.lower()

    if ".domain." in package_lower or annotation_set & rules.domain_annotations:
        return "domain"

    if annotation_set & rules.inbound_annotations:
        return "inbound_adapter"

    if annotation_set & rules.outbound_annotations:
        return "outbound_adapter"

    for imp in imports_list:
        if any(hint in imp for hint in rules.outbound_import_hints):
            return "outbound_adapter"
        if any(imp.endswith(suffix) for suffix in rules.outbound_import_suffixes):
            return "outbound_adapter"

    is_application_candidate = (
        ".application." in package_lower
        or annotation_set & rules.application_annotations
        or name_lower.endswith("service")
    )
    if is_application_candidate:
        if is_inbound_port(name_clean, package_lower, is_interface):
            return "inbound_port"
        if is_outbound_port(name_clean, package_lower, is_interface):
            return "outbound_port"
        return "application"

    return "unknown"


def is_inbound_port(name: str, package_lower: str, is_interface: bool) -> bool:
    score = 0
    inbound_package_hints = (
        ".application.port.in.",
        ".application.ports.in.",
        ".application.input.",
    )
    if any(hint in package_lower for hint in inbound_package_hints):
        score += 2

    inbound_suffixes = ("usecase", "inputport", "inport", "command", "query")
    if name.lower().endswith(inbound_suffixes):
        score += 1

    if is_interface:
        score += 1

    return score >= 2


def is_outbound_port(name: str, package_lower: str, is_interface: bool) -> bool:
    score = 0
    outbound_package_hints = (
        ".application.port.out.",
        ".application.ports.out.",
        ".application.output.",
    )
    if any(hint in package_lower for hint in outbound_package_hints):
        score += 2

    outbound_suffixes = ("port", "outputport", "outport", "gateway", "client")
    if name.lower().endswith(outbound_suffixes):
        score += 1

    if is_interface:
        score += 1

    return score >= 2
