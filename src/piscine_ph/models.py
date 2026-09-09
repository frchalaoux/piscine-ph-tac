"""Contrats Pydantic persistés dans les archives JSON du protocole.

Ce module ne contient aucune règle de transition ni aucun calcul : il décrit les
valeurs validées qui circulent entre la CLI, le service, le calculateur et le
dépôt. Les valeurs par défaut préservent aussi la lecture des anciennes archives.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .settings import SETTINGS


class ProtocolStep(StrEnum):
    """Étapes persistées du protocole, dans leur ordre opérationnel."""

    PH_TO_INTERMEDIATE = "naoh_vers_palier"
    TAC_TO_TARGET = "tac_vers_80"
    PH_TO_TARGET = "naoh_final"
    HIGH_PH_MONITORING = "surveillance_ph_haut"
    COMPLETE = "termine"
    CANCELLED = "annule"


class ProtocolMode(StrEnum):
    """Parcours disponibles dans une archive de suivi."""

    RAISE_PH_TAC = "correction_hausse_ph_tac"
    HIGH_PH_MONITORING = "surveillance_ph_haut"


class ElectrolysisStatus(StrEnum):
    """État déclaré de l'électrolyse, distinct des mesures pH/TAC."""

    UNKNOWN = "inconnu"
    RUNNING = "en_marche"
    STOPPED = "arretee"


class PhRegulatorStatus(StrEnum):
    """État déclaré du régulateur de pH, sans le piloter."""

    UNKNOWN = "inconnu"
    RUNNING = "en_marche"
    STOPPED = "arrete"


class StabilizedTabletStatus(StrEnum):
    """État observé des galets dans le doseur ; ce n'est pas une dose calculée."""

    UNKNOWN = "inconnu"
    ACTIVE = "en_place"
    CONSUMED = "consommes"
    PAUSED = "suspendus"
    NOT_NEEDED = "non_necessaires"


class ChlorineTreatment(StrEnum):
    """Famille de désinfectant déclarée pour contextualiser le modèle pH/TAC."""

    UNKNOWN = "inconnu"
    STABILIZED_TABLETS = "galets_stabilises"
    STABILIZED_DICHLOR = "dichlore_stabilise"
    UNSTABILIZED = "chlore_non_stabilise"


class NaOHConcentrationSource(StrEnum):
    """Origine de la concentration de soude déclarée pour le protocole."""

    DEFAULT = "valeur_par_defaut"
    GRAMS_PER_LITRE = "g_par_litre"
    MASS_PERCENT = "pourcentage_massique"
    VOLUME_PERCENT = "pourcentage_volumique"


class TreatmentContext(BaseModel):
    """Contexte de traitement qui rend la prédiction carbonate plus ou moins fiable.

    Il est volontairement séparé de :class:`ProtocolConfig` : il peut évoluer
    pendant un protocole sans modifier le volume ni les objectifs archivés.
    """

    electrolysis_status: ElectrolysisStatus = ElectrolysisStatus.UNKNOWN
    chlorine_treatment: ChlorineTreatment = ChlorineTreatment.UNKNOWN
    ph_regulator_status: PhRegulatorStatus = PhRegulatorStatus.UNKNOWN
    stabilized_tablet_status: StabilizedTabletStatus = StabilizedTabletStatus.UNKNOWN


class StabilizedTabletRecord(BaseModel):
    """Trace un ajout de galets sans en déduire artificiellement le CYA."""

    count: int = Field(gt=0)
    unit_mass_g: float | None = Field(default=None, gt=0)
    product_label: str = "galet stabilise"
    recorded_at: datetime = Field(default_factory=datetime.now)


class CyanuricAcidMeasurement(BaseModel):
    """Mesure déclarée de stabilisant (CYA), en mg/L ou ppm équivalents."""

    cya_ppm: float = Field(ge=0)
    recorded_at: datetime = Field(default_factory=datetime.now)


class WaterMeasurement(BaseModel):
    """Mesure sans ajout de produit, employée en surveillance pH haut."""

    ph: float = Field(gt=0, lt=14)
    tac_ppm: float = Field(gt=0)
    free_chlorine_ppm: float = Field(ge=0)
    recorded_at: datetime = Field(default_factory=datetime.now)


