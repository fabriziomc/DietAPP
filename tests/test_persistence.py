from __future__ import annotations

from dietapp.auth import AuthSession
from dietapp.config import AppConfig
from dietapp.models import (
    DayPlan,
    HouseholdPreferences,
    MealSlot,
    MealVariant,
    PersonProfile,
    PersonWellnessStrategy,
    PlanningRequest,
    WeeklyPlan,
    WellnessStrategy,
)
from dietapp.persistence import (
    clear_planning_state_from_supabase,
    load_planning_state_from_supabase,
    load_profile_form_values,
    load_profile_form_values_from_supabase,
    save_planning_state_to_supabase,
    save_profile_form_values_to_supabase,
)
from dietapp.planner import DietResult, StrategyResult


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, store: dict[str, dict]):
        self.store = store
        self.user_id = ""
        self.payload = None
        self.operation = ""

    def select(self, _columns: str) -> "FakeTable":
        self.operation = "select"
        return self

    def eq(self, _field: str, user_id: str) -> "FakeTable":
        self.user_id = user_id
        return self

    def limit(self, _value: int) -> "FakeTable":
        return self

    def upsert(self, payload: dict, on_conflict: str | None = None) -> "FakeTable":
        assert on_conflict == "user_id"
        self.operation = "upsert"
        self.payload = payload
        return self

    def execute(self) -> FakeResponse:
        if self.operation == "select":
            row = self.store.get(self.user_id)
            return FakeResponse([row] if row else [])

        assert self.payload is not None
        existing = self.store.get(self.payload["user_id"], {})
        merged = {**existing, **self.payload}
        self.store[self.payload["user_id"]] = merged
        return FakeResponse([merged])


class FakeSupabaseClient:
    def __init__(self):
        self.store: dict[str, dict] = {}

    def table(self, _table_name: str) -> FakeTable:
        return FakeTable(self.store)


def test_app_config_detects_supabase_setup() -> None:
    config = AppConfig(
        supabase_url="https://example.supabase.co",
        supabase_anon_key="anon-key",
    )

    assert config.has_supabase() is True


def test_auth_session_from_dict_requires_tokens_and_user() -> None:
    session = AuthSession.from_dict(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "user_id": "user-1",
            "email": "user@example.com",
        }
    )

    assert session is not None
    assert session.email == "user@example.com"
    assert AuthSession.from_dict({"access_token": "missing-fields"}) is None


def test_profile_values_are_persisted_to_supabase_backend() -> None:
    client = FakeSupabaseClient()

    save_profile_form_values_to_supabase(
        {
            "person_one_name": "Fabrizio",
            "person_one_style": "Onnivoro",
            "person_one_age": 39,
            "person_one_sex": "Uomo",
            "person_one_height_cm": 178,
            "person_one_weight_kg": 82.0,
            "person_one_target_weight_kg": 77.5,
            "person_one_allow_protein_powder": True,
            "person_one_activity": "Palestra 3 volte a settimana",
            "person_one_dislikes": "finocchi",
            "person_one_allergies": "",
            "person_two_name": "Sara",
            "person_two_style": "Vegetariano",
            "person_two_age": 35,
            "person_two_sex": "Donna",
            "person_two_height_cm": 165,
            "person_two_weight_kg": 63.0,
            "person_two_target_weight_kg": 66.0,
            "person_two_allow_protein_powder": False,
            "person_two_activity": "Yoga e camminate",
            "person_two_dislikes": "olive",
            "person_two_allergies": "",
            "budget": "Bilanciato",
            "max_prep_minutes": 25,
            "leftover_lunches": 4,
            "batch_days": ["Domenica"],
            "cuisines": ["Mediterranea"],
            "pantry_staples": ["Riso", "Uova"],
            "excluded_ingredients": "broccoli",
            "notes": "Batch cooking la domenica.",
        },
        client,
        "user-1",
    )

    loaded = load_profile_form_values_from_supabase(client, "user-1")

    assert loaded["person_one_name"] == "Fabrizio"
    assert loaded["person_two_name"] == "Sara"
    assert loaded["person_one_target_weight_kg"] == 77.5
    assert loaded["person_two_target_weight_kg"] == 66.0
    assert loaded["person_one_allow_protein_powder"] is True
    assert loaded["person_two_allow_protein_powder"] is False
    assert loaded["leftover_lunches"] == 4
    assert loaded["batch_days"] == ["Domenica"]


