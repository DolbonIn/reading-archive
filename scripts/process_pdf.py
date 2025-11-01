#!/usr/bin/env python3
"""Reading Archive automation pipeline.

기능 요약
---------
1. PDF 첫 페이지에서 커버 이미지를 추출해 600×800 JPEG으로 저장합니다.
2. Google Gemini 2.5 Pro를 호출해 40장 이상의 Tailwind HTML 프레젠테이션을 생성합니다.
3. 결과물을 `presentations/<slug>.html`, `assets/covers/<slug>.jpg`로 저장하고
   `data/books.json` manifest를 갱신합니다.
4. 옵션에 따라 git add/commit/push를 자동으로 수행합니다.

설치 / 준비
-----------
- Python 3.10+
- `pip install google-genai pypdf pypdfium2 pillow`
- 환경 변수 `GOOGLE_API_KEY` 설정 (API 키를 코드에 하드코딩하지 마세요)

사용 예시
---------
    python scripts/process_pdf.py path/to/book.pdf \
        --title "Deep Work" \
        --author "Cal Newport" \
        --tags "생산성, 집중" \
        --description "깊은 몰입으로 성과를 높이는 전략 정리" \
        --commit

"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parent))
    from env_loader import load_env  # type: ignore  # pylint: disable=import-error
else:  # pragma: no cover
    from .env_loader import load_env  # type: ignore

load_env()

try:
    from google import genai
    from google.genai import types as genai_types
except ImportError:  # pragma: no cover - handled via runtime check
    genai = None
    genai_types = None

ROOT = Path(__file__).resolve().parent.parent
PRESENTATIONS_DIR = ROOT / "presentations"
COVERS_DIR = ROOT / "assets" / "covers"
DATA_FILE = ROOT / "data" / "books.json"
DEFAULT_COVER = "assets/covers/default.svg"

SYSTEM_PROMPT = """**Libraries:**

You are an AI Web Developer. Your task is to generate a single, self-contained HTML document for rendering in an iframe, based on user instructions and data.

**Visual aesthetic:**
    * Aesthetics are crucial. Make the page look amazing, especially on mobile.
    * Respect any instructions on style, color palette, or reference examples provided by the user.
**Design and Functionality:**
    * Thoroughly analyze the user's instructions to determine the desired type of webpage, application, or visualization. What are the key features, layouts, or functionality?
    * Analyze any provided data to identify the most compelling layout or visualization of it. For example, if the user requests a visualization, select an appropriate chart type (bar, line, pie, scatter, etc.) to create the most insightful and visually compelling representation. Or if user instructions say `use a carousel format`, you should consider how to break the content and any media into different card components to display within the carousel.
    * If requirements are underspecified, make reasonable assumptions to complete the design and functionality. Your goal is to deliver a working product with no placeholder content.
    * Ensure the generated code is valid and functional. Return only the code, and open the HTML codeblock with the literal string \"```html\".
    * The output must be a complete and valid HTML document with no placeholder content for the developer to fill in.

**Libraries:**
  Unless otherwise specified, use:
    * Tailwind for CSS