class SupplyEstimate(BaseModel):
    """Repère d'achat généré au démarrage, distinct des doses opérationnelles."""

    naoh_solution_recommended_l: float = Field(gt=0)
    bicarbonate_theoretical_kg: float = Field(ge=0)
    bicarbonate_recommended_kg: float = Field(ge=0)
    basis_tac_ppm: float = Field(gt=0)
    includes_stabilized_chlorine_margin: bool = False


class ProtocolConfig(BaseModel):
    """Paramètres physiques et objectifs immuables d'un protocole.

    Le TAC est exprimé en ppm équivalent CaCO3. Modifier le bassin ou les
    objectifs impose une nouvelle archive afin de préserver la traçabilité.
    """

    model_config = ConfigDict(frozen=True)

    mode: ProtocolMode = ProtocolMode.RAISE_PH_TAC
    pool_volume_m3: float = Field(default=SETTINGS.protocol.pool_volume_m3, gt=0)
    initial_ph: float = Field(default=SETTINGS.protocol.initial_ph, gt=0, lt=14)
    intermediate_ph: float = Field(default=SETTINGS.protocol.intermediate_ph, gt=0, lt=14)
    target_ph: float = Field(default=SETTINGS.protocol.target_ph, gt=0, lt=14)
    initial_tac_ppm: float = Field(default=SETTINGS.protocol.initial_tac_ppm, gt=0)
    target_tac_ppm: float = Field(default=SETTINGS.protocol.target_tac_ppm, gt=0)
    tac_measurement_step_ppm: float = Field(
        default=SETTINGS.protocol.tac_measurement_step_ppm, gt=0
    )
    bucket_volume_l: float = Field(default=SETTINGS.protocol.bucket_volume_l, gt=0)
    naoh_concentration_g_l: float = Field(default=SETTINGS.protocol.naoh_concentration_g_l, gt=0)
    naoh_concentration_source: NaOHConcentrationSource = NaOHConcentrationSource.DEFAULT
    naoh_label_percent: float | None = Field(default=None, gt=0, le=100)
    naoh_density_g_ml: float | None = Field(default=None, gt=0)
    free_chlorine_min_ppm: float = Field(default=1.0, ge=0)
    free_chlorine_max_ppm: float = Field(default=4.0, gt=0)

    @model_validator(mode="after")
    def validate_targets(self) -> ProtocolConfig:
        """Vérifie l'ordre des pH et la résolution réellement disponible du TAC."""
        if self.mode is ProtocolMode.RAISE_PH_TAC:
            if not self.initial_ph < self.intermediate_ph < self.target_ph:
                raise ValueError("Les pH doivent respecter : initial < palier < cible.")
        elif self.initial_ph <= self.target_ph:
            raise ValueError(
                "En surveillance pH haut, le pH initial doit etre strictement superieur a la cible."
            )
        if self.free_chlorine_min_ppm > self.free_chlorine_max_ppm:
            raise ValueError(
                "La borne basse de chlore libre doit etre inferieure ou egale a la borne haute."
            )
        for label, value in (
            ("TAC initial", self.initial_tac_ppm),
            ("TAC cible", self.target_tac_ppm),
        ):
            if not _is_multiple(value, self.tac_measurement_step_ppm):
                raise ValueError(
                    f"{label} doit etre un multiple de {self.tac_measurement_step_ppm:.0f} ppm."
                )
        if self.naoh_concentration_source is NaOHConcentrationSource.MASS_PERCENT and (
            self.naoh_label_percent is None or self.naoh_density_g_ml is None
        ):
            raise ValueError(
                "Une soude en pourcentage massique exige le pourcentage et la densite."
            )
        if (
            self.naoh_concentration_source is NaOHConcentrationSource.VOLUME_PERCENT
            and self.naoh_label_percent is None
        ):
            raise ValueError("Une soude en pourcentage volumique exige le pourcentage.")
        return self


class CoherenceCheck(BaseModel):
    """Résultat du contrôle entre une mesure et le bilan carbonate fermé.

    ``expected_ph`` et ``ph_difference`` valent ``None`` si le modèle ne peut
    pas produire une prédiction de pH exploitable ; le bilan TAC reste disponible.
    """

    expected_ph: float | None
    expected_tac_ppm: float
    ph_difference: float | None
    tac_difference_ppm: float
    inferred_carbon_mol_l: float
    is_consistent: bool
    warnings: list[str] = Field(default_factory=list)


