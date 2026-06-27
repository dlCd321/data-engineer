from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import unicodedata
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, Field, ValidationError, field_validator


ROOT_DIR = Path(__file__).resolve().parents[1]
Q4_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_PATH = ROOT_DIR / "data" / "olist" / "olist_order_reviews_dataset.csv"
DEFAULT_OUTPUT_PATH = Q4_DIR / "extracted_issues.json"
DEFAULT_LIVE_OUTPUT_PATH = Q4_DIR / "extracted_issues_live_sample.json"
DEFAULT_COST_REPORT_PATH = Q4_DIR / "cost_report.md"
DEFAULT_PIPELINE_DESIGN_PATH = Q4_DIR / "pipeline_design.md"
DEFAULT_ACCURACY_PATH = Q4_DIR / "accuracy_evaluation.md"

PIPELINE_VERSION = "q4-v1"
LOW_SCORE_THRESHOLD = 3
SMALL_MAX_CHARS = 120
LARGE_MIN_CHARS = 160
LARGE_COMPLEX_MARKER_MIN = 2
SMALL_RETRY_MIN_CHARS = 100
MIN_CONFIDENCE = 0.70
DEFAULT_PROVIDER: Literal["openrouter", "deepseek"] = "openrouter"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
OPENROUTER_SMALL_MODEL = "deepseek/deepseek-v3.1"
OPENROUTER_LARGE_MODEL = "deepseek/deepseek-r1"
DEEPSEEK_SMALL_MODEL = "deepseek-v4-flash"
DEEPSEEK_LARGE_MODEL = "deepseek-v4-pro"

ALLOWED_TAXONOMY: dict[str, set[str]] = {
    "delivery": {"delay", "not_received", "tracking_issue"},
    "product": {"defective", "wrong_item", "poor_quality", "missing_parts"},
    "service": {"no_response", "refund_problem", "seller_attitude"},
    "payment": {"billing_issue", "refund_delay"},
    "general": {"negative_low_detail", "unclear"},
}

# These are deliberately estimates for budget gating, not billing truth.
# Keep them configurable because provider pricing changes over time.
DEFAULT_MODEL_PRICES_PER_1M = {
    "small": {"input": 0.15, "output": 0.60},
    "large": {"input": 2.50, "output": 10.00},
}


class Issue(BaseModel):
    category: str
    subcategory: str
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("subcategory")
    @classmethod
    def validate_taxonomy(cls, subcategory: str, info: Any) -> str:
        category = info.data.get("category")
        if category not in ALLOWED_TAXONOMY:
            raise ValueError(f"未知 category: {category}")
        if subcategory not in ALLOWED_TAXONOMY[category]:
            raise ValueError(f"未知 subcategory: {category}.{subcategory}")
        return subcategory


class ExtractionResult(BaseModel):
    issues: list[Issue] = Field(min_length=1)
    method: str
    model: str | None = None
    needs_manual_review: bool = False

    @property
    def min_confidence(self) -> float:
        return min(issue.confidence for issue in self.issues)


@dataclass(frozen=True)
class ReviewRecord:
    review_id: str
    order_id: str
    review_score: int
    raw_text: str
    normalized_text: str
    normalized_text_hash: str


@dataclass(frozen=True)
class DedupGroup:
    dedup_key: str
    representative_raw_text: str
    representative_normalized_text: str
    records: tuple[ReviewRecord, ...]


@dataclass(frozen=True)
class RoutedGroup:
    group: DedupGroup
    route: Literal["rule", "small_llm", "large_llm"]
    reason: str


@dataclass(frozen=True)
class ProviderConfig:
    provider: Literal["openrouter", "deepseek"]
    api_key: str
    base_url: str
    default_headers: dict[str, str] | None = None


@dataclass(frozen=True)
class ProviderUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    actual_cost_usd: float | None = None


@dataclass(frozen=True)
class LLMJsonResponse:
    text: str
    usage: ProviderUsage


@dataclass(frozen=True)
class CostTracker:
    max_cost_usd: float | None
    estimated_cost_usd: float = 0.0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    actual_input_tokens: int = 0
    actual_output_tokens: int = 0
    actual_cost_usd: float | None = None

    def add_call(
        self,
        route: Literal["small", "large"],
        input_tokens: int,
        output_tokens: int,
    ) -> "CostTracker":
        prices = DEFAULT_MODEL_PRICES_PER_1M[route]
        call_cost = (
            input_tokens * prices["input"] / 1_000_000
            + output_tokens * prices["output"] / 1_000_000
        )
        next_cost = self.estimated_cost_usd + call_cost
        if self.max_cost_usd is not None and next_cost > self.max_cost_usd:
            raise RuntimeError(
                f"预计成本 ${next_cost:.4f} 超过上限 ${self.max_cost_usd:.2f}，已停止 live 调用。"
            )
        return CostTracker(
            max_cost_usd=self.max_cost_usd,
            estimated_cost_usd=next_cost,
            estimated_input_tokens=self.estimated_input_tokens + input_tokens,
            estimated_output_tokens=self.estimated_output_tokens + output_tokens,
            actual_input_tokens=self.actual_input_tokens,
            actual_output_tokens=self.actual_output_tokens,
            actual_cost_usd=self.actual_cost_usd,
        )

    def add_usage(self, usage: ProviderUsage) -> "CostTracker":
        actual_cost = self.actual_cost_usd
        if usage.actual_cost_usd is not None:
            actual_cost = (actual_cost or 0.0) + usage.actual_cost_usd
        return CostTracker(
            max_cost_usd=self.max_cost_usd,
            estimated_cost_usd=self.estimated_cost_usd,
            estimated_input_tokens=self.estimated_input_tokens,
            estimated_output_tokens=self.estimated_output_tokens,
            actual_input_tokens=self.actual_input_tokens + usage.input_tokens,
            actual_output_tokens=self.actual_output_tokens + usage.output_tokens,
            actual_cost_usd=actual_cost,
        )


