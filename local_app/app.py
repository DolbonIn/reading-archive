#!/usr/bin/env python3
"""Local PDF 업로더 웹 앱.

Flask로 구현되어 있으며, 브라우저에서 PDF를 업로드하면 `scripts.process_pdf.run_pipeline`
을 호출해 AI 프레젠테이션과 manifest를 생성합니다.

실행 방법
=========

    export FLASK_APP=local_app.app:app
    export GOOGLE_API_KEY=...  # 필수
    flask run --reload

필요 패키지: `pip install flask google-genai pypdf pypdfium2 pillow`
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import List

import datetime as dt

from flask import Flask, jsonify, render_template, request, send_from_directory

from scripts.env_loader import load_env
from scripts.process_pdf import ROOT, DATA_FILE, PRESENTATIONS_DIR, run_pipeline

UPLOADS_DIR = ROOT / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

load_env()

TRUE_SET = {"1", "true", "on", "yes"}

AUTO_COMMIT = os.getenv("READING_ARCHIVE_AUTO_COMMIT", "false").lower() in TRUE_SET
AUTO_PUSH = os.getenv("READING_ARCHIVE_AUTO_PUSH", "false").lower() in TRUE_SET

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent / "static"),
)
app.secret_key = secrets.token_hex(16)


def parse_tags(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def to_bool(value: str | None) -> bool:
    return (value or "").lower() in TRUE_SET


@app.get("/")
def bookshelf():
    return send_from_directory(str(ROOT), "index.html")


@app.get("/upload")
def index():
    return render_template("index.html", today=dt.date.today().isoformat())


@app.post("/api/upload")
def upload():
    file = request.files.get("pdf")
    if not file or not file.filename:
        return jsonify({"ok": False, "message": "PDF 파일을 선택해주세요."}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"ok": False, "message": "PDF 파일만 업로드할 수 있습니다."}), 400

    safe_name = file.filename.replace(" ", "_")
    dest_path = UPLOADS_DIR / safe_name
    file.save(dest_path)

    dry_run = to_bool(request.form.get("dry_run"))
    commit_flag = to_bool(request.form.get("commit"))
    push_flag = to_bool(request.form.get("push"))

    commit = (commit_flag or AUTO_COMMIT) and not dry_run
    push = (push_flag or AUTO_PUSH) and not dry_run
    if push and not commit:
        commit = True

    progress_log: List[str] = []

    def capture_progress(message: str) -> None:
        progress_log.append(message)
        app.logger.info(message)

    try:
        result = run_pipeline(
            pdf_path=dest_path,
            title=request.form.get("title") or None,
            author=request.form.get("author") or None,
            date=request.form.get("date") or None,
            tags=parse_tags(request.form.get("tags")),
            description=request.form.get("description") or "",
            dry_run=dry_run,
            commit=commit,
            push=push,
            progress_callback=capture_progress,
        )
    except Exception as exc:  # Front-end에 메시지 전달
        return jsonify({"ok": False, "message": str(exc)}), 500

    if "progress" not in result or not result["progress"]:
        result["progress"] = progress_log
    else:
        result["progress"].extend(x for x in progress_log if x not in result["progress"])

    return jsonify({"ok": True, "data": result})


@app.get("/presentations/<path:filename>")
def serve_presentation(filename: str):
    return send_from_directory(str(PRESENTATIONS_DIR), filename)


@app.get("/assets/<path:filename>")
def serve_assets(filename: str):
    return send_from_directory(str(ROOT / "assets"), filename)


@app.get("/data/<path:filename>")
def serve_data(filename: str):
    return send_from_directory(str(DATA_FILE.parent), filename)


if __name__ == "__main__":
    app.run(debug=True)
