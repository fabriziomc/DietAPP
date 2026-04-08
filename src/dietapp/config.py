from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv:
    load_dotenv()


SUPPORTED_AI_PROVIDERS = ("openai", "groq", "openrouter")


@dataclass(slots=True)
class AppConfig:
    ai_provider: str = "openai"
    openai_api_key: str | None = None
    groq_api_key: str | None = None
    openrouter_api_key: str | None = None
    openai_model: str = "gpt-4.1-mini"
    groq_model: str = "llama-3.3-70b-versatile"
    openrouter_model: str = "google/gemma-4-31b-it:free"
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

        return cls(
            ai_provider=provider,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            groq_api_key=os.getenv("GROQ_API_KEY") or None,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
            groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            openrouter_model=os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free"),
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
        selected_provider = (provider or self.ai_provider or "").strip().lower()
        if selected_provider not in SUPPORTED_AI_PROVIDERS:
            selected_provider = ""

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
        selected_provider = self.normalize_provider(provider)
        if selected_provider == "groq":
            return self.groq_api_key or None
        if selected_provider == "openrouter":
            return self.openrouter_api_key or None
        return self.openai_api_key or None

    def get_model(self, provider: str | None = None) -> str:
        selected_provider = self.normalize_provider(provider)
        if selected_provider == "groq":
            return self.groq_model
        if selected_provider == "openrouter":
            return self.openrouter_model
        return self.openai_model

    def get_base_url(self, provider: str | None = None) -> str | None:
        selected_provider = self.normalize_provider(provider)
        if selected_provider == "groq":
            return "https://api.groq.com/openai/v1"
        if selected_provider == "openrouter":
            return "https://openrouter.ai/api/v1"
        return None

    def get_default_headers(self, provider: str | None = None) -> dict[str, str] | None:
        selected_provider = self.normalize_provider(provider)
        if selected_provider != "openrouter":
            return None

        headers: dict[str, str] = {}
        if self.openrouter_site_url:
            headers["HTTP-Referer"] = self.openrouter_site_url
        if self.openrouter_app_name:
            headers["X-OpenRouter-Title"] = self.openrouter_app_name
        return headers or None

    def get_provider_label(self, provider: str | None = None) -> str:
        selected_provider = self.normalize_provider(provider)
        if selected_provider == "groq":
            return "Groq"
        if selected_provider == "openrouter":
            return "OpenRouter"
        return "OpenAI"
