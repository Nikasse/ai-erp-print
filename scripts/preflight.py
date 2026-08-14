#!/usr/bin/env python3
"""Preflight для ai-erp-print — один прогін усіх обов'язкових перевірок
перед Pull Request і перед deploy на Render.

Запуск (з будь-якої директорії — шляхи скрипт визначає сам):

    python scripts/preflight.py

П'ять перевірок по порядку: Python compile → React build → Docker build →
Secret scan → Config check. Скрипт зупиняється на першій помилці і
повертає ненульовий exit code, тож його можна ставити кроком у CI без
додаткових обгорток.

Один і той самий набір перевірок локально і в GitHub Actions: у коді немає
жодної гілки на CI-змінні (CI, GITHUB_ACTIONS тощо). Єдина умовність —
наявність docker у середовищі, див. check_docker_build().

Тільки стандартна бібліотека — нових залежностей не додає.
"""

import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DOCKER_IMAGE_TAG = "ai-erp-print-preflight"

# Файли, без яких deploy на Render зламається (див. AGENTS.md, розділ 2).
REQUIRED_FILES = (
    "Dockerfile.render",
    "app/render_app.py",
    "app/api.py",
    "requirements.txt",
    "admin/package.json",
)

# Маркер для свідомого виключення рядка з secret scan. Такий самий, як у
# detect-secrets (.secrets.baseline уже є в проєкті) — щоб не плодити два
# різних синтаксиси для однієї задачі.
ALLOW_MARKER = "pragma: allowlist secret"

# Шаблони справжніх секретів. Навмисно вузькі: широкий "sk-ant-" ловив би
# документацію (docs/deploy.md згадує префікс ключа в тексті), тому
# вимагається повна довжина токена.
SECRET_PATTERNS = (
    ("ключ Anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{24,}")),
    ("токен Telegram-бота", re.compile(r"\b\d{8,12}:[A-Za-z0-9_\-]{30,}")),
)

# Connection string з паролем. Пароль виноситься в групу, щоб відрізнити
# реальний від задокументованого плейсхолдера (postgresql://user:password@host).
POSTGRES_URL_RE = re.compile(r"postgres(?:ql)?(?:\+[a-z0-9]+)?://[^\s:/@]{1,64}:([^\s@/'\"]{1,128})@")

# Значення-заглушки: у документації й .env.example вони законні.
PLACEHOLDER_RE = re.compile(
    r"^(?:"
    r"[*x.]+|<[^>]*>|\{+[^}]*\}+|"
    r"pass|passw|passwd|password|secret|token|key|apikey|api_key|"
    r"user|username|host|hostname|db|dbname|database|"
    r"changeme|placeholder|example|test|dummy|none|null|todo"
    r")$",
    re.IGNORECASE,
)
PLACEHOLDER_SUBSTRINGS = ("your_", "your-", "_here", "-here", "example", "<", "xxx", "...")

# Імена змінних, значення яких вважаємо секретом і шукаємо в git-файлах.
# Фільтр за іменем потрібен, щоб нешкідливий конфіг з .env (APP_ENV, MODEL)
# не давав хибних збігів із кодом.
SECRET_KEY_RE = re.compile(r"TOKEN|KEY|SECRET|PASSWORD|PASSWD|CREDENTIAL|DSN|URL", re.IGNORECASE)

MAX_FINDINGS_SHOWN = 20
MAX_LOG_LINES = 30


class CheckFailed(Exception):
    """Перевірка не пройшла. Текст — готове до друку пояснення."""


def _run(cmd: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    """Запускає команду без shell (cross-platform) і повертає результат."""
    try:
        return subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            errors="replace",
        )
    except FileNotFoundError:
        raise CheckFailed(f"не знайдено виконуваний файл: {cmd[0]}")


def _tail(proc: subprocess.CompletedProcess, limit: int = MAX_LOG_LINES) -> str:
    """Останні рядки виводу — щоб показати причину, а не весь build log."""
    text = (proc.stdout or "") + (proc.stderr or "")
    lines = [line for line in text.splitlines() if line.strip()]
    return "\n".join(lines[-limit:]) or "(без виводу)"


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


def _read_text(path: Path) -> str | None:
    """Текст файлу або None, якщо файл бінарний / не читається."""
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _is_placeholder(value: str) -> bool:
    value = value.strip()
    if not value:
        return True
    if PLACEHOLDER_RE.match(value):
        return True
    lowered = value.lower()
    return any(part in lowered for part in PLACEHOLDER_SUBSTRINGS)


