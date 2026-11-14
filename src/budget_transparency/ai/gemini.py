"""Gemini 호출 함수. 키와 모델 ID는 환경 변수에서 읽고, 로컬에서는 .env 파일로 관리한다.

사용:
    load_env()                      # 저장소 루트의 .env를 환경 변수로 읽음(이미 있는 값은 유지)
    generate = make_generate()      # 키나 모델 ID가 없으면 None → 기본 안내·기본 규칙으로 동작
    explain_analysis(analysis, generate)
    parse_query(text, options, generate)

키는 요청 헤더로만 보낸다. URL·로그·오류 메시지에 넣지 않는다.
SDK를 설치하지 않고 표준 라이브러리로 REST API를 호출한다.
"""
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
KEY_ENV = "GEMINI_API_KEY"
MODEL_ENV = "GEMINI_MODEL"
TIMEOUT_SECONDS = 10
_MODEL_ID = re.compile(r"[A-Za-z0-9._-]+")


class GeminiError(RuntimeError):
    """모델 호출 실패. 메시지에 키·요청 내용을 넣지 않는다."""


def load_env(path=None):
    """.env 파일의 KEY=VALUE를 환경 변수로 읽는다. 이미 설정된 환경 변수는 덮어쓰지 않는다.

    파일이 없으면 아무것도 하지 않는다. 읽은 변수 이름 목록을 돌려준다(값은 돌려주지 않음).
    """
    path = Path(path) if path is not None else ROOT / ".env"
    if not path.is_file():
        return []
    names = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name, value = name.strip(), value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) or not value:
            continue
        os.environ.setdefault(name, value)
        names.append(name)
    return names


def _text_from(response):
    """응답 JSON에서 모델이 쓴 글만 꺼낸다."""
    try:
        parts = response["candidates"][0]["content"]["parts"]
        text = "".join(part["text"] for part in parts if isinstance(part.get("text"), str))
    except (KeyError, IndexError, TypeError, AttributeError):
        raise GeminiError("모델 응답에 내용이 없습니다.") from None
    if not text.strip():
        raise GeminiError("모델 응답에 내용이 없습니다.")
    return text


def make_generate(api_key=None, model=None, timeout=TIMEOUT_SECONDS, opener=None):
    """(system, user) → 응답 문자열 함수를 만든다. 키나 모델 ID가 없으면 None.

    None을 explain_analysis·parse_query에 그대로 넘기면 AI 없이 동작한다.
    opener는 테스트에서 실제 호출을 대신하는 함수다(기본은 urllib.request.urlopen).
    """
    api_key = api_key if api_key is not None else os.environ.get(KEY_ENV, "")
    model = model if model is not None else os.environ.get(MODEL_ENV, "")
    api_key, model = api_key.strip(), model.strip()
    if not api_key or not model:
        return None
    if not _MODEL_ID.fullmatch(model):
        raise GeminiError("모델 ID 형식이 올바르지 않습니다.")
    opener = opener or urllib.request.urlopen
    url = API_URL.format(model=model)

    def generate(system, user):
        body = {
            "system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
            method="POST",
        )
        try:
            with opener(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise GeminiError(f"모델 호출이 실패했습니다(HTTP {exc.code}).") from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise GeminiError("모델에 연결하지 못했거나 시간이 초과되었습니다.") from None
        except ValueError:
            raise GeminiError("모델 응답을 읽을 수 없습니다.") from None
        return _text_from(payload)

    return generate
