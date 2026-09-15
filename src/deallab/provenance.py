"""
Provenance discipline, carried forward from Trellis and ValuationLab.

Trellis tags every value Demonstrated / Sourced / Assumed. ValuationLab carries the
same idea as `source` / `basis` / `caveat` strings on its result dataclasses. A
transaction model needs it more than either, because an M&A model's output is almost
entirely a function of inputs nobody can derive from a filing: synergy run-rate,
phase-in, cost to achieve, financing mix, CVR probability, exit multiple. A merger
model that reports "3.2% accretive" without reporting which of those six numbers were
invented is not a model, it is a number with a story attached.

So every input that enters a transaction calculation is an `Input`, and every
`Input` that is ASSUMED registers itself. `AssumptionRegister.report()` is the thing a
reviewer reads first: it is the list of numbers on which the entire conclusion rests
and for which no evidence exists.

Deliberately NOT done here: wrapping intermediate arithmetic in Input. Once an Input
crosses into a calculation it becomes a float, and the result dataclass carries the
basis strings. Tagging every intermediate would make the code unreadable for no
analytical gain -- the contested numbers are the entry points, not the multiplications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Basis(Enum):
    DEMONSTRATED = "Demonstrated"  # computed by an upstream module from filed data
    SOURCED = "Sourced"            # quoted from a named filing/release, citation required
    ASSUMED = "Assumed"            # no evidence; a choice, and it must say so


class MissingInputError(RuntimeError):
    """Raised when a calculation reaches for an input that was never supplied.

    This exists so the model cannot fall back to a plausible default. A merger model
    that silently defaults the exit multiple to entry, or the CVR probability to zero,
    produces an answer indistinguishable from a researched one -- and that is the
    single most dangerous failure mode in this whole repo.
    """


@dataclass(frozen=True)
class Input:
    """One numeric input with its evidentiary standing.

    `citation` is mandatory for SOURCED and for ASSUMED -- for SOURCED it is the
    filing, for ASSUMED it is the reasoning ("why this number rather than another").
    An assumption without a stated reason is indistinguishable from a guess, and the
    whole point of the ASSUMED tag is to make the difference visible.
    """
    name: str
    value: float | None
    basis: Basis
    citation: str = ""

    def __post_init__(self):
        if self.basis in (Basis.SOURCED, Basis.ASSUMED) and not self.citation.strip():
            raise ValueError(
                f"Input '{self.name}' is tagged {self.basis.value} with no citation. "
                f"A sourced figure needs the filing; an assumed figure needs the "
                f"reasoning. Untagged numbers are how merger models lie.")

    def required(self) -> float:
        if self.value is None:
            raise MissingInputError(
                f"'{self.name}' has no value. {self.citation or 'No guidance recorded.'}")
        return self.value

    @property
    def is_missing(self) -> bool:
        return self.value is None


def demonstrated(name: str, value: float | None, citation: str = "") -> Input:
    return Input(name, value, Basis.DEMONSTRATED, citation)


def sourced(name: str, value: float | None, citation: str) -> Input:
    return Input(name, value, Basis.SOURCED, citation)


def assumed(name: str, value: float | None, citation: str) -> Input:
    return Input(name, value, Basis.ASSUMED, citation)


def unsourced(name: str, what_to_find: str) -> Input:
    """A required input deliberately left empty, with instructions for filling it.

    Used where a real figure exists in a real filing but has not been read yet. This
    is NOT the same as an assumption: an assumption is a choice made in the absence of
    evidence, this is evidence that exists and hasn't been collected. Collapsing the
    two -- plugging a plausible number and tagging it ASSUMED -- would let a
    researchable fact hide inside the assumption register forever.
    """
    return Input(name, None, Basis.SOURCED,
                 f"NOT YET COLLECTED. {what_to_find}")


@dataclass
class AssumptionRegister:
    """Collects every ASSUMED input that entered a run, plus every input that was
    required but missing. Both lists belong in the output, not in a comment."""
    entries: list[Input] = field(default_factory=list)

    def record(self, *inputs: Input) -> None:
        for i in inputs:
            if ((i.basis is Basis.ASSUMED or i.is_missing)
                    and i.name not in {e.name for e in self.entries}):
                self.entries.append(i)

    @property
    def assumptions(self) -> list[Input]:
        return [e for e in self.entries if e.basis is Basis.ASSUMED and not e.is_missing]

    @property
    def missing(self) -> list[Input]:
        return [e for e in self.entries if e.is_missing]

    def report(self) -> str:
        lines: list[str] = []
        if self.missing:
            lines.append("MISSING INPUTS -- the model cannot run until these are collected:")
            for i in self.missing:
                lines.append(f"  [{i.name}] {i.citation}")
            lines.append("")
        if self.assumptions:
            lines.append("ASSUMPTIONS -- every number below is a choice, not evidence. "
                         "The conclusion is only as good as these:")
            for i in self.assumptions:
                lines.append(f"  [{i.name}] = {i.value:,.4g}")
                lines.append(f"      {i.citation}")
        if not lines:
            lines.append("No assumed or missing inputs recorded -- every input in this "
                         "run is Demonstrated or Sourced.")
        return "\n".join(lines)
