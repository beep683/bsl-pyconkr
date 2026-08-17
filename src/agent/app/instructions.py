from pathlib import Path

from .schemas import EvaluationArea

_ROLE_FILES = {
    EvaluationArea.NUTRITION: "nutrition.md",
    EvaluationArea.HEALTH: "health.md",
    EvaluationArea.MENU_QUALITY: "menu-quality.md",
}


class InstructionError(RuntimeError):
    """Raised when rubric or role instructions cannot be loaded."""


class InstructionLoader:
    def __init__(
        self,
        rubric_path: Path | None = None,
        instruction_dir: Path | None = None,
    ) -> None:
        module_path = Path(__file__).resolve()
        self._rubric_path = rubric_path or self._find_rubric(module_path.parent)
        self._instruction_dir = instruction_dir or module_path.parents[1] / "instructions"

    def specialist(self, area: EvaluationArea) -> str:
        return self._combine(self._instruction_dir / _ROLE_FILES[area])

    def judge(self) -> str:
        return self._combine(self._instruction_dir / "judge.md")

    def _combine(self, role_path: Path) -> str:
        return f"{self._read(self._rubric_path)}\n\n---\n\n{self._read(role_path)}"

    @staticmethod
    def _read(path: Path) -> str:
        try:
            content = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            raise InstructionError(f"Unable to read instructions at {path}") from exc
        if not content:
            raise InstructionError(f"Instructions are empty at {path}")
        return content

    @staticmethod
    def _find_rubric(start: Path) -> Path:
        for directory in (start, *start.parents):
            candidate = directory / "EVALUATION_RUBRIC.md"
            if candidate.is_file():
                return candidate
        generated = start.parents[1] / "EVALUATION_RUBRIC.md"
        if generated.is_file():
            return generated
        raise InstructionError("Unable to locate EVALUATION_RUBRIC.md")
