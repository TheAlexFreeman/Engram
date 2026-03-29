from __future__ import annotations

import importlib
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Callable, ClassVar, cast

REPO_ROOT = Path(__file__).resolve().parents[3]


def load_estimator_module() -> ModuleType:
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    try:
        return importlib.import_module("engram_mcp.agent_memory_mcp.sidecar.estimator")
    except ModuleNotFoundError as exc:
        raise unittest.SkipTest(f"sidecar estimator dependencies unavailable: {exc.name}") from exc


class HelpfulnessEstimatorTests(unittest.TestCase):
    estimator_module: ClassVar[ModuleType]

    @classmethod
    def setUpClass(cls) -> None:
        cls.estimator_module = load_estimator_module()

    def _estimate(self) -> Callable[..., float]:
        return cast(Callable[..., float], self.estimator_module.estimate_helpfulness)

    def test_estimate_helpfulness_scores_high_for_direct_reuse(self) -> None:
        score = self._estimate()(
            retrieved_content=(
                "The parser framework defines TranscriptFile, ParsedSession, "
                "and TranscriptParser for normalized session data."
            ),
            response_text=(
                "The parser framework defines TranscriptFile, ParsedSession, "
                "and TranscriptParser for normalized session data."
            ),
            task_description="summarize the parser framework",
        )

        self.assertGreaterEqual(score, 0.75)
        self.assertLessEqual(score, 0.9)

    def test_estimate_helpfulness_scores_mid_for_paraphrase(self) -> None:
        score = self._estimate()(
            retrieved_content=(
                "Checkpoint entries are appended to CURRENT.md with UTC timestamps "
                "and optional session_id comments."
            ),
            response_text=(
                "The checkpoint tool writes UTC-stamped notes to CURRENT.md and can "
                "tag them with the session id."
            ),
            task_description="implement checkpoint persistence",
        )

        self.assertGreaterEqual(score, 0.5)
        self.assertLessEqual(score, 0.6)

    def test_estimate_helpfulness_scores_low_when_content_is_not_used(self) -> None:
        score = self._estimate()(
            retrieved_content=(
                "Checkpoint entries are appended to CURRENT.md with UTC timestamps "
                "and optional session_id comments."
            ),
            response_text="I added CLI flag parsing and left checkpoint behavior unchanged.",
            task_description="wire CLI parsing",
        )

        self.assertGreaterEqual(score, 0.2)
        self.assertLessEqual(score, 0.4)


if __name__ == "__main__":
    unittest.main()