class PendingNaOHDose(BaseModel):
    """Dose de soude préparée, sans mesure bassin de confirmation.

    Sa présence interdit une seconde préparation. Elle est annulable uniquement
    si elle n'a pas été versée dans le bassin.
    """

    phase: Literal["intermediate", "final"]
    ph_before: float
    tac_before_ppm: float
    naoh_ml: float = Field(gt=0)
    water_l: float = Field(gt=0)
    created_at: datetime = Field(default_factory=datetime.now)


class NaOHDoseRecord(BaseModel):
    """Ajout de soude confirmé, avec mesures avant/après et contrôle associé."""

    phase: Literal["intermediate", "final"]
    ph_before: float
    tac_before_ppm: float
    naoh_ml: float
    ph_after: float
    tac_after_ppm: float
    coherence: CoherenceCheck
    recorded_at: datetime = Field(default_factory=datetime.now)


class PendingBicarbonatePlan(BaseModel):
    """Lot de bicarbonate calculé, en attente de sa mesure de confirmation."""

    ph_before: float
    tac_before_ppm: float
    bicarbonate_kg: float = Field(ge=0)
    bicarbonate_total_kg: float | None = Field(default=None, ge=0)
    created_at: datetime = Field(default_factory=datetime.now)


class BicarbonateRecord(BaseModel):
    """Apport de bicarbonate confirmé, avec mesures avant/après et contrôle associé."""

    ph_before: float
    tac_before_ppm: float
    bicarbonate_kg: float
    ph_after: float
    tac_after_ppm: float
    coherence: CoherenceCheck
    recorded_at: datetime = Field(default_factory=datetime.now)


class JournalEvent(BaseModel):
    """Événement horodaté lisible par l'utilisateur dans l'historique."""

    event: str
    created_at: datetime = Field(default_factory=datetime.now)


class CumulativeAdditions(BaseModel):
    """Bilan dérivé des produits effectivement enregistrés dans le bassin.

    Les contributions TAC sont théoriques et ne remplacent jamais le TAC mesuré.
    """

    naoh_solution_ml: float = 0.0
    naoh_moles: float = 0.0
    bicarbonate_kg: float = 0.0
    bicarbonate_moles: float = 0.0
    theoretical_tac_from_naoh_ppm: float = 0.0
    theoretical_tac_from_bicarbonate_ppm: float = 0.0
    theoretical_tac_total_ppm: float = 0.0


class ProtocolState(BaseModel):
    """État complet sérialisable d'un protocole et de son historique.

    Les champs ``pending_*`` représentent une action préparée mais non confirmée.
    Les listes de doses ne contiennent que les apports confirmés par une mesure.
    ``cumulative_additions`` est recalculé par le service depuis ces listes.
    """

    version: int = 3
    protocol_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    archive_name: str
    config: ProtocolConfig
    treatment: TreatmentContext = Field(default_factory=TreatmentContext)
    supply_estimate: SupplyEstimate | None = None
    step: ProtocolStep = ProtocolStep.PH_TO_INTERMEDIATE
    current_ph: float
    current_tac_ppm: float
    initial_coherence: CoherenceCheck | None = None
    pending_naoh: PendingNaOHDose | None = None
    pending_bicarbonate: PendingBicarbonatePlan | None = None
    naoh_doses: list[NaOHDoseRecord] = Field(default_factory=list)
    bicarbonate_doses: list[BicarbonateRecord] = Field(default_factory=list)
    stabilized_tablets: list[StabilizedTabletRecord] = Field(default_factory=list)
    cyanuric_acid_measurements: list[CyanuricAcidMeasurement] = Field(default_factory=list)
    water_measurements: list[WaterMeasurement] = Field(default_factory=list)
    cumulative_additions: CumulativeAdditions = Field(default_factory=CumulativeAdditions)
    journal: list[JournalEvent] = Field(default_factory=list)

    def add_event(self, event: str) -> None:
        """Ajoute un événement au journal et actualise la date de modification."""
        self.journal.append(JournalEvent(event=event))
        self.updated_at = datetime.now(UTC)


def _is_multiple(value: float, step: float) -> bool:
    """Teste un multiple malgré les imprécisions de représentation des flottants."""
    return abs(value / step - round(value / step)) < 1e-9
