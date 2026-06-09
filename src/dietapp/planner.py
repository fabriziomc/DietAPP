from __future__ import annotations

from typing import Any

from dietapp.config import AppConfig
from dietapp.models import PlanningRequest, WeeklyPlan, WellnessStrategy
from dietapp.planning.ai import (
    _apply_strategy_targets,
    _build_local_provider_warning,
    _build_partial_ai_plan_warning,
    _build_provider_failure,
    _build_provider_recovery_warning,
    _build_provider_source_label,
    _generate_staged_ai_plan,
    _build_strategy_ai_prompt,
    _format_prompt_preview,
    _format_provider_exception,
    _normalize_ai_plan,
    _normalize_wellness_strategy,
    build_plan_prompt_preview,
    build_strategy_prompt_preview,
)
from dietapp.planning.ai import (
    _call_llm_json as _call_llm_json_impl,
)
from dietapp.planning.common import (
    AI_PLAN_MAX_TOKENS,
    AI_STRATEGY_MAX_TOKENS,
    PLAN_SYSTEM_PROMPT,
    STRATEGY_SYSTEM_PROMPT,
    DietResult,
    PlanResult,
    ProviderFailure,
    StrategyResult,
    _build_bundle_source_label,
)
from dietapp.planning.fallback_plan import generate_fallback_plan as _generate_fallback_plan_impl
from dietapp.planning.strategy import (
    generate_fallback_wellness_strategy as _generate_fallback_wellness_strategy_impl,
)

OpenAI: Any = None

try:
    from openai import OpenAI as _OpenAI
except ImportError:
    pass
else:
    OpenAI = _OpenAI


def generate_weekly_plan(request: PlanningRequest, config: AppConfig) -> PlanResult:
    strategy_result = generate_wellness_strategy(request, config)
    diet_result = generate_diet_from_strategy(request, strategy_result.strategy, config)
    source_label = _build_bundle_source_label(strategy_result.source_label, diet_result.source_label)
    warnings = [warning for warning in (strategy_result.warning, diet_result.warning) if warning]
    return PlanResult(
        plan=diet_result.plan,
        strategy=strategy_result.strategy,
        source_label=source_label,
        warning="\n\n".join(warnings) if warnings else None,
    )


def generate_wellness_strategy(request: PlanningRequest, config: AppConfig) -> StrategyResult:
    failures: list[ProviderFailure] = []
    for provider in config.get_provider_attempt_order():
        try:
            strategy = _generate_ai_wellness_strategy(request, config, provider)
            source_label = _build_provider_source_label(config, provider)
            return StrategyResult(
                strategy=strategy,
                source_label=source_label,
                warning=_build_provider_recovery_warning(
                    "Strategia benessere",
                    failures,
                    source_label,
                ),
            )
        except Exception as exc:
            failures.append(_build_provider_failure(exc, config, provider))

    fallback_strategy = generate_fallback_wellness_strategy(request)
    return StrategyResult(
        strategy=fallback_strategy,
        source_label="Planner locale",
        warning=_build_local_provider_warning(
            "Strategia benessere",
            failures,
            "Ho usato il motore locale.",
        ),
    )


def generate_diet_from_strategy(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    config: AppConfig,
) -> DietResult:
    enriched_request = _apply_strategy_targets(request, strategy)
    failures: list[ProviderFailure] = []
    for provider in config.get_provider_attempt_order():
        try:
            plan = _generate_ai_plan(enriched_request, strategy, config, provider)
            source_label = _build_provider_source_label(config, provider)
            warning = _combine_warnings(
                _build_provider_recovery_warning(
                    "Dieta settimanale",
                    failures,
                    source_label,
                ),
                _build_partial_ai_plan_warning(plan, source_label),
            )
            return DietResult(
                plan=plan,
                source_label=source_label,
                warning=warning,
            )
        except Exception as exc:
            failures.append(_build_provider_failure(exc, config, provider))

    fallback_plan = generate_fallback_plan(enriched_request, strategy)
    return DietResult(
        plan=fallback_plan,
        source_label="Planner locale",
        warning=_build_local_provider_warning(
            "Dieta settimanale",
            failures,
            "Ho creato il piano con il motore locale.",
        ),
    )


def generate_fallback_wellness_strategy(request: PlanningRequest) -> WellnessStrategy:
    return _generate_fallback_wellness_strategy_impl(request)


def generate_fallback_plan(
    request: PlanningRequest,
    strategy: WellnessStrategy | None = None,
) -> WeeklyPlan:
    return _generate_fallback_plan_impl(request, strategy)


def _generate_ai_wellness_strategy(
    request: PlanningRequest,
    config: AppConfig,
    provider: str | None = None,
) -> WellnessStrategy:
    raw_strategy = _call_llm_json(
        config,
        STRATEGY_SYSTEM_PROMPT,
        _build_strategy_ai_prompt(request),
        max_tokens=AI_STRATEGY_MAX_TOKENS,
        provider=provider,
    )
    return _normalize_wellness_strategy(
        raw_strategy,
        request,
        _build_provider_source_label(config, provider),
    )


def _generate_ai_plan(
    request: PlanningRequest,
    strategy: WellnessStrategy,
    config: AppConfig,
    provider: str | None = None,
) -> WeeklyPlan:
    return _generate_staged_ai_plan(
        lambda system_prompt, user_prompt, max_tokens: _call_llm_json(
            config,
            system_prompt,
            user_prompt,
            max_tokens=max_tokens,
            provider=provider,
        ),
        request,
        strategy,
        _build_provider_source_label(config, provider),
    )


def _call_llm_json(
    config: AppConfig,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    return _call_llm_json_impl(
        OpenAI,
        config,
        system_prompt,
        user_prompt,
        max_tokens=max_tokens,
        provider=provider,
    )


def _combine_warnings(*messages: str | None) -> str | None:
    resolved_messages = [message for message in messages if message]
    return "\n\n".join(resolved_messages) if resolved_messages else None


__all__ = [
    "AI_PLAN_MAX_TOKENS",
    "AI_STRATEGY_MAX_TOKENS",
    "PLAN_SYSTEM_PROMPT",
    "STRATEGY_SYSTEM_PROMPT",
    "DietResult",
    "OpenAI",
    "PlanResult",
    "ProviderFailure",
    "StrategyResult",
    "_call_llm_json",
    "_format_prompt_preview",
    "_format_provider_exception",
    "_generate_ai_plan",
    "_generate_ai_wellness_strategy",
    "_normalize_ai_plan",
    "build_plan_prompt_preview",
    "build_strategy_prompt_preview",
    "generate_diet_from_strategy",
    "generate_fallback_plan",
    "generate_fallback_wellness_strategy",
    "generate_weekly_plan",
    "generate_wellness_strategy",
]
