from .sandbox import Sandbox, is_protected, iter_files, run_pytest

MAX_READ_CHARS = 20_000

SCHEMAS = [
    {"type": "function", "function": {
        "name": "list_files",
        "description": "List every file in the repository (relative paths).",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "read_file",
        "description": "Read a text file from the repository.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path relative to the repository root"}},
            "required": ["path"]},
    }},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "Overwrite (or create) a source file with the full new content. "
                       "Test files and test config cannot be written.",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "description": "Path relative to the repository root"},
            "content": {"type": "string", "description": "The complete new file content"}},
            "required": ["path", "content"]},
    }},
    {"type": "function", "function": {
        "name": "run_tests",
        "description": "Run the test suite with pytest and return the (trimmed) output.",
        "parameters": {"type": "object", "properties": {}},
    }},
]


class Toolbox:
    def __init__(self, sandbox: Sandbox, test_timeout: int = 30):
        self.sb = sandbox
        self.test_timeout = test_timeout

    def list_files(self) -> str:
        return "\n".join(p.as_posix() for p in iter_files(self.sb.root)) or "(empty)"

    def read_file(self, path: str) -> str:
        p = self.sb.resolve(path)
        if not p.is_file():
            return f"ERROR: no such file: {path}"
        text = p.read_text(errors="replace")
        return text if len(text) <= MAX_READ_CHARS else text[:MAX_READ_CHARS] + "\n...[truncated]"

    def write_file(self, path: str, content: str) -> str:
        p = self.sb.resolve(path)
        rel = self.sb.rel(p)
        if is_protected(rel):
            return f"REFUSED: {rel} is a test or test-config file. Fix the source code, not the tests."
        if p.is_dir():
            return f"ERROR: {rel} is a directory"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return f"wrote {rel} ({len(content)} chars)"

    def run_tests(self) -> str:
        passed, out = run_pytest(self.sb.root, timeout=self.test_timeout)
        return ("ALL TESTS PASSED\n" if passed else "TESTS FAILED\n") + out

    def call(self, name: str, args: dict) -> str:
        try:
            if name == "list_files":
                return self.list_files()
            if name == "read_file":
                return self.read_file(args.get("path", ""))
            if name == "write_file":
                return self.write_file(args.get("path", ""), args.get("content", ""))
            if name == "run_tests":
                return self.run_tests()
            return f"ERROR: unknown tool {name!r}"
        except PermissionError as e:
            return f"REFUSED: {e}"
        except (OSError, UnicodeError, TypeError) as e:
            return f"ERROR: {type(e).__name__}: {e}"