def _findings_in_line(line: str) -> list[str]:
    """Список причин, чому рядок схожий на секрет. Самі значення не повертає."""
    if ALLOW_MARKER in line:
        return []

    reasons = []
    for reason, pattern in SECRET_PATTERNS:
        if pattern.search(line):
            reasons.append(reason)

    for match in POSTGRES_URL_RE.finditer(line):
        if not _is_placeholder(match.group(1)):
            reasons.append("connection string з паролем")
            break

    return reasons


def _parse_env_file(path: Path) -> list[tuple[str, str]]:
    """Пари (ключ, значення) з .env-подібного файлу. Значення не логуються."""
    text = _read_text(path)
    if text is None:
        return []

    pairs = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        pairs.append((key.strip(), value.strip().strip('"').strip("'")))
    return pairs


def _real_env_values() -> list[tuple[str, str]]:
    """Реальні значення з локального .env: (ключ, значення).

    У CI .env немає — тоді список порожній і перевірка просто не має що
    порівнювати. Це не гілка «якщо CI», а наслідок відсутності файлу.
    """
    env_path = ROOT / ".env"
    if not env_path.is_file():
        return []

    values = []
    for key, value in _parse_env_file(env_path):
        if not SECRET_KEY_RE.search(key):
            continue
        if len(value) < 12 or _is_placeholder(value):
            continue
        values.append((key, value))
    return values


def _tracked_files() -> list[str]:
    proc = _run(["git", "ls-files", "-z"])
    if proc.returncode != 0:
        raise CheckFailed(f"git ls-files впав (exit {proc.returncode}):\n{_tail(proc)}")
    return [path for path in proc.stdout.split("\0") if path]


# ---------------------------------------------------------------------------
# 1/5 — Python compile
# ---------------------------------------------------------------------------
def check_python_compile() -> tuple[str, str | None]:
    """Компілює всі .py у app/ і scripts/ — ловить синтаксичні помилки.

    Байткод пишеться в тимчасову директорію (cfile), щоб перевірка не
    залишала __pycache__ у репозиторії.
    """
    files: list[Path] = []
    for folder in ("app", "scripts"):
        directory = ROOT / folder
        if not directory.is_dir():
            continue
        files.extend(
            path
            for path in sorted(directory.rglob("*.py"))
            if "__pycache__" not in path.parts
        )

    if not files:
        raise CheckFailed("не знайдено жодного .py у app/ і scripts/")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        for index, path in enumerate(files):
            try:
                py_compile.compile(
                    str(path),
                    cfile=str(tmp_dir / f"{index}.pyc"),
                    doraise=True,
                )
            except py_compile.PyCompileError as exc:
                raise CheckFailed(str(exc).strip())

    return "OK", None


# ---------------------------------------------------------------------------
# 2/5 — React build
# ---------------------------------------------------------------------------
def check_react_build() -> tuple[str, str | None]:
    """npm ci + npm run build в admin/.

    Відсутній npm — це FAILED, а не SKIPPED: зібраний фронтенд входить у
    production-образ (Dockerfile.render), тому «не перевірили» тут означало б
    відправити на Render код, який ніхто не компілював.
    """
    admin = ROOT / "admin"
    if not (admin / "package.json").is_file():
        raise CheckFailed("немає admin/package.json — перевіряти нічого")

    # shutil.which, а не рядок "npm": на Windows це npm.cmd, і subprocess
    # без shell знайде його лише за повним шляхом.
    npm = shutil.which("npm")
    if npm is None:
        raise CheckFailed(
            "npm не знайдено в PATH.\n"
            "React build обов'язковий (фронтенд іде в production-образ).\n"
            "Постав Node.js 20+ (та сама версія, що в Dockerfile.render) і повтори."
        )

    for args in (["ci"], ["run", "build"]):
        proc = _run([npm, *args], cwd=admin)
        if proc.returncode != 0:
            raise CheckFailed(
                f"npm {' '.join(args)} впав (exit {proc.returncode}):\n{_tail(proc)}"
            )

    if not (admin / "dist" / "index.html").is_file():
        raise CheckFailed("npm run build пройшов, але admin/dist/index.html не з'явився")

    return "OK", None


