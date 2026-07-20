from pydantic import BaseModel


class JdKeyword(BaseModel):
    term: str
    aliases: list[str] = []
    required: bool


class AtsScore(BaseModel):
    overall: int  # 0-100
    keyword_coverage: float  # fraction of required keywords matched, 0-1
    llm_fit: int  # 0-100
    required_keywords: list[str]
    matched: list[str]
    missing: list[str]  # required JD keywords absent from the résumé — the gap list
    rationale: str