@dataclass(frozen=True)
class ProcessingStats:
    llm_call_count: int = 0
    failed_llm_count: int = 0
    schema_error_count: int = 0
    evidence_error_count: int = 0
    budget_exhausted: bool = False
    live_sample_requested: int | None = None
    live_sample_actual: int | None = None

    def with_call(self) -> "ProcessingStats":
        return self.__class__(**{**self.__dict__, "llm_call_count": self.llm_call_count + 1})

    def with_failure(
        self,
        *,
        schema_error: bool = False,
        evidence_error: bool = False,
    ) -> "ProcessingStats":
        return self.__class__(
            **{
                **self.__dict__,
                "failed_llm_count": self.failed_llm_count + 1,
                "schema_error_count": self.schema_error_count + int(schema_error),
                "evidence_error_count": self.evidence_error_count + int(evidence_error),
            }
        )

    def with_budget_exhausted(self) -> "ProcessingStats":
        return self.__class__(**{**self.__dict__, "budget_exhausted": True})


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT_DIR / ".env")


def default_small_model(provider: Literal["openrouter", "deepseek"]) -> str:
    return OPENROUTER_SMALL_MODEL if provider == "openrouter" else DEEPSEEK_SMALL_MODEL


def default_large_model(provider: Literal["openrouter", "deepseek"]) -> str:
    return OPENROUTER_LARGE_MODEL if provider == "openrouter" else DEEPSEEK_LARGE_MODEL


def provider_config(provider: Literal["openrouter", "deepseek"]) -> ProviderConfig:
    if provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("live 模式 provider=openrouter 需要 OPENROUTER_API_KEY。")
        return ProviderConfig(
            provider=provider,
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_HTTP_REFERER", "https://localhost/q4-llm-extraction"),
                "X-OpenRouter-Title": os.getenv("OPENROUTER_APP_TITLE", "Q4 Review Extraction"),
            },
        )

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("live 模式 provider=deepseek 需要 DEEPSEEK_API_KEY。")
    return ProviderConfig(
        provider=provider,
        api_key=api_key,
        base_url=DEEPSEEK_BASE_URL,
        default_headers=None,
    )


def clean_text_cell(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_raw_text(title: Any, message: Any) -> str:
    parts = [clean_text_cell(title), clean_text_cell(message)]
    return " ".join(part for part in parts if part).strip()


def normalize_text(text: str) -> str:
    normalized = html.unescape(text)
    normalized = re.sub(r"<[^>]+>", " ", normalized)
    normalized = re.sub(r"https?://\S+|www\.\S+", " ", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"[\u200b-\u200f\ufeff]", "", normalized)
    normalized = normalized.casefold()
    normalized = unicodedata.normalize("NFKD", normalized)
    normalized = "".join(c for c in normalized if not unicodedata.combining(c))
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def hash_normalized_text(normalized_text: str) -> str:
    return hashlib.sha1(normalized_text.encode("utf-8")).hexdigest()


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\wÀ-ÿ]+\b", text, flags=re.UNICODE))


