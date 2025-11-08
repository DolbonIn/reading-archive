#!/usr/bin/env python3
"""Batch process PDFs into Reading Archive HTML presentations.

`uploads/` 디렉터리 안의 PDF를 순회하며 `scripts.process_pdf.run_pipeline`
을 호출해 책장에 필요한 HTML 슬라이드와 manifest 항목을 생성합니다.

파일명 규칙
-----------
    제목 -- 저자 -- 그 외 메타데이터.pdf

첫 번째 ` -- ` 앞까지를 제목으로, 첫 번째와 두 번째 ` -- ` 사이를 저자로
인식합니다. 나머지 구간은 무시됩니다. 제목이나 저자가 비어 있으면 자동으로
보정하며, 실패한 변환은 최대 2회까지 재시도합니다.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fnmatch
import json
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if __package__ in (None, ""):
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.append(str(SCRIPT_DIR))
    from process_pdf import (  # type: ignore
        COVERS_DIR,
        DATA_FILE,
        DEFAULT_COVER,
        ROOT,
        extract_cover,
        run_pipeline,
        slugify,
        update_manifest,
    )
else:  # pragma: no cover - module import path
    from .process_pdf import (  # type: ignore
        COVERS_DIR,
        DATA_FILE,
        DEFAULT_COVER,
        ROOT,
        extract_cover,
        run_pipeline,
        slugify,
        update_manifest,
    )

DELIMITER = " -- "
MAX_PDF_SIZE = 80 * 1024 * 1024  # 80MB limit


def normalize_segment(text: str) -> str:
    cleaned = text.replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" _-\t")


def parse_title_author(stem: str) -> Tuple[str, Optional[str]]:
    if DELIMITER not in stem:
        title = normalize_segment(stem) or "Untitled"
        return title, None

    first, remainder = stem.split(DELIMITER, 1)
    title = normalize_segment(first) or "Untitled"

    if not remainder:
        return title, None

    if DELIMITER in remainder:
        author_segment, _ = remainder.split(DELIMITER, 1)
    else:
        author_segment = remainder
    author = normalize_segment(author_segment)
    return title, author or None


def load_existing_slugs() -> Dict[str, dict]:
    if not DATA_FILE.exists():
        return {}
    try:
        records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(records, list):
        return {}
    return {entry.get("slug", ""): entry for entry in records if "slug" in entry}


def should_skip(slug: str, existing: Dict[str, dict], force: bool) -> bool:
    if force:
        return False
    return slug in existing


def persist_entry(result: dict, existing: Dict[str, dict]) -> None:
    """Ensure the manifest reflects the latest pipeline result."""
    entry = {
        key: result.get(key)
        for key in ("slug", "title", "author", "date", "tags", "description", "presentation", "cover")
        if key in result
    }
    if not entry.get("slug"):
        return
    update_manifest(entry)
    existing[entry["slug"]] = entry


def handle_large_pdf(
    *,
    pdf_path: Path,
    title: str,
    author: Optional[str],
    slug: str,
    existing: Dict[str, dict],
) -> dict:
    """Create manifest + cover entry without running Gemini for oversized PDFs."""
    print(f"[스킵] 80MB 초과: {pdf_path.name} (표지 + manifest만 갱신)")
    presentation_rel = f"presentations/{slug}.html"
    cover_path = COVERS_DIR / f"{slug}.jpg"
    cover_rel = DEFAULT_COVER

    try:
        extract_cover(pdf_path, cover_path)
        cover_rel = cover_path.relative_to(ROOT).as_posix()
    except Exception as exc:  # pragma: no cover - environment-specific
        print(f"    [경고] 표지 추출 실패, 기본 이미지 사용: {exc}")
        cover_rel = DEFAULT_COVER

    entry = {
        "slug": slug,
        "title": title,
        "author": author,
        "date": dt.date.today().isoformat(),
        "tags": [],
        "description": "",
        "presentation": presentation_rel,
        "cover": cover_rel,
    }
    update_manifest(entry)
    existing[slug] = entry
    return entry


def run_with_retries(
    *,
    pdf_path: Path,
    title: str,
    author: Optional[str],
    retries: int,
    dry_run: bool,
    commit: bool,
    push: bool,
) -> Tuple[bool, Optional[Exception], int, Optional[dict]]:
    attempts = 0
    last_error: Optional[Exception] = None

    while attempts <= retries:
        attempts += 1
        try:
            progress_lines: List[str] = []

            def progress_callback(message: str) -> None:
                progress_lines.append(message)
                print(f"    {message}")

            result = run_pipeline(
                pdf_path=pdf_path,
                title=title,
                author=author,
                dry_run=dry_run,
                commit=commit,
                push=push,
                progress_callback=progress_callback,
            )
            print(f"    [완료] {result.get('presentation')}")
            return True, None, attempts, result
        except Exception as exc:  # pragma: no cover - runtime dependency
            last_error = exc
            print(f"    [경고] 시도 {attempts}회 실패: {exc}")
            if attempts > retries:
                break
            time.sleep(1.0)
    return False, last_error, attempts, None


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uploads",
        type=Path,
        default=ROOT / "uploads",
        help="PDF를 찾을 디렉터리 (기본: %(default)s)",
    )
    parser.add_argument(
        "--file-list",
        type=Path,
        help="업로드 목록 텍스트 파일 (한 줄당 상대/절대 경로)",
    )
    parser.add_argument(
        "--pattern",
        default="*.pdf",
        help="대상 파일 글로브 패턴 (기본: %(default)s)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=2,
        help="실패 시 재시도 횟수 (기본: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="이미 manifest에 존재해도 다시 생성합니다.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gemini 호출 없이 파일만 준비합니다 (--dry-run 전달).",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="각 항목 처리 후 git commit 수행",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="commit 이후 git push 수행 (commit 옵션과 함께 의미 있음)",
    )
    return parser.parse_args(argv)


def collect_pdf_files(directory: Path, pattern: str) -> List[Path]:
    """Collect files matching pattern while tolerating I/O errors."""
    matches: List[Path] = []
    try:
        iterator = directory.iterdir()
    except OSError as exc:
        print(f"[경고] 디렉터리 탐색 실패: {directory} ({exc})")
        return matches

    try:
        for entry in iterator:
            try:
                if not entry.is_file():
                    continue
            except OSError as exc:
                print(f"  [무시] 항목 확인 실패: {entry.name} ({exc})")
                continue

            try:
                if fnmatch.fnmatch(entry.name, pattern):
                    matches.append(entry)
            except re.error as exc:
                print(f"  [무시] 패턴 비교 실패: {entry.name} ({exc})")
    except OSError as exc:
        print(f"  [무시] 일부 항목 열람 실패: {exc}")

    if matches:
        return sorted(matches)

    shell_matches = shell_glob_scan(directory, pattern)
    if shell_matches:
        return sorted(shell_matches)

    windows_matches = windows_glob_scan(directory, pattern)
    if windows_matches:
        write_auto_file_list(directory, windows_matches)
        return sorted(windows_matches)

    return fallback_find(directory, pattern)


def shell_glob_scan(directory: Path, pattern: str) -> List[Path]:
    """Use bash globbing (with nocase support) to enumerate files."""
    if not directory.exists():
        return []

    quoted_dir = shlex.quote(str(directory))
    quoted_pattern = shlex.quote(pattern)
    command = (
        f"cd {quoted_dir} && "
        "shopt -s nullglob nocaseglob; "
        f"pattern={quoted_pattern}; "
        "for f in $pattern; do printf '%s\\0' \"$PWD/$f\"; done"
    )
    result = subprocess.run(
        ["bash", "-lc", command],
        capture_output=True,
        text=False,
        check=False,
    )
    if result.returncode not in (0, 1):
        if result.stderr:
            msg = result.stderr.decode("utf-8", "ignore").strip()
            if msg:
                print(f"[무시] shell glob 경고: {msg}")
        return []

    entries = [
        Path(path.decode("utf-8", "ignore"))
        for path in result.stdout.split(b"\0")
        if path
    ]
    return entries


def fallback_find(directory: Path, pattern: str) -> List[Path]:
    """Use `find` as the final fallback when everything else fails."""
    if not directory.exists():
        return []

    result = subprocess.run(
        [
            "find",
            str(directory),
            "-maxdepth",
            "1",
            "-type",
            "f",
            "-name",
            pattern,
            "-print0",
        ],
        capture_output=True,
        text=False,
        check=False,
    )
    if result.stderr:
        message = result.stderr.decode("utf-8", "ignore").strip()
        if message:
            print(f"[무시] find 경고: {message}")

    entries = [
        Path(path.decode("utf-8", "ignore"))
        for path in result.stdout.split(b"\0")
        if path
    ]
    return sorted(entries)


def windows_glob_scan(directory: Path, pattern: str) -> List[Path]:
    """Use cmd.exe to gather file list when available."""
    win_dir = to_windows_path(directory)
    if not win_dir:
        return []

    pattern_path = str(Path(win_dir) / pattern)
    command = f'for %f in ("{pattern_path}") do @echo %~ff'
    try:
        result = subprocess.run(
            ["cmd.exe", "/c", command],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(f"[무시] Windows dir 호출 실패: {exc}")
        return []

    if result.returncode not in (0, 1):
        message = (result.stderr or "").strip()
        if message:
            print(f"[무시] Windows dir 경고: {message}")
        return []

    paths: List[Path] = []
    for line in result.stdout.splitlines():
        clean = line.strip()
        if not clean:
            continue
        wsl_path = to_wsl_path(clean)
        if wsl_path:
            paths.append(wsl_path)
    return paths


def to_windows_path(path: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["wslpath", "-w", str(path)],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def to_wsl_path(path: str) -> Optional[Path]:
    try:
        result = subprocess.run(
            ["wslpath", "-u", path],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (OSError, subprocess.CalledProcessError):
        if len(path) >= 2 and path[1] == ":":
            drive = path[0].lower()
            remainder = path[2:].replace("\\", "/")
            return Path(f"/mnt/{drive}/{remainder}")
        return None


def write_auto_file_list(directory: Path, paths: List[Path]) -> None:
    auto_file = directory / ".auto_file_list.txt"
    try:
        relative_lines = []
        for path in paths:
            try:
                relative_lines.append(str(path.relative_to(directory)))
            except ValueError:
                relative_lines.append(str(path))
        auto_file.write_text("\n".join(relative_lines), encoding="utf-8")
        print(f"[안내] Windows 목록을 '{auto_file}'에 저장했습니다.")
    except OSError as exc:
        print(f"[무시] file-list 저장 실패: {exc}")


def load_list_file(file_path: Path, uploads_dir: Path) -> List[Path]:
    entries: List[Path] = []
    try:
        raw_text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"[경고] file-list를 읽을 수 없습니다 ({exc}). 무시합니다.")
        return entries
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        candidate = Path(stripped)
        if not candidate.is_absolute():
            candidate = uploads_dir / candidate
        entries.append(candidate)
    return entries


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    uploads_dir: Path = args.uploads
    list_file: Optional[Path] = args.file_list
    pattern: str = args.pattern
    retries: int = max(0, args.retries)
    force: bool = args.force
    dry_run: bool = args.dry_run
    commit: bool = args.commit
    push: bool = args.push

    if push and not commit:
        print("[안내] --push 는 --commit 과 함께 사용할 때만 동작합니다.")

    if not uploads_dir.exists():
        print(f"[경고] 업로드 디렉터리를 찾지 못했습니다: {uploads_dir}")
        return 0

    pdf_files: List[Path]
    if list_file:
        pdf_files = load_list_file(list_file, uploads_dir)
        if not pdf_files:
            print(f"[경고] file-list에서 유효한 경로를 찾지 못했습니다: {list_file}")
    else:
        try:
            pdf_files = sorted(uploads_dir.glob(pattern))
        except OSError:
            pdf_files = collect_pdf_files(uploads_dir, pattern)
        else:
            if not pdf_files:
                pdf_files = collect_pdf_files(uploads_dir, pattern)
    if not pdf_files:
        print(f"[안내] 변환할 PDF가 없습니다. (패턴: {pattern})")
        return 0

    existing = load_existing_slugs()
    successes: List[Path] = []
    failures: List[Tuple[Path, Optional[Exception], int]] = []

    print(f"[시작] 총 {len(pdf_files)}개 PDF 처리 예정")

    for pdf_path in pdf_files:
        title, author = parse_title_author(pdf_path.stem)
        slug_candidate = slugify(title if not author else f"{title} {author}")

        if should_skip(slug_candidate, existing, force):
            print(f"[건너뜀] 이미 존재: {pdf_path.name} (slug: {slug_candidate})")
            continue

        label = f"{title} / {author}" if author else title
        print(f"[진행] {pdf_path.name} → {label}")

        try:
            size_bytes = pdf_path.stat().st_size
        except OSError as exc:
            print(f"  [경고] 파일 크기를 확인할 수 없습니다: {exc}")
            size_bytes = 0

        if size_bytes > MAX_PDF_SIZE:
            entry = handle_large_pdf(
                pdf_path=pdf_path,
                title=title,
                author=author,
                slug=slug_candidate,
                existing=existing,
            )
            successes.append(pdf_path)
            continue

        ok, error, attempts, result = run_with_retries(
            pdf_path=pdf_path,
            title=title,
            author=author,
            retries=retries,
            dry_run=dry_run,
            commit=commit,
            push=push,
        )

        if ok:
            successes.append(pdf_path)
            if result:
                persist_entry(result, existing)
        else:
            failures.append((pdf_path, error, attempts))

    print(f"[요약] 성공 {len(successes)}건 / 실패 {len(failures)}건")
    if failures:
        for pdf_path, error, attempts in failures:
            print(f"  - {pdf_path.name} (시도 {attempts}회 실패): {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
