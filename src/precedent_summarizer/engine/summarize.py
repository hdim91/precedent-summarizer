"""요약 엔진 v1 (Claude 소유). 단건 호출·배치 요청 생성·응답 파싱."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
from typing import Any, Optional

from precedent_summarizer.config import PROJECT_ROOT
from precedent_summarizer.schemas.summary import OUTPUT_CONFIG, SUMMARY_VERSION

PROMPT_PATH = PROJECT_ROOT / "prompts" / f"summarize_{SUMMARY_VERSION}.md"
MAX_TOKENS = 16000  # 모델 내부 추론(thinking) 토큰 포함 여유


@dataclass
class CaseInput:
    prec_id: str
    case_no: Optional[str]
    case_name: Optional[str]
    decision_date: Optional[str]
    court_name: Optional[str]
    case_type_name: Optional[str]
    full_text_clean: str


def system_prompt() -> str:
    return Path(PROMPT_PATH).read_text(encoding="utf-8")


def user_message(c: CaseInput) -> str:
    meta = "\n".join(f"- {k}: {v or '(없음)'}" for k, v in [
        ("판례일련번호", c.prec_id), ("사건번호", c.case_no), ("사건명", c.case_name),
        ("선고일자", c.decision_date), ("법원", c.court_name), ("사건종류", c.case_type_name)])
    return f"# 판결 메타데이터\n{meta}\n\n<판례내용>\n{c.full_text_clean}\n</판례내용>\n\n위 판결을 지정된 JSON 스키마로 요약하라."


def request_params(c: CaseInput, model: str) -> dict[str, Any]:
    """messages.create / Batches API 공용 파라미터. 시스템 프롬프트는 캐시."""
    return {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": [{"type": "text", "text": system_prompt(), "cache_control": {"type": "ephemeral"}}],
        "output_config": OUTPUT_CONFIG,
        "messages": [{"role": "user", "content": user_message(c)}],
    }


class SummaryParseError(ValueError):
    pass


def parse_output(message: Any) -> dict:
    """응답(Message 객체 또는 dict)의 text 블록 JSON 파싱. 잘림·거부는 오류."""
    content = message["content"] if isinstance(message, dict) else message.content
    stop = message.get("stop_reason") if isinstance(message, dict) else message.stop_reason
    if stop in ("max_tokens", "refusal"):
        raise SummaryParseError(f"구조화 출력 미완결(stop_reason={stop})")
    for block in content:
        btype = block["type"] if isinstance(block, dict) else block.type
        if btype == "text":
            text = block["text"] if isinstance(block, dict) else block.text
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                raise SummaryParseError(f"JSON 파싱 실패: {exc.msg}") from None
    raise SummaryParseError(f"text 블록 없음(stop_reason={stop})")


def summarize_one(client: Any, c: CaseInput, model: str) -> tuple[dict, dict]:
    """단건 동기 호출 → (summary, usage)."""
    msg = client.messages.create(**request_params(c, model))
    u = msg.usage
    usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
             "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0) or 0,
             "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0) or 0,
             "stop_reason": msg.stop_reason}
    return parse_output(msg), usage