def normalize_evidence_text(text: str) -> str:
    normalized = html.unescape(text)
    normalized = re.sub(r"[\u200b-\u200f\ufeff]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip().casefold()
    return normalized


def contains_evidence(raw_text: str, evidence: str) -> bool:
    if evidence == "":
        return raw_text == ""
    return normalize_evidence_text(evidence) in normalize_evidence_text(raw_text)


def validate_result_for_text(result: ExtractionResult, raw_text: str) -> ExtractionResult:
    for issue in result.issues:
        if not contains_evidence(raw_text, issue.evidence):
            raise ValueError(f"evidence 不在原文中: {issue.evidence}")
    return result


def load_low_score_reviews(input_path: Path) -> list[ReviewRecord]:
    df = pd.read_csv(input_path)
    required_columns = {
        "review_id",
        "order_id",
        "review_score",
        "review_comment_title",
        "review_comment_message",
    }
    missing = required_columns - set(df.columns)
    if missing:
        raise ValueError(f"输入文件缺少列: {sorted(missing)}")

    low = df[df["review_score"] <= LOW_SCORE_THRESHOLD].copy()
    records: list[ReviewRecord] = []
    for row in low.itertuples(index=False):
        raw_text = build_raw_text(row.review_comment_title, row.review_comment_message)
        normalized_text = normalize_text(raw_text)
        records.append(
            ReviewRecord(
                review_id=str(row.review_id),
                order_id=str(row.order_id),
                review_score=int(row.review_score),
                raw_text=raw_text,
                normalized_text=normalized_text,
                normalized_text_hash=hash_normalized_text(normalized_text),
            )
        )
    return records


def deduplicate_reviews(records: list[ReviewRecord]) -> list[DedupGroup]:
    grouped: OrderedDict[str, list[ReviewRecord]] = OrderedDict()
    for record in records:
        grouped.setdefault(record.normalized_text_hash, []).append(record)

    return [
        DedupGroup(
            dedup_key=dedup_key,
            representative_raw_text=items[0].raw_text,
            representative_normalized_text=items[0].normalized_text,
            records=tuple(items),
        )
        for dedup_key, items in grouped.items()
    ]


def issue(
    category: str,
    subcategory: str,
    evidence: str,
    confidence: float,
) -> Issue:
    return Issue(
        category=category,
        subcategory=subcategory,
        evidence=evidence,
        confidence=confidence,
    )


def raw_excerpt(raw_text: str, max_chars: int = 200) -> str:
    return raw_text.strip()[:max_chars]


RULE_PATTERNS: tuple[tuple[str, str, str, float], ...] = (
    (r"\b(n[aã]o|nao|não)\s+(recebi|recebeu|chegou|entregaram|entregou)\b|produto\s+n[aã]o\s+entregue|pedido\s+n[aã]o\s+chegou", "delivery", "not_received", 0.95),
    (r"\b(ainda|ate|até).{0,25}\b(n[aã]o|nao|não)\s+(recebi|chegou)\b", "delivery", "not_received", 0.95),
    (r"\b(atraso|atrasado|demora|demorou|prazo|fora do prazo)\b", "delivery", "delay", 0.88),
    (r"\b(rastreamento|transportadora|correios|codigo de rastreio|código de rastreio)\b", "delivery", "tracking_issue", 0.82),
    (r"\b(defeito|defeituoso|quebrad[oa]|danificad[oa]|estragad[oa]|avariad[oa])\b", "product", "defective", 0.90),
    (r"\b(produto errado|item errado|modelo errado|veio errado|diferente do anuncio|diferente do anúncio|nao condiz|não condiz)\b", "product", "wrong_item", 0.88),
    (r"\b(qualidade ruim|baixa qualidade|inferior|mal acabado|fragil|frágil|pessima qualidade|péssima qualidade)\b", "product", "poor_quality", 0.86),
    (r"\b(faltou|faltando|veio sem|incompleto|somente 1|s[oó] recebi uma|s[oó] recebi um)\b", "product", "missing_parts", 0.86),
    (r"\b(sem resposta|nao respondeu|não respondeu|ningu[eé]m responde|atendimento|sac|suporte)\b", "service", "no_response", 0.84),
    (r"\b(reembolso|estorno|devolu[cç][aã]o|troca)\b", "service", "refund_problem", 0.82),
    (r"\b(cobran[cç]a|boleto|cart[aã]o|pagamento|cobrado)\b", "payment", "billing_issue", 0.80),
)

LOW_INFORMATION_PATTERNS = (
    r"^(ruim|pessimo|péssimo|horrivel|horrível|regular|ok|nao gostei|não gostei|nao recomendo|não recomendo|insatisfeito|decepcionado)\.?$",
)

POSITIVE_OR_CONTRADICTORY_PATTERNS = (
    r"^(bom|boa|muito bom|ótimo|otimo|excelente|recomendo|entrega no prazo|ok)\.?$",
)


def apply_rule_engine(group: DedupGroup) -> ExtractionResult | None:
    raw_text = group.representative_raw_text
    normalized = group.representative_normalized_text

    if normalized == "":
        return ExtractionResult(
            issues=[issue("general", "negative_low_detail", "", 0.75)],
            method="rule",
            model=None,
            needs_manual_review=True,
        )

    if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in POSITIVE_OR_CONTRADICTORY_PATTERNS):
        return ExtractionResult(
            issues=[issue("general", "unclear", raw_excerpt(raw_text), 0.55)],
            method="rule",
            model=None,
            needs_manual_review=True,
        )

    if count_words(normalized) <= 4 or any(
        re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in LOW_INFORMATION_PATTERNS
    ):
        return ExtractionResult(
            issues=[issue("general", "negative_low_detail", raw_excerpt(raw_text), 0.72)],
            method="rule",
            model=None,
            needs_manual_review=False,
        )

    issues: list[Issue] = []
    seen: set[tuple[str, str]] = set()
    for pattern, category, subcategory, confidence in RULE_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            key = (category, subcategory)
            if key not in seen:
                issues.append(issue(category, subcategory, raw_excerpt(raw_text), confidence))
                seen.add(key)

    if not issues:
        return None

    return ExtractionResult(
        issues=issues,
        method="rule",
        model=None,
        needs_manual_review=False,
    )


def route_group(group: DedupGroup) -> RoutedGroup:
    if apply_rule_engine(group) is not None:
        return RoutedGroup(group=group, route="rule", reason="规则或低信息模板命中")

    text_length = len(group.representative_normalized_text)
    complex_markers = len(
        re.findall(
            r"\b(mas|por[eé]m|tamb[eé]m|al[eé]m|reembolso|troca|resposta|prazo|quebrad[oa]|faltou)\b",
            group.representative_normalized_text,
            flags=re.IGNORECASE,
        )
    )

    if text_length > LARGE_MIN_CHARS:
        return RoutedGroup(group=group, route="large_llm", reason=f"字符数 {text_length} 超过 {LARGE_MIN_CHARS}")

    if text_length > SMALL_MAX_CHARS and complex_markers >= LARGE_COMPLEX_MARKER_MIN:
        return RoutedGroup(group=group, route="large_llm", reason="中长文本且包含多个问题信号")

    return RoutedGroup(group=group, route="small_llm", reason="短文本且规则未稳定覆盖")


