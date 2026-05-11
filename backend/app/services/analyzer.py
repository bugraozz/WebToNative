from __future__ import annotations

import json
import re
from pathlib import Path

from ..models import DetectedSummary


def analyze_project(source_dir: Path) -> DetectedSummary:
    package_jsons = list(source_dir.rglob("package.json"))
    dependencies = set()

    for package_json in package_jsons:
        dependencies.update(_read_dependencies(package_json))

    frontend = _detect_frontend(dependencies, source_dir)
    backend = _detect_backend(dependencies, source_dir)
    database = _detect_database(dependencies, source_dir)
    styles = _detect_styles(dependencies, source_dir)
    payments = _detect_payments(dependencies, source_dir)
    docker = _detect_docker(source_dir)

    notes: list[str] = []
    if len(package_jsons) > 3:
        notes.append("Multiple package.json files detected.")
    if not frontend:
        notes.append("No frontend framework detected.")
    if not backend:
        notes.append("No backend framework detected.")

    return DetectedSummary(
        frontend=sorted(frontend),
        backend=sorted(backend),
        database=sorted(database),
        styles=sorted(styles),
        payments=sorted(payments),
        docker=sorted(docker),
        notes=notes,
    )


def _read_dependencies(package_json_path: Path) -> set[str]:
    try:
        data = json.loads(package_json_path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    deps: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        items = data.get(key, {})
        if isinstance(items, dict):
            deps.update(items.keys())
    return deps


def _detect_frontend(deps: set[str], source_dir: Path) -> list[str]:
    results: list[str] = []
    if "react" in deps:
        results.append("React")
    if "next" in deps or (source_dir / "next.config.js").exists():
        results.append("Next.js")
    if "vite" in deps:
        results.append("Vite")
    if "react-scripts" in deps:
        results.append("Create React App")
    if "react-router-dom" in deps:
        results.append("React Router")
    return _unique(results)


def _detect_backend(deps: set[str], source_dir: Path) -> list[str]:
    results: list[str] = []
    node_map = {
        "express": "Express",
        "fastify": "Fastify",
        "nestjs": "NestJS",
        "koa": "Koa",
    }
    for dep, label in node_map.items():
        if dep in deps:
            results.append(label)

    py_frameworks = _scan_python_frameworks(source_dir)
    results.extend(py_frameworks)

    return _unique(results)


def _scan_python_frameworks(source_dir: Path) -> list[str]:
    results: list[str] = []
    requirement_files = list(source_dir.rglob("requirements.txt"))
    for req in requirement_files:
        text = req.read_text(encoding="utf-8", errors="ignore")
        if "fastapi" in text:
            results.append("FastAPI")
        if "django" in text:
            results.append("Django")
        if "flask" in text:
            results.append("Flask")

    pyproject_files = list(source_dir.rglob("pyproject.toml"))
    for pyproject in pyproject_files:
        text = pyproject.read_text(encoding="utf-8", errors="ignore")
        if "fastapi" in text:
            results.append("FastAPI")
        if "django" in text:
            results.append("Django")
        if "flask" in text:
            results.append("Flask")

    return _unique(results)


def _detect_database(deps: set[str], source_dir: Path) -> list[str]:
    results: list[str] = []
    db_map = {
        "prisma": "Prisma",
        "mongoose": "MongoDB",
        "sequelize": "Sequelize",
        "typeorm": "TypeORM",
        "pg": "PostgreSQL",
        "mysql": "MySQL",
        "mysql2": "MySQL",
        "sqlite3": "SQLite",
        "sqlalchemy": "SQLAlchemy",
    }
    for dep, label in db_map.items():
        if dep in deps:
            results.append(label)

    if _detect_database_url(source_dir):
        results.append("Database URL")

    return _unique(results)


def _detect_database_url(source_dir: Path) -> bool:
    for env_file in source_dir.rglob(".env*"):
        if not env_file.is_file():
            continue
        text = env_file.read_text(encoding="utf-8", errors="ignore")
        if re.search(r"DATABASE_URL\s*=", text):
            return True
    return False


def _detect_styles(deps: set[str], source_dir: Path) -> list[str]:
    results: list[str] = []
    style_map = {
        "tailwindcss": "Tailwind CSS",
        "styled-components": "Styled Components",
        "sass": "Sass",
        "less": "Less",
        "@emotion/react": "Emotion",
    }
    for dep, label in style_map.items():
        if dep in deps:
            results.append(label)

    if (source_dir / "tailwind.config.js").exists() or (source_dir / "tailwind.config.ts").exists():
        results.append("Tailwind CSS")

    return _unique(results)


def _detect_docker(source_dir: Path) -> list[str]:
    results: list[str] = []
    for path in source_dir.rglob("Dockerfile"):
        if path.is_file():
            results.append("Dockerfile")
            break
    if (source_dir / "docker-compose.yml").exists() or (source_dir / "docker-compose.yaml").exists():
        results.append("docker-compose")
    return _unique(results)


def _detect_payments(deps: set[str], source_dir: Path) -> list[str]:
    results: list[str] = []

    for dep in deps:
        name = dep.lower()
        if "iyzipay" in name or "iyzico" in name:
            results.append("Iyzico")
        if "dodo" in name and "pay" in name:
            results.append("DodoPayments")

    keyword_map = {
        "iyzico": "Iyzico",
        "iyzipay": "Iyzico",
        "dodopay": "DodoPayments",
        "dodo payments": "DodoPayments",
        "dodo-payments": "DodoPayments",
    }

    results.extend(_scan_text_for_keywords(source_dir, keyword_map))
    return _unique(results)


def _scan_text_for_keywords(source_dir: Path, keyword_map: dict[str, str]) -> list[str]:
    results: set[str] = set()
    extensions = (".js", ".jsx", ".ts", ".tsx", ".env")
    files: list[Path] = []

    for ext in extensions:
        files.extend(source_dir.rglob(f"*{ext}"))

    for path in files[:300]:
        try:
            if path.stat().st_size > 1_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue

        for key, label in keyword_map.items():
            if key in text:
                results.add(label)

    return list(results)


def _unique(items: list[str]) -> list[str]:
    seen = set()
    unique_items = []
    for item in items:
        key = item.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_items.append(item)
    return unique_items
