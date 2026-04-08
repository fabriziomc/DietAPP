from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_OPENROUTER_FALLBACK_MODELS = (
    "meta-llama/llama-3.3-70b-instruct:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "openai/gpt-oss-120b:free",
)


def _split_csv_env(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    return tuple(item.strip() for item in raw_value.split(",") if item.strip())

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


SUPPORTED_AI_PROVIDERS = ("openai", "groq", "openrouter")


def _coerce_provider_name(provider: str | None) -> str:
    normalized = (provider or "").strip().lower()
    return normalized if normalized in SUPPORTED_AI_PROVIDERS else ""


@dataclass(slots=True)
class AppConfig:
    ai_provider: str = "openai"
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_model: str = "google/gemma-4-31b-it:free"
    openrouter_fallback_models: tuple[str, ...] = DEFAULT_OPENROUTER_FALLBACK_MODELS
    openrouter_site_url: str | None = None
    openrouter_app_name: str | None = None
    supabase_url: str | None = None
    supabase_anon_key: str | None = None
    supabase_profile_table: str = "user_profiles"
    supabase_auth_redirect_url: str | None = None

    @classmethod
    def from_env(cls) -> "AppConfig":
        provider = (os.getenv("AI_PROVIDER") or "").strip().lower()
        if provider not in SUPPORTED_AI_PROVIDERS:
            if os.getenv("GROQ_API_KEY"):
                provider = "groq"
            elif os.getenv("OPENROUTER_API_KEY"):
                provider = "openrouter"
            elif os.getenv("OPENAI_API_KEY"):
                provider = "openai"
            else:
                provider = "openai"

        fallback_models_raw = os.getenv("OPENROUTER_FALLBACK_MODELS")
        fallback_models = (
            _split_csv_env(fallback_models_raw)
            if fallback_models_raw is not None
            else DEFAULT_OPENROUTER_FALLBACK_MODELS
        )

        return cls(
            ai_provider=provider,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free"),
            openrouter_fallback_models=fallback_models,
            openrouter_site_url=os.getenv("OPENROUTER_SITE_URL") or None,
            openrouter_app_name=os.getenv("OPENROUTER_APP_NAME") or None,
            supabase_url=os.getenv("SUPABASE_URL") or None,
            supabase_anon_key=os.getenv("SUPABASE_ANON_KEY") or None,
            supabase_profile_table=os.getenv("SUPABASE_PROFILE_TABLE", "user_profiles"),
            supabase_auth_redirect_url=os.getenv("SUPABASE_AUTH_REDIRECT_URL") or None,
        )

    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_anon_key)

    def normalize_provider(self, provider: str | None = None) -> str:
        selected_provider = _coerce_provider_name(provider or self.ai_provider)

        if selected_provider == "groq" and self.groq_api_key:
            return "groq"
        if selected_provider == "openrouter" and self.openrouter_api_key:
            return "openrouter"
        if selected_provider == "openai" and self.openai_api_key:
            return "openai"
        if self.groq_api_key:
            return "groq"
        if self.openrouter_api_key:
            return "openrouter"
        if self.openai_api_key:
            return "openai"
        if selected_provider:
            return selected_provider
        return "openai"

    def get_api_key(self, provider: str | None = None) -> str | None:
        selected_provider = _coerce_provider_name(provider) if provider is not None else self.normalize_provider()
        if selected_provider == "groq":
            return self.groq_api_key or None
        if selected_provider == "openrouter":
            return self.openrouter_api_key or None
        if selected_provider == "openai":
            return self.openai_api_key or None
        return None

    def get_model(self, provider: str | None = None) -> str:
        selected_provider = _coerce_provider_name(provider) if provider is not None else self.normalize_provider()
        if selected_provider == "groq":
            return self.groq_model
        if selected_provider == "openrouter":
            return self.openrouter_model
        return self.openai_model

    def get_base_url(self, provider: str | None = None) -> str | None:
        selected_provider = _coerce_provider_name(provider) if provider is not None else self.normalize_provider()
        if selected_provider == "groq":
            return "https://api.groq.com/openai/v1"
        if selected_provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        return None

    def get_default_headers(self, provider: str | None = None) -> dict[str, str] | None:
        selected_provider = _coerce_provider_name(provider) if provider is not None else self.normalize_provider()
        if selected_provider != "openrouter":
            return None

        headers: dict[str, str] = {}
        if self.openrouter_site_url:
            headers["HTTP-Referer"] = self.openrouter_site_url
        if self.openrouter_app_name:
            headers["X-OpenRouter-Title"] = self.openrouter_app_name
        return headers or None

    def get_model_fallbacks(self, provider: str | None = None) -> tuple[str, ...]:
        selected_provider = _coerce_provider_name(provider) if provider is not None else self.normalize_provider()
        if selected_provider != "openrouter":
            return ()

        primary_model = self.get_model(selected_provider)
        fallbacks: list[str] = []
        for candidate in self.openrouter_fallback_models:
            normalized = str(candidate).strip()
            if not normalized or normalized == primary_model or normalized in fallbacks:
                continue
            fallbacks.append(normalized)
        return tuple(fallbacks)

    def get_provider_attempt_order(self) -> tuple[str, ...]:
        selected_provider = _coerce_provider_name(self.ai_provider)
        if selected_provider == "openrouter":
            ordered = []
            if self.openrouter_api_key:
                ordered.append("openrouter")
            if self.groq_api_key:
                ordered.append("groq")
            return tuple(ordered)
        if selected_provider == "groq":
            return ("groq",) if self.groq_api_key else ()
        if selected_provider == "openai":
            return ("openai",) if self.openai_api_key else ()

        normalized = self.normalize_provider()
        if self.get_api_key(normalized):
            return (normalized,)
        return ()

    def get_provider_label(self, provider: str | None = None) -> str:
        selected_provider = _coerce_provider_name(provider) if provider is not None else self.normalize_provider()
        if selected_provider == "groq":
            return "Groq"
        if selected_provider == "openrouter":
            return "OpenRouter"
        return "OpenAI"