def count_complex_markers(normalized_text: str) -> int:
    return len(
        re.findall(
            r"\b(mas|por[eé]m|tamb[eé]m|al[eé]m|reembolso|troca|resposta|prazo|quebrad[oa]|faltou)\b",
            normalized_text,
            flags=re.IGNORECASE,
        )
    )


def should_retry_small_failure_as_large(group: DedupGroup) -> bool:
    normalized = group.representative_normalized_text
    if len(normalized) >= SMALL_RETRY_MIN_CHARS:
        return True
    if count_complex_markers(normalized) >= LARGE_COMPLEX_MARKER_MIN:
        return True
    return bool(
        re.search(
            r"\b(reembolso|estorno|devolu[cç][aã]o|troca|sem resposta|atendimento|sac|suporte|cobran[cç]a|pagamento|produto errado|veio errado|diferente do anuncio|diferente do anúncio|defeito|quebrad[oa]|faltou|faltando)\b",
            normalized,
            flags=re.IGNORECASE,
        )
    )


def fallback_unclear_result(route: Literal["small_llm", "large_llm"], raw_text: str) -> ExtractionResult:
    return ExtractionResult(
        issues=[issue("general", "unclear", raw_excerpt(raw_text), 0.50)],
        method=f"offline_{route}_fallback",
        model=None,
        needs_manual_review=True,
    )


def estimate_tokens(text: str) -> int:
    return max(1, int(len(text) / 4) + 1)


def build_small_batches(groups: list[DedupGroup], token_budget: int) -> list[list[DedupGroup]]:
    batches: list[list[DedupGroup]] = []
    current_batch: list[DedupGroup] = []
    current_tokens = 0

    for group in groups:
        item_tokens = estimate_tokens(group.representative_raw_text) + 80
        if current_batch and current_tokens + item_tokens > token_budget:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0
        current_batch.append(group)
        current_tokens += item_tokens

    if current_batch:
        batches.append(current_batch)
    return batches


class CompatibleLLMExtractor:
    def __init__(
        self,
        provider: Literal["openrouter", "deepseek"],
        small_model: str,
        large_model: str,
    ) -> None:
        config = provider_config(provider)
        from openai import OpenAI

        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            default_headers=config.default_headers,
        )
        self.provider = config.provider
        self.small_model = small_model
        self.large_model = large_model

    def call_small_batch(self, batch: list[DedupGroup]) -> tuple[dict[str, ExtractionResult], ProviderUsage]:
        payload = [
            {"dedup_key": group.dedup_key, "raw_text": group.representative_raw_text}
            for group in batch
        ]
        prompt = (
            "你是电商评论问题抽取器。只从葡萄牙语原文中抽取明确出现的问题，"
            "返回 JSON: {\"items\":[{\"dedup_key\":\"...\",\"issues\":[{\"category\":\"...\","
            "\"subcategory\":\"...\",\"evidence\":\"原文片段\",\"confidence\":0.0}],"
            "\"needs_manual_review\":false}]}。类别必须使用预定义 taxonomy。"
            f"taxonomy={json.dumps({k: sorted(v) for k, v in ALLOWED_TAXONOMY.items()}, ensure_ascii=False)}"
        )
        response = self._chat_json(self.small_model, prompt, json.dumps(payload, ensure_ascii=False))
        parsed = json.loads(response.text)
        results: dict[str, ExtractionResult] = {}
        for item in parsed.get("items", []):
            dedup_key = item["dedup_key"]
            results[dedup_key] = ExtractionResult(
                issues=[Issue(**raw_issue) for raw_issue in item["issues"]],
                method="small_llm",
                model=self.small_model,
                needs_manual_review=bool(item.get("needs_manual_review", False)),
            )
        return results, response.usage

    def call_large_single(self, group: DedupGroup) -> tuple[ExtractionResult, ProviderUsage]:
        prompt = (
            "你是复杂电商差评分析器。抽取评论中所有明确出现的问题，允许多个 issue。"
            "必须返回 json object: {\"issues\":[{\"category\":\"...\",\"subcategory\":\"...\","
            "\"evidence\":\"原文片段\",\"confidence\":0.0}],\"needs_manual_review\":false}。"
            "evidence 必须是原文中连续片段，不要翻译后再当 evidence。"
            f"taxonomy={json.dumps({k: sorted(v) for k, v in ALLOWED_TAXONOMY.items()}, ensure_ascii=False)}"
        )
        response = self._chat_json(self.large_model, prompt, group.representative_raw_text)
        parsed = json.loads(response.text)
        return (
            ExtractionResult(
                issues=[Issue(**raw_issue) for raw_issue in parsed["issues"]],
                method="large_llm",
                model=self.large_model,
                needs_manual_review=bool(parsed.get("needs_manual_review", False)),
            ),
            response.usage,
        )

    def _chat_json(self, model: str, system_prompt: str, user_prompt: str) -> LLMJsonResponse:
        response = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("LLM 返回空内容。")
        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        actual_cost = getattr(usage, "cost", None)
        if actual_cost is not None:
            actual_cost = float(actual_cost)
        return LLMJsonResponse(
            text=content,
            usage=ProviderUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                actual_cost_usd=actual_cost,
            ),
        )


