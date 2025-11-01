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
import fnmatch
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if __package__ in (None, ""):
    SCRIPT_DIR = Path(__file__).resolve().parent
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.append(str(SCRIPT_DIR))
    from process_pdf import DATA_FILE, ROOT, run_pipeline, slugify  # type: ignore
else:  # pragma: no cover - module import path
    from .process_pdf import DATA_FILE, ROOT, run_pipeline, slugify  # type: ignore

DELIMITER = " -- "


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


def run_with_retries(
    *,
    pdf_path: Path,
    title: str,
    author: Optional[str],
    retries: int,
    dry_run: bool,
    commit: bool,
    push: bool,
) -> Tuple[bool, Optional[Exception], int]:
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
            return True, None, attempts
        except Exception as exc:  # pragma: no cover - runtime dependency
            last_error = exc
            print(f"    [경고] 시도 {attempts}회 실패: {exc}")
            if attempts > retries:
                break
            time.sleep(1.0)
    return False, last_error, attempts


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--uploads",
        type=Path,
        default=ROOT / "uploads",
        help="PDF를 찾을 디렉터리 (기본: %(default)s)",
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

    return fallback_shell_glob(directory, pattern)


def fallback_shell_glob(directory: Path, pattern: str) -> List[Path]:
    """Use `find` as a last resort to work around DrvFs I/O errors."""
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


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    uploads_dir: Path = args.uploads
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

        ok, error, attempts = run_with_retries(
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
