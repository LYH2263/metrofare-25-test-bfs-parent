"""极简 pytest shim：无 pip 环境下运行本仓测试（测试只依赖标准库）。"""
import importlib.util
import inspect
import pathlib
import sys
import tempfile
import types
import traceback

pytest = types.ModuleType("pytest")


class _Raises:
    def __init__(self, exc):
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, et, ev, tb):
        if et is None:
            raise AssertionError(f"DID NOT RAISE {self.exc}")
        return issubclass(et, self.exc)


def raises(exc):
    return _Raises(exc)


class _MonkeyPatch:
    def setattr(self, obj, name, value):
        setattr(obj, name, value)


def _fixture(*args, **kwargs):
    if args and callable(args[0]):  # 裸 @pytest.fixture
        return args[0]
    return lambda f: f  # @pytest.fixture(...)


pytest.raises = raises
pytest.fixture = _fixture
sys.modules["pytest"] = pytest

BACKEND = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND))

def _build_fixtures(mod):
    """为单个测试构造函数级 fixture（对齐 pytest 默认作用域）。"""
    fixtures = {}
    svc_fn = getattr(mod, "svc", None)
    if svc_fn is not None:
        tmp = tempfile.mkdtemp()
        fixtures["tmp_path"] = pathlib.Path(tmp)
        fixtures["monkeypatch"] = _MonkeyPatch()
        gen = svc_fn(**{p: fixtures[p] for p in inspect.signature(svc_fn).parameters})
        fixtures["svc"] = next(gen)
        fixtures["_gen"] = gen
    return fixtures


passed = failed = 0
_live_gens = []  # 保活 fixture generator，避免 GC 提前触发 with 清理
for tfile in sorted((BACKEND / "app" / "tests").glob("test_*.py")):
    spec = importlib.util.spec_from_file_location(tfile.stem, tfile)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for name, fn in sorted(vars(mod).items()):
        if name.startswith("test_") and callable(fn):
            params = inspect.signature(fn).parameters
            fixtures = _build_fixtures(mod)
            _live_gens.append(fixtures.get("_gen"))
            try:
                fn(**{p: v for p, v in fixtures.items() if p in params})
                passed += 1
                print(f"PASS {tfile.stem}::{name}")
            except Exception:
                failed += 1
                print(f"FAIL {tfile.stem}::{name}")
                traceback.print_exc()

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