def live_sample_routed_groups(routed_groups: list[RoutedGroup], live_sample_size: int | None) -> list[RoutedGroup]:
    if live_sample_size is None:
        return routed_groups
    if live_sample_size == 0:
        return routed_groups
    if live_sample_size <= 0:
        raise ValueError("--live-sample-size 必须大于 0。")

    per_route = max(1, live_sample_size // 3)
    selected: list[RoutedGroup] = []
    selected_keys: set[str] = set()
    for route in ("rule", "small_llm", "large_llm"):
        route_items = [item for item in routed_groups if item.route == route]
        for item in route_items[:per_route]:
            selected.append(item)
            selected_keys.add(item.group.dedup_key)

    if len(selected) < live_sample_size:
        for item in routed_groups:
            if item.group.dedup_key in selected_keys:
                continue
            selected.append(item)
            selected_keys.add(item.group.dedup_key)
            if len(selected) >= live_sample_size:
                break

    return selected


def process_routed_groups(
    routed_groups: list[RoutedGroup],
    mode: Literal["offline", "live"],
    provider: Literal["openrouter", "deepseek"],
    small_model: str,
    large_model: str,
    batch_token_budget: int,
    max_cost_usd: float | None,
    live_sample_size: int | None,
    llm_concurrency: int = 8,
) -> tuple[dict[str, ExtractionResult], CostTracker, ProcessingStats, list[RoutedGroup]]:
    results: dict[str, ExtractionResult] = {}
    cost = CostTracker(max_cost_usd=max_cost_usd)
    active_routed_groups = live_sample_routed_groups(routed_groups, live_sample_size) if mode == "live" else routed_groups
    stats = ProcessingStats(
        live_sample_requested=live_sample_size if mode == "live" else None,
        live_sample_actual=len(active_routed_groups) if mode == "live" else None,
    )

    for routed in active_routed_groups:
        if routed.route != "rule":
            continue
        rule_result = apply_rule_engine(routed.group)
        if rule_result is None:
            raise RuntimeError("route=rule 但规则引擎未返回结果。")
        results[routed.group.dedup_key] = validate_result_for_text(
            rule_result,
            routed.group.representative_raw_text,
        )

    small_groups = [routed.group for routed in active_routed_groups if routed.route == "small_llm"]
    large_groups = [routed.group for routed in active_routed_groups if routed.route == "large_llm"]

    if mode == "offline":
        for group in small_groups:
            results[group.dedup_key] = fallback_unclear_result("small_llm", group.representative_raw_text)
        for group in large_groups:
            results[group.dedup_key] = fallback_unclear_result("large_llm", group.representative_raw_text)
        return results, cost, stats, active_routed_groups

    batches = build_small_batches(small_groups, token_budget=batch_token_budget)
    failed_small_groups: list[DedupGroup] = []

    def build_extractor() -> CompatibleLLMExtractor:
        return CompatibleLLMExtractor(provider=provider, small_model=small_model, large_model=large_model)

    def call_small_batch(batch: list[DedupGroup]) -> tuple[dict[str, ExtractionResult], ProviderUsage]:
        return build_extractor().call_small_batch(batch)

    def call_large_single(group: DedupGroup) -> tuple[ExtractionResult, ProviderUsage]:
        return build_extractor().call_large_single(group)

    def mark_small_fallback(batch: list[DedupGroup]) -> None:
        for group in batch:
            results[group.dedup_key] = fallback_unclear_result("small_llm", group.representative_raw_text)

    def mark_large_fallback(group: DedupGroup) -> None:
        results[group.dedup_key] = fallback_unclear_result("large_llm", group.representative_raw_text)

    def reserve_small_call(batch: list[DedupGroup]) -> bool:
        input_tokens = sum(estimate_tokens(group.representative_raw_text) + 80 for group in batch)
        output_tokens = max(200, len(batch) * 120)
        nonlocal cost, stats
        try:
            cost = cost.add_call("small", input_tokens=input_tokens, output_tokens=output_tokens)
        except RuntimeError:
            stats = stats.with_budget_exhausted()
            mark_small_fallback(batch)
            return False
        stats = stats.with_call()
        return True

    def reserve_large_call(group: DedupGroup) -> bool:
        input_tokens = estimate_tokens(group.representative_raw_text) + 180
        output_tokens = 450
        nonlocal cost, stats
        try:
            cost = cost.add_call("large", input_tokens=input_tokens, output_tokens=output_tokens)
        except RuntimeError:
            stats = stats.with_budget_exhausted()
            mark_large_fallback(group)
            return False
        stats = stats.with_call()
        return True

    concurrency = max(1, llm_concurrency)
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        small_futures = {}
        large_futures = {}

        for batch in batches:
            if stats.budget_exhausted:
                mark_small_fallback(batch)
                continue
            if reserve_small_call(batch):
                future = executor.submit(call_small_batch, batch)
                small_futures[future] = batch

        for group in large_groups:
            if stats.budget_exhausted:
                mark_large_fallback(group)
                continue
            if reserve_large_call(group):
                future = executor.submit(call_large_single, group)
                large_futures[future] = group

        for future in as_completed([*small_futures.keys(), *large_futures.keys()]):
            if future in small_futures:
                batch = small_futures[future]
                try:
                    batch_results, usage = future.result()
                    cost = cost.add_usage(usage)
                except (ValidationError, KeyError, TypeError, json.JSONDecodeError):
                    stats = stats.with_failure(schema_error=True)
                    failed_small_groups.extend(batch)
                    continue
                except Exception:
                    stats = stats.with_failure()
                    failed_small_groups.extend(batch)
                    continue

                for group in batch:
                    result = batch_results.get(group.dedup_key)
                    if result is None or result.min_confidence < MIN_CONFIDENCE:
                        failed_small_groups.append(group)
                        continue
                    try:
                        results[group.dedup_key] = validate_result_for_text(
                            result,
                            group.representative_raw_text,
                        )
                    except ValidationError:
                        stats = stats.with_failure(schema_error=True)
                        failed_small_groups.append(group)
                    except ValueError:
                        stats = stats.with_failure(evidence_error=True)
                        failed_small_groups.append(group)
                continue

            group = large_futures[future]
            try:
                result, usage = future.result()
                cost = cost.add_usage(usage)
                validated = validate_result_for_text(result, group.representative_raw_text)
                if validated.min_confidence < MIN_CONFIDENCE:
                    validated = validated.model_copy(update={"needs_manual_review": True})
                results[group.dedup_key] = validated
            except ValidationError:
                stats = stats.with_failure(schema_error=True)
                mark_large_fallback(group)
            except (KeyError, TypeError, json.JSONDecodeError):
                stats = stats.with_failure(schema_error=True)
                mark_large_fallback(group)
            except ValueError:
                stats = stats.with_failure(evidence_error=True)
                mark_large_fallback(group)
            except Exception:
                stats = stats.with_failure()
                mark_large_fallback(group)

        retry_small_groups: list[DedupGroup] = []
        for group in failed_small_groups:
            if should_retry_small_failure_as_large(group):
                retry_small_groups.append(group)
            else:
                mark_small_fallback([group])

        retry_futures = {}
        for group in retry_small_groups:
            if stats.budget_exhausted:
                mark_large_fallback(group)
                continue
            if reserve_large_call(group):
                future = executor.submit(call_large_single, group)
                retry_futures[future] = group

        for future in as_completed(retry_futures):
            group = retry_futures[future]
            try:
                result, usage = future.result()
                cost = cost.add_usage(usage)
                validated = validate_result_for_text(result, group.representative_raw_text)
                if validated.min_confidence < MIN_CONFIDENCE:
                    validated = validated.model_copy(update={"needs_manual_review": True})
                results[group.dedup_key] = validated
            except ValidationError:
                stats = stats.with_failure(schema_error=True)
                mark_large_fallback(group)
            except (KeyError, TypeError, json.JSONDecodeError):
                stats = stats.with_failure(schema_error=True)
                mark_large_fallback(group)
            except ValueError:
                stats = stats.with_failure(evidence_error=True)
                mark_large_fallback(group)
            except Exception:
                stats = stats.with_failure()
                mark_large_fallback(group)

    for group in large_groups + retry_small_groups:
        if group.dedup_key in results:
            continue
        if stats.budget_exhausted:
            mark_large_fallback(group)

    return results, cost, stats, active_routed_groups


def adapt_issues_to_record(issues: list[Issue], raw_text: str) -> list[dict[str, Any]]:
    adapted: list[dict[str, Any]] = []
    for raw_issue in issues:
        evidence = raw_issue.evidence
        if not contains_evidence(raw_text, evidence):
            evidence = raw_excerpt(raw_text) if raw_text else ""
        adapted.append(raw_issue.model_copy(update={"evidence": evidence}).model_dump())
    return adapted


def expand_results(
    groups: list[DedupGroup],
    results_by_dedup_key: dict[str, ExtractionResult],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for group in groups:
        result = results_by_dedup_key[group.dedup_key]
        for record in group.records:
            records.append(
                {
                    "review_id": record.review_id,
                    "order_id": record.order_id,
                    "review_score": record.review_score,
                    "raw_text": record.raw_text,
                    "normalized_text_hash": record.normalized_text_hash,
                    "issues": adapt_issues_to_record(result.issues, record.raw_text),
                    "method": result.method,
                    "model": result.model,
                    "needs_manual_review": result.needs_manual_review,
                }
            )
    return records


def representative_groups(groups: list[DedupGroup]) -> list[DedupGroup]:
    return [replace(group, records=(group.records[0],)) for group in groups]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_cost_report(payload: dict[str, Any]) -> str:
    metadata = payload["metadata"]
    route_counts = metadata["route_counts"]
    active_route_counts = metadata["active_route_counts"]
    method_counts = metadata["method_counts"]
    cost_label = "实际成本" if metadata["actual_cost_usd"] is not None else "估算成本"
    cost_value = metadata["actual_cost_usd"] if metadata["actual_cost_usd"] is not None else metadata["estimated_cost_usd"]
    max_cost_label = "不设限" if metadata["max_cost_usd"] is None else f"${metadata['max_cost_usd']:.2f}"
    return f"""# Q4 成本报告

## 执行模式

- 模式：`{metadata["mode"]}`
- live LLM 是否调用：`{"是" if metadata["mode"] == "live" else "否"}`
- Provider：`{metadata["provider"] or "none"}`
- Small model：`{metadata["small_model"] or "none"}`
- Large model：`{metadata["large_model"] or "none"}`
- 成本上限：`{max_cost_label}`
- {cost_label}：`${cost_value:.6f}`
- 估算输入/输出 tokens：`{metadata["estimated_input_tokens"]}` / `{metadata["estimated_output_tokens"]}`
- 服务端返回输入/输出 tokens：`{metadata["actual_input_tokens"]}` / `{metadata["actual_output_tokens"]}`
- LLM 调用次数：`{metadata["llm_call_count"]}`
- LLM 失败次数：`{metadata["failed_llm_count"]}`
- budget_exhausted：`{metadata["budget_exhausted"]}`

默认运行使用 offline 模式，因此 `python run_all.py` 或 `uv run python run_all.py` 不会因为缺少 API key 失败，也不会产生模型费用。需要真实调用模型时，必须显式传入 `--mode live` 并配置 `OPENROUTER_API_KEY` 或 `DEEPSEEK_API_KEY`。live 模式默认只抽样验证 DeepSeek/OpenRouter 模型路径，不直接全量调用所有 LLM 路由。

## 样本量与分流

| 指标 | 数量 |
|---|---:|
| 低分评论数 | {metadata["record_count"]} |
| 空文本低分评论数 | {metadata["empty_text_count"]} |
| 去重后文本数 | {metadata["dedup_count"]} |
| Rule Engine 路由 | {route_counts.get("rule", 0)} |
| Small LLM 路由 | {route_counts.get("small_llm", 0)} |
| Large LLM 路由 | {route_counts.get("large_llm", 0)} |

## 本次实际处理路由

| 指标 | 数量 |
|---|---:|
| live_sample_requested | {metadata["live_sample_requested"] or 0} |
| live_sample_actual | {metadata["live_sample_actual"] or 0} |
| Rule Engine 实际处理 | {active_route_counts.get("rule", 0)} |
| Small LLM 实际处理 | {active_route_counts.get("small_llm", 0)} |
| Large LLM 实际处理 | {active_route_counts.get("large_llm", 0)} |

## 实际处理方式

| method | 数量 |
|---|---:|
{chr(10).join(f"| `{method}` | {count} |" for method, count in sorted(method_counts.items()))}

## 成本控制说明

1. 只处理 `review_score <= 3` 的评论。
2. 对 `normalized_text` 做精确去重，模型只需要处理代表文本。
3. 空评论、极短评论和高置信度模板由本地规则处理。
4. 短文本才进入 Small LLM batch；复杂长文本或低置信度结果才升级到 Large LLM。
5. live 模式下每次调用前都会做 token 估算；如果设置了成本上限，预计成本超过上限会停止；如果传入 `--no-cost-limit`，则不做本地预算 gate。

本次 offline 输出中，Small/Large LLM 路由样本被标记为 `general.unclear` 和 `needs_manual_review=true`，用于保证一键运行可复现、零成本。
"""


def write_cost_report(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(build_cost_report(payload), encoding="utf-8")




def write_accuracy_evaluation(path: Path, payload: dict[str, Any]) -> None:
    route_counts = payload["metadata"]["route_counts"]
    path.write_text(
        f"""# Q4 准确率评估方法

由于 Olist 评论没有现成 ground truth，本模块采用分层抽样人工评估，而不是只随机抽样最终结果。建议从输出中抽 30 条：

| 分层 | 抽样数 | 检查重点 |
|---|---:|---|
| Rule Engine | 10 | 模板是否误判、低信息评论是否被过度解释 |
| Small LLM 路由 | 10 | 短评论主问题是否分类正确、evidence 是否来自原文 |
| Large LLM 路由 | 10 | 多问题召回、复杂语义和时间线是否漏抽 |

本次运行的路由分布为：Rule `{route_counts.get("rule", 0)}`、Small LLM `{route_counts.get("small_llm", 0)}`、Large LLM `{route_counts.get("large_llm", 0)}`。如果某一层不足 10 条，则从相邻模型层补足，但评估表中必须记录来源。

人工标注字段：

1. `category/subcategory` 是否正确。
2. `evidence` 是否为原文中的连续片段。
3. 是否漏掉主要问题。
4. 是否需要人工复核。

准确率计算：

- 分类准确率 = 分类正确条数 / 抽样条数。
- evidence 合规率 = evidence 在原文中且能支持分类的条数 / 抽样条数。
- 漏召回率 = 漏掉主要问题的条数 / 抽样条数。

如果规则误判集中出现，优先修正规则；如果 evidence 不合规集中出现在 LLM 路径，优先收紧 prompt 和 schema 校验，而不是直接升级模型。
""",
        encoding="utf-8",
    )


def run_pipeline(
    input_path: Path = DEFAULT_INPUT_PATH,
    output_path: Path = DEFAULT_OUTPUT_PATH,
    mode: Literal["offline", "live"] = "offline",
    provider: Literal["openrouter", "deepseek"] = DEFAULT_PROVIDER,
    small_model: str | None = None,
    large_model: str | None = None,
    batch_token_budget: int = 6000,
    max_cost_usd: float | None = 3.0,
    live_sample_size: int | None = None,
    llm_concurrency: int = 8,
    write_docs: bool = True,
) -> dict[str, Any]:
    load_dotenv_if_available()
    resolved_small_model = small_model or default_small_model(provider)
    resolved_large_model = large_model or default_large_model(provider)
    records = load_low_score_reviews(input_path)
    groups = deduplicate_reviews(records)
    routed_groups = [route_group(group) for group in groups]
    route_counts = Counter(routed.route for routed in routed_groups)

    results_by_dedup_key, cost, stats, active_routed_groups = process_routed_groups(
        routed_groups=routed_groups,
        mode=mode,
        provider=provider,
        small_model=resolved_small_model,
        large_model=resolved_large_model,
        batch_token_budget=batch_token_budget,
        max_cost_usd=max_cost_usd,
        live_sample_size=live_sample_size,
        llm_concurrency=llm_concurrency,
    )

    active_groups = [routed.group for routed in active_routed_groups]
    output_groups = representative_groups(active_groups) if mode == "live" else active_groups
    active_route_counts = Counter(routed.route for routed in active_routed_groups)
    expanded_records = expand_results(output_groups, results_by_dedup_key)
    method_counts = Counter(record["method"] for record in expanded_records)
    payload = {
        "metadata": {
            "source": str(input_path.relative_to(ROOT_DIR) if input_path.is_relative_to(ROOT_DIR) else input_path),
            "filter": f"review_score <= {LOW_SCORE_THRESHOLD}",
            "language": "pt-BR",
            "pipeline_version": PIPELINE_VERSION,
            "mode": mode,
            "provider": provider if mode == "live" else None,
            "record_count": len(records),
            "empty_text_count": sum(1 for record in records if record.raw_text == ""),
            "dedup_count": len(groups),
            "route_counts": dict(route_counts),
            "active_route_counts": dict(active_route_counts),
            "method_counts": dict(method_counts),
            "max_cost_usd": max_cost_usd,
            "estimated_cost_usd": round(cost.estimated_cost_usd, 6),
            "actual_cost_usd": round(cost.actual_cost_usd, 6) if cost.actual_cost_usd is not None else None,
            "estimated_input_tokens": cost.estimated_input_tokens,
            "estimated_output_tokens": cost.estimated_output_tokens,
            "actual_input_tokens": cost.actual_input_tokens,
            "actual_output_tokens": cost.actual_output_tokens,
            "small_model": resolved_small_model if mode == "live" else None,
            "large_model": resolved_large_model if mode == "live" else None,
            "live_sample_requested": stats.live_sample_requested,
            "live_sample_actual": stats.live_sample_actual,
            "llm_call_count": stats.llm_call_count,
            "failed_llm_count": stats.failed_llm_count,
            "schema_error_count": stats.schema_error_count,
            "evidence_error_count": stats.evidence_error_count,
            "budget_exhausted": stats.budget_exhausted,
        },
        "records": expanded_records,
    }

    write_json(output_path, payload)
    if write_docs:
        write_cost_report(DEFAULT_COST_REPORT_PATH, payload)
        write_accuracy_evaluation(DEFAULT_ACCURACY_PATH, payload)

    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Q4 低分评论结构化抽取 pipeline")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--mode", choices=["offline", "live"], default=os.getenv("Q4_MODE", "offline"))
    parser.add_argument("--provider", choices=["openrouter", "deepseek"], default=os.getenv("Q4_PROVIDER", DEFAULT_PROVIDER))
    parser.add_argument("--small-model", default=os.getenv("Q4_SMALL_MODEL"))
    parser.add_argument("--large-model", default=os.getenv("Q4_LARGE_MODEL"))
    parser.add_argument("--batch-token-budget", type=int, default=int(os.getenv("Q4_BATCH_TOKEN_BUDGET", "6000")))
    parser.add_argument("--llm-concurrency", type=int, default=int(os.getenv("Q4_LLM_CONCURRENCY", "8")))
    parser.add_argument("--max-cost-usd", type=float, default=float(os.getenv("Q4_MAX_COST_USD", "3.0")))
    parser.add_argument(
        "--no-cost-limit",
        action="store_true",
        help="live 模式不做本地预算 gate；会真实调用所有进入 LLM 路由的样本。",
    )
    parser.add_argument(
        "--live-sample-size",
        type=int,
        default=int(os.getenv("Q4_LIVE_SAMPLE_SIZE", "30")),
        help="live 模式抽样验证模型路径；传 0 表示全量 live，不抽样。offline 模式忽略该参数。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = args.output
    if output_path is None:
        output_path = DEFAULT_LIVE_OUTPUT_PATH if args.mode == "live" else DEFAULT_OUTPUT_PATH
    payload = run_pipeline(
        input_path=args.input,
        output_path=output_path,
        mode=args.mode,
        provider=args.provider,
        small_model=args.small_model,
        large_model=args.large_model,
        batch_token_budget=args.batch_token_budget,
        max_cost_usd=None if args.no_cost_limit else args.max_cost_usd,
        live_sample_size=args.live_sample_size if args.mode == "live" else None,
        llm_concurrency=args.llm_concurrency,
    )
    metadata = payload["metadata"]
    print(
        "[OK] Q4 抽取完成："
        f"低分评论 {metadata['record_count']} 条，"
        f"去重 {metadata['dedup_count']} 条，"
        f"输出 {len(payload['records'])} 条 -> {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
