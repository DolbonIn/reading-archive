# Reading Archive · AI Bookshelf

PDF 한 권만 업로드하면 Google Gemini 2.5 Pro가 Tailwind 기반 HTML 프레젠테이션을 자동으로 생성하고,
정교한 3D 책장 UI에서 책처럼 진열되는 프로젝트입니다.

## 구조

```
/
├── index.html                # GitHub Pages용 단일 페이지 (Three.js 책장)
├── assets/
│   ├── css/shelf.css         # 책장/오버레이 스타일
│   ├── js/shelf.js           # Three.js로 3D 책장 렌더링
│   └── covers/default.svg    # 기본 커버 이미지
├── data/books.json           # 책 메타데이터 manifest (자동 갱신)
├── presentations/            # Gemini가 생성한 HTML 프레젠테이션
├── scripts/process_pdf.py    # PDF → 커버 & 프레젠테이션 & manifest 자동화
└── local_app/                # 로컬 업로드 웹 앱 (Flask)
```

## 환경 변수 (.env)

- `.env.example`을 `.env`로 복사한 뒤 값을 채워주세요.
- `GOOGLE_API_KEY`에 Gemini API 키를 넣으면 CLI와 Flask 앱이 자동으로 불러옵니다.
- `READING_ARCHIVE_AUTO_COMMIT`, `READING_ARCHIVE_AUTO_PUSH`를 `true`로 설정하면 업로드 시 자동 커밋/푸시가 동작합니다. 값은 미설정 시 `false`로 간주됩니다.
- `.env`는 `.gitignore`에 포함되어 있어 안전하게 버전 관리에서 제외됩니다.

## 1. GitHub Pages 책장 UI

`index.html`은 `data/books.json`을 로드해 실제 표지를 사용한 3D 책장을 그립니다. 책을 클릭하면
`presentations/<slug>.html` 파일을 새 탭에서 열어 바로 AI 요약을 볼 수 있습니다.

- Three.js + Tailwind CDN 기반, 빌드 과정 없이 바로 사용 가능
- 마우스 이동 시 책장이 부드럽게 회전, 호버하면 우측 패널에 정보 표시
- `data/books.json` 구조 예시:
  ```json
  [
    {
      "slug": "deep-work",
      "title": "Deep Work",
      "author": "Cal Newport",
      "date": "2024-01-01",
      "tags": ["생산성", "집중"],
      "description": "깊은 몰입으로 성과를 높이는 전략",
      "presentation": "/presentations/deep-work.html",
      "cover": "/assets/covers/deep-work.jpg"
    }
  ]
  ```

GitHub Pages에 배포할 때는 이 저장소 루트를 그대로 사용하면 됩니다.

## 2. Gemini 자동화 파이프라인

`scripts/process_pdf.py`는 한 번의 명령으로 다음을 수행합니다.

1. PDF 첫 페이지에서 600×800 커버 JPEG 추출
2. Gemini 2.5 Pro 호출 → Tailwind HTML 프레젠테이션 생성
3. `presentations/<slug>.html`, `assets/covers/<slug>.jpg` 저장
4. `data/books.json` manifest 갱신 (날짜 역순 정렬)

### 설치

```bash
pip install google-genai pypdfium2 pypdf pillow
# 또는 `.env`에 GOOGLE_API_KEY를 설정해 두세요.
```

### 실행 예시

```bash
python scripts/process_pdf.py ./books/deep_work.pdf \
  --title "Deep Work" \
  --author "Cal Newport" \
  --tags "생산성, 집중" \
  --description "깊은 몰입으로 성과를 높이는 전략" \
  --commit
```

옵션
- `--dry-run` : Gemini 호출 없이 HTML 틀만 작성
- `--commit` / `--push` : 변경 파일을 자동 커밋/푸시 (GitHub Pages 자동 배포 시 유용)
- `--slug` : URL 슬러그 강제 지정
- 실행 중에는 스트림 API를 이용해 슬라이드 생성 진행 상황(슬라이드 수, 생성된 문자 수)이 콘솔에 출력됩니다.

## 3. 로컬 업로드 웹 앱 (Flask)

`local_app/app.py`는 Tailwind 스타일의 미려한 업로더를 제공합니다.

```bash
pip install flask google-genai pypdfium2 pypdf pillow
export FLASK_APP=local_app.app:app
# `.env`에 GOOGLE_API_KEY를 지정했다면 별도 export 없이 동작합니다.
flask run --reload
```

- 드래그 & 드롭 또는 클릭으로 PDF 업로드
- 제목/저자/태그/설명/날짜 입력 가능
- Gemini 호출 없이 테스트(`dry-run`), 자동 커밋/푸시 토글
- 성공 시 프레젠테이션 파일 링크를 바로 제공합니다.
- 환경 변수 `READING_ARCHIVE_AUTO_COMMIT=true`, `READING_ARCHIVE_AUTO_PUSH=true`를 설정하면 체크박스 선택과 상관없이 업로드 때마다 자동 커밋/푸시가 수행됩니다(단, `--dry-run`일 때는 항상 비활성화).
- 업로드 후 응답 패널에서 스트리밍된 진행 로그를 확인할 수 있으며, 서버 로그에도 동일한 메시지가 기록됩니다.

## 4. GitHub Pages 배포 가이드

1. 이 저장소 루트에 `.nojekyll` 파일이 없어야 Jekyll 처리 없이 정적 파일이 제공됩니다.
2. `data/books.json`과 `presentations/` 내 파일을 커밋 후 기본 브랜치에 push
3. GitHub Pages를 “Deploy from a branch” > `main`/`docs` 등으로 설정하면 즉시 반영됩니다.
4. 새 PDF 추가 시 `process_pdf.py` 또는 로컬 웹 앱을 사용해 파일을 생성하고 다시 커밋/푸시합니다.

## 5. 개발 팁

- `assets/js/shelf.js`는 Three.js 전역 객체를 사용하므로 CDN 버전을 변경할 경우 API 호환성을 확인하세요.
- 책 데이터가 없을 때는 화면 중앙에 안내 메시지가 표시됩니다.
- `presentations/.gitkeep`는 폴더 유지용이므로 실제 프레젠테이션 생성 후 삭제해도 됩니다.

행복한 독서와 기록을 응원합니다! 📚