def test_planning_state_is_persisted_and_restored_from_supabase_backend() -> None:
    client = FakeSupabaseClient()

    request_payload = PlanningRequest(
        person_one=PersonProfile(
            name="Fabrizio",
            dietary_style="Onnivoro",
            age=39,
            sex="Uomo",
            height_cm=178,
            weight_kg=82.0,
            target_weight_kg=77.5,
            allow_protein_powder=True,
            activity_summary="Palestra e camminate",
        ),
        person_two=PersonProfile(
            name="Sara",
            dietary_style="Vegetariano",
            age=35,
            sex="Donna",
            height_cm=165,
            weight_kg=63.0,
            target_weight_kg=66.0,
            allow_protein_powder=False,
            activity_summary="Yoga e camminate",
        ),
        preferences=HouseholdPreferences(
            goal="",
            budget="Bilanciato",
            max_prep_minutes=30,
            leftover_lunches=3,
            batch_days=["Domenica"],
            favorite_cuisines=["Mediterranea"],
            pantry_staples=["Riso", "Uova"],
            excluded_ingredients=["broccoli"],
            notes="Batch la domenica.",
        ),
    )
    strategy_result = StrategyResult(
        strategy=WellnessStrategy(
            title="Settimana sostenibile",
            couple_summary="Base comune e split finale.",
            shared_principles=["Piatti semplici"],
            kitchen_principles=["Batch cooking"],
            person_one=PersonWellnessStrategy(
                focus="Ricompensa corporea",
                rationale="Piu proteine nei giorni attivi.",
                daily_kcal_target=2200,
                protein_target_g=140,
                movement_guidance="Mantieni 3 allenamenti.",
                nutrition_guidance=["Colazione proteica"],
            ),
            person_two=PersonWellnessStrategy(
                focus="Equilibrio energetico",
                rationale="Proteine distribuite nella giornata.",
                daily_kcal_target=1800,
                protein_target_g=95,
                movement_guidance="Yoga e passi quotidiani.",
                nutrition_guidance=["Legumi 4 volte"],
            ),
            model_source="test-suite",
        ),
        source_label="Planner locale",
        warning="warning di test",
    )
    diet_result = DietResult(
        plan=WeeklyPlan(
            title="Piano test",
            strategy="Strategia condivisa",
            prep_tasks=["Cuoci il riso"],
            planning_notes=["Riusa le verdure"],
            shopping_list={"Dispensa": ["Riso", "Ceci"]},
            days=[
                DayPlan(
                    day="Lunedi",
                    breakfast=MealSlot(
                        shared_base="Yogurt e avena",
                        person_one=MealVariant("Bowl 1", "Versione onnivora", ["yogurt"], "5 min"),
                        person_two=MealVariant("Bowl 2", "Versione vegetariana", ["yogurt"], "5 min"),
                        prep_minutes=5,
                        leftover_friendly=False,
                    ),
                    lunch=MealSlot(
                        shared_base="Insalata di riso",
                        person_one=MealVariant("Riso con pollo", "Proteico", ["riso", "pollo"], "10 min"),
                        person_two=MealVariant("Riso con ceci", "Vegetariano", ["riso", "ceci"], "10 min"),
                        prep_minutes=10,
                        leftover_friendly=True,
                        reuse_from_previous="Riso cotto domenica",
                    ),
                    dinner=MealSlot(
                        shared_base="Verdure al forno",
                        person_one=MealVariant("Pollo e verdure", "Forno", ["pollo"], "20 min"),
                        person_two=MealVariant("Tofu e verdure", "Forno", ["tofu"], "20 min"),
                        prep_minutes=20,
                        leftover_friendly=True,
                        kitchen_load="Medio",
                    ),
                    source="AI",
                )
            ],
            model_source="test-suite",
        ),
        source_label="Groq | llama-test",
        warning=None,
    )

    save_planning_state_to_supabase(
        request_payload,
        strategy_result,
        diet_result,
        client,
        "user-1",
    )

    loaded = load_planning_state_from_supabase(client, "user-1")

    assert loaded is not None
    assert loaded.request_payload.person_one.name == "Fabrizio"
    assert loaded.request_payload.person_one.target_weight_kg == 77.5
    assert loaded.request_payload.person_two.target_weight_kg == 66.0
    assert loaded.request_payload.person_one.allow_protein_powder is True
    assert loaded.request_payload.person_two.allow_protein_powder is False
    assert loaded.strategy_result.strategy.person_two.protein_target_g == 95
    assert loaded.diet_result is not None
    assert loaded.diet_result.plan.days[0].lunch.person_two.title == "Riso con ceci"
    assert loaded.diet_result.plan.days[0].source == "AI"
    assert loaded.diet_result.source_label == "Groq | llama-test"


def test_legacy_profile_without_target_weight_defaults_to_current_weight(tmp_path: Path) -> None:
    profile_path = tmp_path / "household_profile.json"
    profile_path.write_text(
        """
{
  "person_one_name": "Fabrizio",
  "person_one_weight_kg": 82.0,
  "person_two_name": "Sara",
  "person_two_weight_kg": 63.0
}
""".strip(),
        encoding="utf-8",
    )

    loaded = load_profile_form_values(profile_path)

    assert loaded["person_one_target_weight_kg"] == 82.0
    assert loaded["person_two_target_weight_kg"] == 63.0
    assert loaded["person_one_allow_protein_powder"] is False
    assert loaded["person_two_allow_protein_powder"] is False