**Template**
```html
<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"UTF-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
  <title>Presentation Template</title>
  <script src=\"https://cdn.tailwindcss.com\"></script>
  <link rel=\"stylesheet\" href=\"https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css\">
  <link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">
  <link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>
  <link href=\"https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700;900&display=swap\" rel=\"stylesheet\">
  <style>
    body {
      font-family: 'Noto Sans KR', sans-serif;
      background-color: #FCFCFC;
      background-image: linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(0,0,0,0.03) 1px, transparent 1px);
      background-size: 30px 30px;
    }
    .slide {
      display: none;
      min-height: 85vh;
      align-items: center;
      justify-content: center;
    }
    .slide.active {
      display: flex;
    }
    .slide-container {
      width: 100%;
      max-width: 1100px;
      padding: 50px 60px;
      display: flex;
      flex-direction: column;
      justify-content: center;
    }
    .slide-part-title {
      font-size: 1.2rem;
      font-weight: 700;
      color: #555;
      margin-bottom: 8px;
    }
    .slide-title {
      font-size: 2.8rem;
      font-weight: 900;
      color: #111;
      margin-bottom: 25px;
      line-height: 1.3;
    }
    .slide-subtitle {
      font-size: 1.4rem;
      font-weight: 500;
      color: #444;
      margin-bottom: 35px;
      line-height: 1.6;
    }
    .slide-content {
      font-size: 1.1rem;
      line-height: 1.9;
      color: #333;
    }
    .highlight {
      background-color: #FFDD00;
      padding: 0 0.25em;
    }
    .btn {
      padding: 12px 28px;
      border-radius: 8px;
      font-weight: 700;
      transition: all 0.2s ease;
      cursor: pointer;
      border: none;
    }
    .btn-primary {
      background-color: #111;
      color: white;
    }
    .btn-primary:hover {
      background-color: #333;
    }
    .btn-secondary {
      background-color: #F0F0F0;
      color: #333;
    }
    .btn-secondary:hover {
      background-color: #E0E0E0;
    }
    .progress-bar-container {
      position: fixed;
      bottom: 0;
      left: 0;
      width: 100%;
      padding: 20px 40px;
      background-color: rgba(255, 255, 255, 0.95);
      backdrop-filter: blur(8px);
      border-top: 1px solid #eee;
      z-index: 10;
    }
    .progress-bar {
      width: 100%;
      background-color: #eee;
      border-radius: 9999px;
      height: 8px;
      margin-bottom: 15px;
    }
    .progress {
      background-color: #111;
      height: 100%;
      border-radius: 9999px;
      transition: width 0.3s ease;
    }
  </style>
</head>
<body class=\"flex flex-col items-center justify-center min-h-screen p-4 md:p-8 pb-32\">

  <div class=\"w-full\">
    <!-- Slides Container: Add your slides here -->
    <div id=\"slides-container\">

      <!-- Slide 1: Title -->
      <div class=\"slide active\">
        <div class=\"slide-container text-center\">
          <div class=\"text-7xl mb-8\">:bulb:</div>
          <h1 class=\"text-5xl md:text-6xl font-black text-gray-900 mb-4\">[Your Project Title]</h1>
          <p class=\"text-xl md:text-2xl text-gray-700\">[Your Subtitle] <span class=\"highlight\">[Highlighted Keyword]</span> [More Subtitle]</p>
        </div>
      </div>

      <!-- Slide 2: Table of Contents -->
      <div class=\"slide\">
        <div class=\"slide-container\">
          <h2 class=\"slide-title\">목차</h2>
          <div class=\"slide-content text-lg space-y-3\">
            <p><b>1. Part 1 Title:</b> Brief description of part 1.</p>
            <p><b>2. Part 2 Title:</b> Brief description of part 2.</p>
            <p><b>3. Part 3 Title:</b> Brief description of part 3.</p>
            <p><b>4. Part 4 Title:</b> Brief description of part 4.</p>
            <p><b>5. Conclusion:</b> Summary and final thoughts.</p>
          </div>
        </div>
      </div>

      <!-- Slide 3: Section Title -->
      <div class=\"slide\">
        <div class=\"slide-container\">
          <p class=\"slide-part-title\">Part 1: [Section Name]</p>
          <h2 class=\"slide-title\">[Title of Part 1] with <span class=\"highlight\">[Highlight]</span></h2>
          <p class=\"slide-content\">Brief introduction to this section of the presentation. What is the main topic you will be covering?</p>
        </div>
      </div>

      <!-- Slide 4: Standard Content Slide -->
      <div class=\"slide\">
        <div class=\"slide-container\">
          <h2 class=\"slide-title\">[Slide Title] <span class=\"highlight\">[Highlight]</span></h2>
          <p class=\"slide-subtitle\">[A compelling subtitle that explains the core message of the slide.]</p>
          <div class=\"slide-content\">
            <p>Main content of the slide. Use clear and concise sentences. Explain the key concepts and provide necessary details.</p>
            <p class=\"mt-4 font-bold\">This is an important takeaway or a key finding.</p>
          </div>
        </div>
      </div>

      <!-- Slide 5: Content with a special block -->
      <div class=\"slide\">
        <div class=\"slide-container\">
          <h2 class=\"slide-title\">[Slide with a <span class=\"highlight\">Special Block</span>]</h2>
          <p class=\"slide-subtitle\">[Explain the context for the information in the block below.]</p>
          <div class=\"slide-content\">
            <p>Supporting text that leads into the main point highlighted in the box.</p>
            <div class=\"mt-8 p-6 bg-gray-50 border border-gray-200 rounded-lg\">
              <h3 class=\"font-bold text-lg\">[Title for the Block]</h3>
              <p class=\"mt-2\">This block can be used to emphasize a key principle, a warning, or a special insight. <span class=\"highlight\">Use highlights</span> for important terms.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Slide 6: Two Column Layout -->
       <div class=\"slide\">
        <div class=\"slide-container\">
          <h2 class=\"slide-title\">[Two Column <span class=\"highlight\">Comparison</span>]</h2>
          <p class=\"slide-subtitle\">[Use this slide to compare two or more ideas, concepts, or data points.]</p>
          <div class=\"slide-content grid grid-cols-1 md:grid-cols-2 gap-8\">
            <div>
              <h3 class=\"font-bold text-lg\">[Column 1 Title]</h3>
              <p>Description for the first column. Explain the concept clearly.</p>
            </div>
            <div>
              <h3 class=\"font-bold text-lg\">[Column 2 Title]</h3>
              <p>Description for the second column. This should contrast or complement the first column.</p>
            </div>
          </div>
        </div>
      </div>

      <!-- Slide 7: Conclusion -->
      <div class=\"slide\">
        <div class=\"slide-container text-center\">
          <div class=\"text-6xl mb-6\">:dart:</div>
          <h2 class=\"slide-title\">Final Conclusion</h2>
          <div class=\"slide-content max-w-4xl mx-auto\">
            <p class=\"mb-4\">This is the final and most important message of your presentation. What is the one thing you want your audience to remember? <span class=\"highlight\">Highlight the absolute key takeaway.</span></p>
            <p class=\"mt-8 font-bold text-xl text-gray-800\">End with a strong, memorable statement.</p>
          </div>
        </div>
      </div>

      <!-- Slide 8: Thank You / Q&A -->
      <div class=\"slide\">
        <div class=\"slide-container text-center\">
          <div class=\"text-7xl mb-8\">:clap:</div>
          <h1 class=\"text-5xl md:text-6xl font-bold text-gray-800 mb-4\">Thank You</h1>
          <p class=\"text-xl md:text-2xl text-gray-600\">Q&A</p>
        </div>
      </div>

    </div>
  </div>

  <!-- Navigation -->
  <div class=\"progress-bar-container\">
    <div class=\"progress-bar\">
      <div id=\"progress\" class=\"progress\"></div>
    </div>
    <div class=\"flex justify-between items-center w-full max-w-6xl mx-auto\">
      <button id=\"prevBtn\" class=\"btn btn-secondary\"><i class=\"fa-solid fa-arrow-left mr-2\"></i> 이전</button>
      <span id=\"slideCounter\" class=\"text-gray-600 font-medium\"></span>
      <button id=\"nextBtn\" class=\"btn btn-primary\">다음 <i class=\"fa-solid fa-arrow-right ml-2\"></i></button>
    </div>
  </div>

  <script>
    let currentSlide = 0;
    const slides = document.querySelectorAll('.slide');
    const slideCounter = document.getElementById('slideCounter');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const progressBar = document.getElementById('progress');

    function updateSlide() {
      slides.forEach((slide, index) => {
        slide.classList.remove('active');
        if (index === currentSlide) {
          slide.classList.add('active');
        }
      });
      slideCounter.textContent = `Slide ${currentSlide + 1} / ${slides.length}`;
      progressBar.style.width = `${((currentSlide + 1) / slides.length) * 100}%`;

      prevBtn.disabled = currentSlide === 0;
      nextBtn.disabled = currentSlide === slides.length - 1;

      prevBtn.classList.toggle('opacity-50', currentSlide === 0);
      prevBtn.classList.toggle('cursor-not-allowed', currentSlide === 0);
      nextBtn.classList.toggle('opacity-50', currentSlide === slides.length - 1);
      nextBtn.classList.toggle('cursor-not-allowed', currentSlide === slides.length - 1);
    }

    nextBtn.addEventListener('click', () => {
      if (currentSlide < slides.length - 1) {
        currentSlide++;
        updateSlide();
      }
    });

    prevBtn.addEventListener('click', () => {
      if (currentSlide > 0) {
        currentSlide--;
        updateSlide();
      }
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight') {
        nextBtn.click();
      } else if (e.key === 'ArrowLeft') {
        prevBtn.click();
      }
    });

    // Initial setup
    updateSlide();
  </script>

</body>
</html>
```
"""

USER_PROMPT_TEMPLATE = """You are an expert content processor and HTML presentation generator. Your task is to process the content of the uploaded book file, comprehensively extract its information, and generate a detailed, multi-page HTML presentation. The presentation must be at least 40 pages long and include a title slide, table of contents, section title slides, standard content slides, content with special blocks, two-column layouts, a conclusion slide, and thank you/Q&A slides, all formatted as HTML ready for rendering.
Title: {title}
Author: {author}
# Step by Step instructions
1. Extract the content from the Book File.
2. Generate the HTML for the title slide of the presentation.
3. Generate the HTML for the table of contents slide, based on the extracted content.
4. Generate the HTML for a section title slide, followed by standard content slides, content with special blocks, or two-column layouts, using the extracted content.
5. Check if the total number of generated pages is at least 40 and if all extracted content has been comprehensively covered. If not, go back to step 4 to generate more slides, ensuring variety in slide types and comprehensive coverage of the Book File content.
6. Generate the HTML for the conclusion slide.
7. Generate the HTML for the thank you/Q&A slides.
"""


class MissingDependencyError(Exception):
    """Raised when required third-party packages are absent."""


def slugify(value: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", value.lower()).strip("-")
    return re.sub(r"-+", "-", slug) or "book"


def ensure_dependencies() -> None:
    missing: List[str] = []
    try:
        import pypdfium2  # noqa: F401
    except ImportError:
        missing.append("pypdfium2")
    try:
        from pypdf import PdfReader  # noqa: F401
    except ImportError:
        missing.append("pypdf")
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        missing.append("Pillow")
    if genai is None or genai_types is None:
        missing.append("google-genai")
    if missing:
        raise MissingDependencyError(
            "필수 패키지가 설치되어 있지 않습니다: " + ", ".join(missing)
        )


def extract_cover(pdf_path: Path, dest_path: Path) -> None:
    from PIL import Image
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        try:
            page = pdf.get_page(0)  # older API
        except AttributeError:
            page = pdf[0]  # pypdfium2 >= 5

        if hasattr(page, "render_topil"):
            bitmap = page.render_topil(scale=2.0)
        else:
            render_job = page.render(scale=2.0)
            bitmap = render_job.to_pil()
    finally:
        try:
            pdf.close()
        except AttributeError:
            pass

    width, height = bitmap.size
    target_ratio = 3 / 4
    current_ratio = width / height
    if current_ratio > target_ratio:
        new_width = int(height * target_ratio)
        offset = (width - new_width) // 2
        bitmap = bitmap.crop((offset, 0, offset + new_width, height))
    elif current_ratio < target_ratio:
        new_height = int(width / target_ratio)
        offset = (height - new_height) // 2
        bitmap = bitmap.crop((0, offset, width, offset + new_height))
    bitmap = bitmap.resize((600, 800), Image.LANCZOS)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    bitmap.save(dest_path, format="JPEG", quality=92)


def extract_pdf_metadata(pdf_path: Path) -> dict:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    info = reader.metadata or {}
    title = info.get("/Title")
    author = info.get("/Author")
    return {
        "title": title.strip() if isinstance(title, str) and title.strip() else None,
        "author": author.strip() if isinstance(author, str) and author.strip() else None,
    }


def call_gemini(
    pdf_path: Path,
    *,
    title: str,
    author: Optional[str],
    thinking_budget: int = 32_768,
    on_progress: Optional[Callable[[str], None]] = None,
) -> Tuple[str, List[str]]:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("환경 변수 GOOGLE_API_KEY가 설정되어 있지 않습니다.")

    client = genai.Client(api_key=api_key)
    pdf_bytes = pdf_path.read_bytes()

    request = [
        genai_types.Content(
            role="user",
            parts=[
                genai_types.Part.from_bytes(mime_type="application/pdf", data=pdf_bytes),
                genai_types.Part.from_text(
                    text=USER_PROMPT_TEMPLATE.format(title=title, author=author or "")
                ),
            ],
        )
    ]

    config = genai_types.GenerateContentConfig(
        system_instruction=[genai_types.Part.from_text(text=SYSTEM_PROMPT)],
        thinking_config=genai_types.ThinkingConfig(thinking_budget=thinking_budget),
    )

    state = {"chars": 0, "slides": 0, "last": 0}
    messages: List[str] = []

    def emit(message: str) -> None:
        messages.append(message)
        if on_progress:
            on_progress(message)
        else:
            print(message, flush=True)

    def handle_chunk(chunk_text: str) -> None:
        if not chunk_text:
            return
        state["chars"] += len(chunk_text)
        slide_hits = chunk_text.count('class="slide')
        if slide_hits:
            state["slides"] += slide_hits
            emit(f"[Gemini] 슬라이드 조각 생성: {state['slides']}")
        elif state["chars"] - state["last"] >= 1500:
            state["last"] = state["chars"]
            emit(f"[Gemini] 생성 중... {state['chars']} 글자")

    buffer: List[str] = []

    stream = client.models.generate_content_stream(
        model="gemini-2.5-pro",
        contents=request,
        config=config,
    )
    for chunk in stream:
        text_piece = getattr(chunk, "text", "") or ""
        if not text_piece and getattr(chunk, "candidates", None):
            collected: List[str] = []
            for cand in chunk.candidates:
                if getattr(cand, "content", None):
                    for part in cand.content.parts:
                        if hasattr(part, "text") and part.text:
                            collected.append(part.text)
            text_piece = "".join(collected)
        if not text_piece:
            continue
        buffer.append(text_piece)
        handle_chunk(text_piece)

    text = "".join(buffer)
    match = re.search(r"```html\n(.*)```", text, re.DOTALL)
    html = match.group(1).strip() if match else text.strip()
    if not html.lower().startswith("<!doctype"):
        html = "<!DOCTYPE html>\n" + html
    emit("[Gemini] 생성 완료")
    return html, messages


def write_presentation(html: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")


def update_manifest(entry: dict) -> None:
    records: List[dict]
    if DATA_FILE.exists():
        try:
            records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            if not isinstance(records, list):
                records = []
        except json.JSONDecodeError:
            records = []
    else:
        records = []

    records = [r for r in records if r.get("slug") != entry["slug"]]
    records.append(entry)

    def sort_key(item: dict) -> tuple:
        date_str = item.get("date") or ""
        try:
            return (dt.date.fromisoformat(date_str), item.get("title", ""))
        except ValueError:
            return (dt.date.min, item.get("title", ""))

    records.sort(key=sort_key, reverse=True)
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")


def git_stage_commit_push(files: Sequence[Path], *, message: str, do_commit: bool, do_push: bool) -> None:
    if not files:
        return
    rel_paths = [str(f.relative_to(ROOT)) for f in files if f.exists()]
    if not rel_paths:
        return
    subprocess.run(["git", "add", *rel_paths], cwd=ROOT, check=True)
    if do_commit:
        subprocess.run(["git", "commit", "-m", message], cwd=ROOT, check=True)
        if do_push:
            subprocess.run(["git", "push"], cwd=ROOT, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="원본 PDF 파일 경로")
    parser.add_argument("--title", help="표시 제목 (없으면 PDF 메타데이터 사용)")
    parser.add_argument("--author", help="저자 이름")
    parser.add_argument("--date", help="YYYY-MM-DD 형식, 기본값=오늘")
    parser.add_argument("--tags", help="쉼표로 구분된 태그 목록")
    parser.add_argument("--description", default="", help="짧은 설명")
    parser.add_argument("--slug", help="URL 슬러그 강제 지정")
    parser.add_argument("--dry-run", action="store_true", help="Gemini 호출 없이 파일만 준비")
    parser.add_argument("--commit", action="store_true", help="git commit 수행")
    parser.add_argument("--push", action="store_true", help="commit 후 push 수행")
    return parser.parse_args()


def run_pipeline(
    *,
    pdf_path: Path,
    title: Optional[str] = None,
    author: Optional[str] = None,
    date: Optional[str] = None,
    tags: Optional[Sequence[str]] = None,
    description: str = "",
    slug: Optional[str] = None,
    dry_run: bool = False,
    commit: bool = False,
    push: bool = False,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> dict:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF를 찾을 수 없습니다: {pdf_path}")

    ensure_dependencies()

    metadata = extract_pdf_metadata(pdf_path)
    resolved_title = title or metadata.get("title") or pdf_path.stem
    resolved_author = author or metadata.get("author")
    resolved_date = date or dt.date.today().isoformat()
    tag_list = [t.strip() for t in (tags or []) if t and t.strip()]
    resolved_slug = slug or slugify(resolved_title)
    safe_description = description.strip()

    cover_path = COVERS_DIR / f"{resolved_slug}.jpg"
    cover_rel = DEFAULT_COVER

    try:
        extract_cover(pdf_path, cover_path)
        cover_rel = cover_path.relative_to(ROOT).as_posix()
    except Exception as exc:  # pragma: no cover - environment dependent
        print(f"[경고] 커버 추출 실패: {exc}. 기본 이미지를 사용합니다.")
        cover_path = ROOT / DEFAULT_COVER

    progress_messages: List[str] = []

    if dry_run:
        html_text = (
            "<!DOCTYPE html><html lang='ko'><head><meta charset='utf-8'><title>Dry Run</title></head>"
            "<body><p>--dry-run 플래그로 인해 Gemini 호출을 건너뛰었습니다.</p></body></html>"
        )
        progress_messages.append("[Gemini] --dry-run: 실제 호출 없이 파일이 생성되었습니다.")
    else:
        def aggregator(message: str) -> None:
            progress_messages.append(message)
            if progress_callback:
                progress_callback(message)
            else:
                print(message, flush=True)

        aggregator("[Gemini] Gemini 2.5 Pro 호출 시작")
        html_text, generated_messages = call_gemini(
            pdf_path,
            title=resolved_title,
            author=resolved_author,
            on_progress=aggregator,
        )
        for msg in generated_messages:
            if msg not in progress_messages:
                progress_messages.append(msg)

    presentation_path = PRESENTATIONS_DIR / f"{resolved_slug}.html"
    presentation_rel = presentation_path.relative_to(ROOT).as_posix()
    write_presentation(html_text, presentation_path)

    entry = {
        "slug": resolved_slug,
        "title": resolved_title,
        "author": resolved_author,
        "date": resolved_date,
        "tags": tag_list,
        "description": safe_description,
        "presentation": presentation_rel,
        "cover": cover_rel,
    }
    update_manifest(entry)

    changed_files = [presentation_path, DATA_FILE]
    if cover_path and cover_path.exists():
        changed_files.append(cover_path)

    if commit or push:
        git_stage_commit_push(changed_files, message=f"Add book: {resolved_title}", do_commit=commit, do_push=push)

    return {
        **entry,
        "cover_path": str(cover_path) if cover_path else None,
        "presentation_path": str(presentation_path),
        "manifest_path": str(DATA_FILE),
        "progress": progress_messages,
    }


def main() -> int:
    args = parse_args()
    try:
        tag_list = [t.strip() for t in args.tags.split(",")] if args.tags else []
        run_pipeline(
            pdf_path=args.pdf,
            title=args.title,
            author=args.author,
            date=args.date,
            tags=tag_list,
            description=args.description,
            slug=args.slug,
            dry_run=args.dry_run,
            commit=args.commit,
            push=args.push,
        )
    except MissingDependencyError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(f"[오류] {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"[경고] git 작업 실패: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - unexpected
        print(f"[오류] 처리 중 예외 발생: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
