# ppt-test (Slide Generator Demo)

FastAPI 기반 슬라이드 생성 데모 앱입니다.

## 준비

- **Python** 3.10 이상 권장  
- 패키지 관리: **pip** 또는 **[uv](https://docs.astral.sh/uv/)** (둘 다 가능)

### pip + venv

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate
```

### uv

```bash
uv venv
```

이후 명령은 프로젝트 루트에서 **`uv run …`** 으로 실행하면 `.venv`를 자동으로 씁니다(별도 `activate` 불필요).

## 설치

### pip

```bash
pip install -r requirements.txt
playwright install
```

### uv

```bash
uv pip install -r requirements.txt
uv run playwright install
```

`playwright install`은 PDF/HTML export 등에 쓰는 브라우저 바이너리를 받습니다.

## 환경 변수

`.env.example`을 복사해 `.env`를 만들고 API 키를 넣습니다.

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

필수에 가깝게 쓰이는 값은 `OPENROUTER_API_KEY`입니다. 나머지는 기본값으로도 동작합니다.

## 실행

**Windows**에서는 Playwright(서브프로세스)와 개발 서버 호환을 위해 `run_dev.py`를 사용합니다.

```bash
python run_dev.py
# uv 사용 시(루트에서, activate 없이)
uv run python run_dev.py
```

- 기본 주소: `http://127.0.0.1:8001` (8001이 막혀 있으면 스크립트가 비슷한 포트로 자동 선택)
- 포트 지정: `python run_dev.py --port 8010`
- 리로드 끄기: `python run_dev.py --no-reload`

**macOS / Linux**에서는 일반적으로 아래로도 실행할 수 있습니다.

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
# uv
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

## API 문서

서버 실행 후 브라우저에서:

- Swagger UI: `http://127.0.0.1:<포트>/docs`
- ReDoc: `http://127.0.0.1:<포트>/redoc`

`<포트>`는 터미널에 출력된 값과 맞춥니다.