# ---------------------------------------------------------------------------
# 3/5 — Docker build
# ---------------------------------------------------------------------------
def check_docker_build() -> tuple[str, str | None]:
    """Збирає production-образ з Dockerfile.render.

    Саме Dockerfile.render, а не Dockerfile: другий збирає образ
    Telegram-бота і до deploy на Render стосунку не має (AGENTS.md, розділ 2).

    Чому SKIPPED, а не FAILED, коли docker недоступний: у GitHub Actions
    docker є завжди, і там перевірка реально виконується. Але локально його
    може не бути взагалі або Docker Desktop може бути закритий — блокувати
    через це роботу над кодом чи документацією немає сенсу. Образ усе одно
    буде зібраний у CI і на самому Render, тож SKIPPED тут нічого не
    приховує: перевірка не втрачається, вона лише відкладається.
    """
    docker = shutil.which("docker")
    if docker is None:
        return "SKIPPED", "docker not available"

    if _run([docker, "info"]).returncode != 0:
        return "SKIPPED", "docker daemon not running"

    if not (ROOT / "Dockerfile.render").is_file():
        raise CheckFailed("немає Dockerfile.render")

    proc = _run([docker, "build", "-f", "Dockerfile.render", "-t", DOCKER_IMAGE_TAG, "."])
    if proc.returncode != 0:
        raise CheckFailed(
            f"docker build -f Dockerfile.render впав (exit {proc.returncode}):\n{_tail(proc)}"
        )

    return "OK", None


# ---------------------------------------------------------------------------
# 4/5 — Secret scan
# ---------------------------------------------------------------------------
def check_secret_scan() -> tuple[str, str | None]:
    """Шукає секрети у файлах під git.

    Область — тільки git ls-files: по всьому диску скан зачепив би сам .env,
    node_modules і admin/dist, і завалювався б на файлах, яких у репозиторії
    немає.

    Знайдене значення НЕ друкується — у вивід іде лише файл, номер рядка і
    тип знахідки.
    """
    findings: list[str] = []
    env_values = _real_env_values()

    for rel_path in _tracked_files():
        name = rel_path.rsplit("/", 1)[-1]
        if name == ".env" or (name.startswith(".env.") and name != ".env.example"):
            findings.append(f"{rel_path} — файл із секретами не має бути під git")

        path = ROOT / rel_path
        if not path.is_file():
            continue

        text = _read_text(path)
        if text is None:
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            for reason in _findings_in_line(line):
                findings.append(f"{rel_path}:{lineno} — {reason}")

            if ALLOW_MARKER in line:
                continue
            for key, value in env_values:
                if value in line:
                    findings.append(f"{rel_path}:{lineno} — значення {key} з .env")

    if findings:
        shown = findings[:MAX_FINDINGS_SHOWN]
        message = "знайдено потенційні секрети:\n" + "\n".join(shown)
        if len(findings) > len(shown):
            message += f"\n... і ще {len(findings) - len(shown)}"
        message += (
            "\n\nПрибрати значення з файлу, перевипустити секрет, "
            f"або (якщо це справді не секрет) додати в рядок '{ALLOW_MARKER}'."
        )
        raise CheckFailed(message)

    return "OK", None


# ---------------------------------------------------------------------------
# 5/5 — Config check
# ---------------------------------------------------------------------------
def check_config() -> tuple[str, str | None]:
    """Перевіряє, що конфігурація проєкту на місці, а .env — поза git."""
    problems: list[str] = []

    # Успіх тут — це НЕВДАЧА команди: --error-unmatch падає, коли файл не
    # відстежується. Нульовий exit code означав би, що .env потрапив у git.
    if _run(["git", "ls-files", "--error-unmatch", ".env"]).returncode == 0:
        problems.append(".env відстежується git — прибрати з індексу: git rm --cached .env")

    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        problems.append("немає .gitignore")
    else:
        patterns = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
        if not patterns & {".env", "/.env", ".env*", "*.env"}:
            problems.append(".env немає у .gitignore")

    for rel_path in REQUIRED_FILES:
        if not (ROOT / rel_path).is_file():
            problems.append(f"немає критичного файлу: {rel_path}")

    example = ROOT / ".env.example"
    if not example.is_file():
        problems.append("немає .env.example")
    else:
        env_values = {value: key for key, value in _real_env_values()}
        for key, value in _parse_env_file(example):
            if _findings_in_line(f"{key}={value}"):
                problems.append(f".env.example: у {key} схоже на реальний секрет")
            elif value in env_values and not _is_placeholder(value):
                problems.append(f".env.example: значення {key} збігається з реальним із .env")

    if problems:
        raise CheckFailed("\n".join(problems))

    return "OK", None


CHECKS = (
    ("Python compile", check_python_compile),
    ("React build", check_react_build),
    ("Docker build", check_docker_build),
    ("Secret scan", check_secret_scan),
    ("Config check", check_config),
)


def main() -> int:
    total = len(CHECKS)

    for index, (name, check) in enumerate(CHECKS, start=1):
        print(f"[{index}/{total}] {name} ... ", end="", flush=True)
        try:
            status, note = check()
        except CheckFailed as exc:
            print("FAILED", flush=True)
            print()
            print(_indent(str(exc)))
            print()
            print("PREFLIGHT FAILED", flush=True)
            return 1

        print(f"{status} ({note})" if note else status, flush=True)

    print("PREFLIGHT PASSED", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
