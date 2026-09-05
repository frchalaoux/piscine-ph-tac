"""Chargement et validation des valeurs opérationnelles par défaut.

Le fichier :mod:`piscine_ph.defaults.json` contient les valeurs propres au
protocole par défaut (bassin, objectifs et portions indicatives). Les constantes
physico-chimiques restent dans ``chemistry.py`` : elles font partie du modèle et
ne doivent pas être rendues modifiables par simple édition d'un JSON.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

from pydantic import BaseModel, Field, model_validator


class ProtocolDefaults(BaseModel):
    """Valeurs par défaut d'un bassin, avec les unités des champs de protocole."""

    pool_volume_m3: float = Field(gt=0, description="Volume du bassin en m3.")
    initial_ph: float = Field(gt=0, lt=14, description="pH de départ mesuré.")
    intermediate_ph: float = Field(gt=0, lt=14, description="Palier pH avant le TAC.")
    target_ph: float = Field(gt=0, lt=14, description="pH final demandé.")
    initial_tac_ppm: float = Field(gt=0, description="TAC initial en ppm CaCO3.")
    target_tac_ppm: float = Field(gt=0, description="TAC objectif en ppm CaCO3.")
    tac_measurement_step_ppm: float = Field(
        gt=0, description="Résolution du test TAC en ppm CaCO3."
    )
    bucket_volume_l: float = Field(gt=0, description="Volume nominal du seau en litres.")
    naoh_concentration_g_l: float = Field(gt=0, description="Concentration NaOH en g/L.")


class WorkflowDefaults(BaseModel):
    """Tailles de portions indicatives, sans valeur prédictive de pH."""

    naoh_large_gap_ph: float = Field(
        gt=0, description="Écart pH au-delà duquel la grande portion est proposée."
    )
    naoh_medium_gap_ph: float = Field(
        gt=0, description="Écart pH au-delà duquel la portion moyenne est proposée."
    )
    naoh_large_dose_ml: float = Field(gt=0, description="Repère NaOH pour un grand écart pH.")
    naoh_medium_dose_ml: float = Field(gt=0, description="Repère NaOH pour un écart moyen.")
    naoh_small_dose_ml: float = Field(gt=0, description="Repère NaOH près de la cible.")
    bicarbonate_batch_max_kg: float = Field(
        gt=0, description="Masse maximale d'un apport de bicarbonate en kg."
    )
    bicarbonate_wait_min_minutes: int = Field(
        gt=0, description="Attente minimale de circulation avant le contrôle TAC."
    )

    @model_validator(mode="after")
    def validate_naoh_thresholds(self) -> WorkflowDefaults:
        """Garantit que les seuils sélectionnent bien petite, moyenne puis grande portion."""
        if self.naoh_medium_gap_ph >= self.naoh_large_gap_ph:
            raise ValueError("Le seuil NaOH moyen doit etre inferieur au seuil NaOH grand.")
        return self


class SupplyPlanningDefaults(BaseModel):
    """Marges d'achat : elles ne constituent jamais des doses à verser."""

    naoh_purchase_recommended_l: float = Field(gt=0)
    bicarbonate_purchase_margin_kg: float = Field(ge=0)
    stabilized_chlorine_extra_bicarbonate_margin_kg: float = Field(ge=0)


class ApplicationSettings(BaseModel):
    """Schéma validé du fichier JSON de paramètres opérationnels."""

    schema_version: int = Field(ge=1, description="Version du format defaults.json.")
    protocol: ProtocolDefaults
    workflow: WorkflowDefaults
    supply_planning: SupplyPlanningDefaults


@lru_cache
def load_settings() -> ApplicationSettings:
    """Lit une fois ``defaults.json`` embarqué avec le paquet et le valide.

    Une erreur de format est volontairement levée au démarrage : utiliser des
    paramètres silencieusement incomplets serait dangereux pour ce protocole.
    """
    payload = files("piscine_ph").joinpath("defaults.json").read_text(encoding="utf-8")
    return ApplicationSettings.model_validate_json(payload)


SETTINGS = load_settings()
