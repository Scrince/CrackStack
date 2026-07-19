from __future__ import annotations

import importlib.util
import inspect
import pathlib
import sys
import tempfile


class MonkeyPatch:
    def setenv(self, key: str, value: object) -> None:
        import os

        os.environ[key] = str(value)


def main() -> int:
    root = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    failures: list[tuple[str, str, BaseException]] = []

    for path in sorted((root / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for name, func in inspect.getmembers(module, inspect.isfunction):
            if not name.startswith("test_"):
                continue
            kwargs = {}
            temp_dirs: list[tempfile.TemporaryDirectory] = []
            for param in inspect.signature(func).parameters:
                if param == "tmp_path":
                    temp_dir = tempfile.TemporaryDirectory()
                    temp_dirs.append(temp_dir)
                    kwargs[param] = pathlib.Path(temp_dir.name)
                elif param == "monkeypatch":
                    kwargs[param] = MonkeyPatch()
                else:
                    raise RuntimeError(f"unsupported fixture {param} in {path}:{name}")
            try:
                func(**kwargs)
                print(f"PASS {path.name}::{name}")
            except Exception as exc:
                failures.append((path.name, name, exc))
                print(f"FAIL {path.name}::{name}: {exc}")
            finally:
                for temp_dir in temp_dirs:
                    temp_dir.cleanup()

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
