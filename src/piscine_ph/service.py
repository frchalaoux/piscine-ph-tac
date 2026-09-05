"""Règles métier et transitions persistées du protocole.

Cette couche est l'unique responsable des mutations de ``ProtocolState``. Elle
sépare les décisions de protocole de la CLI et du stockage afin que les
transitions restent testables et traçables.
"""

from __future__ import annotations

from datetime import datetime
from math import ceil

from .chemistry import BucketPreparation, ChemistryCalculator
from .models import (
    BicarbonateRecord,
    ChlorineTreatment,
    CoherenceCheck,
    CyanuricAcidMeasurement,
    ElectrolysisStatus,
    NaOHDoseRecord,
    PendingBicarbonatePlan,
    PendingNaOHDose,
    ProtocolConfig,
    ProtocolState,
    ProtocolStep,
    StabilizedTabletRecord,
    SupplyEstimate,
    TreatmentContext,
)
from .repository import JsonProtocolRepository
from .settings import SETTINGS


class ProtocolService:
    """Orchestre un protocole à partir d'un dépôt et d'un calculateur chimique."""

    def __init__(
        self, repository: JsonProtocolRepository, chemistry: ChemistryCalculator | None = None
    ):
        """Construit le service ; un calculateur peut être injecté pour les tests."""
        self.repository = repository
        self.chemistry = chemistry or ChemistryCalculator()

    def active(self) -> ProtocolState:
        """Retourne le protocole actif ou explique à l'appelant comment en créer un."""
        state = self.repository.active()
        if state is None:
            raise ValueError("Aucun protocole actif. Lancez d'abord la commande start.")
        if state.supply_estimate is None:
            state.supply_estimate = self.build_supply_estimate(state.config, state.treatment)
            state.add_event("Plan d'approvisionnement genere pour le protocole existant")
            self.repository.save(state)
        return state

    def refresh_cumulative_additions(self, state: ProtocolState) -> None:
        """Recalcule le cumul depuis les apports confirmés par une mesure.

        Ce recalcul plutôt qu'un incrément évite qu'une correction de lecture ou
        une annulation fasse dériver les quantités réellement comptabilisées.
        """
        naoh_ml = sum(dose.naoh_ml for dose in state.naoh_doses)
        bicarbonate_kg = sum(dose.bicarbonate_kg for dose in state.bicarbonate_doses)
        state.cumulative_additions = self.chemistry.cumulative_additions(
            state.config, naoh_ml, bicarbonate_kg
        )

    @staticmethod
    def treatment_warnings(state: ProtocolState) -> list[str]:
        """Retourne les limites du modèle liées au traitement déclaré.

        Les bilans stœchiométriques NaOH/NaHCO3 demeurent utilisables. En
        revanche, les galets stabilisés ajoutent de l'acidité et du cyanurate,
        deux phénomènes absents du modèle carbonate fermé.
        """
        treatment = state.treatment
        warnings: list[str] = []
        if treatment.chlorine_treatment in {
            ChlorineTreatment.STABILIZED_TABLETS,
            ChlorineTreatment.STABILIZED_DICHLOR,
        }:
            warnings.append(
                "Chlore stabilise declare : le CYA et son alcalinite ne sont pas modelises ; "
                "la prediction de pH est indicative."
            )
        if treatment.electrolysis_status is ElectrolysisStatus.STOPPED:
            warnings.append(
                "Electrolyse arretee : la hausse habituelle de pH liee a la cellule n'est plus attendue."
            )
        if (
            treatment.electrolysis_status is ElectrolysisStatus.STOPPED
            and treatment.chlorine_treatment is ChlorineTreatment.STABILIZED_TABLETS
        ):
            warnings.append(
                "Galets stabilises avec electrolyse arretee : suivre pH et TAC sur mesure ; "
                "les galets peuvent acidifier l'eau et faire baisser le TAC."
            )
        if state.cyanuric_acid_measurements:
            cya = state.cyanuric_acid_measurements[-1].cya_ppm
            if cya >= 75:
                warnings.append(
                    f"CYA mesure a {cya:.0f} ppm : ne plus ajouter de chlore stabilise ; "
                    "evaluer un renouvellement partiel d'eau."
                )
            elif cya >= 50:
                warnings.append(
                    f"CYA mesure a {cya:.0f} ppm : surveiller l'accumulation avant de poursuivre "
                    "les galets stabilises."
                )
        return warnings

    def build_supply_estimate(
        self, config: ProtocolConfig, treatment: TreatmentContext
    ) -> SupplyEstimate:
        """Construit un repère d'achat à partir du protocole, sans prédire le pH.

        La soude est un stock prudent configurable : la consommation réelle ne
        peut pas être déduite du seul pH de départ. Le bicarbonate est fondé sur
        le bilan TAC initial, complété par une marge d'achat explicite.
        """
        theoretical_bicarbonate_kg = self.chemistry.bicarbonate_kg(config, config.initial_tac_ppm)
        stabilized = treatment.chlorine_treatment is ChlorineTreatment.STABILIZED_TABLETS
        margin_kg = SETTINGS.supply_planning.bicarbonate_purchase_margin_kg
        if stabilized:
            margin_kg += SETTINGS.supply_planning.stabilized_chlorine_extra_bicarbonate_margin_kg
        return SupplyEstimate(
            naoh_solution_recommended_l=SETTINGS.supply_planning.naoh_purchase_recommended_l,
            bicarbonate_theoretical_kg=theoretical_bicarbonate_kg,
            bicarbonate_recommended_kg=float(ceil(theoretical_bicarbonate_kg + margin_kg)),
            basis_tac_ppm=config.initial_tac_ppm,
            includes_stabilized_chlorine_margin=stabilized,
        )

    def enrich_check_with_treatment(
        self, state: ProtocolState, check: CoherenceCheck
    ) -> CoherenceCheck:
        """Ajoute au contrôle les avertissements de contexte, sans fausser le bilan TAC."""
        for warning in self.treatment_warnings(state):
            if warning not in check.warnings:
                check.warnings.append(warning)
        return check

    def set_treatment(
        self, electrolysis_status: ElectrolysisStatus, chlorine_treatment: ChlorineTreatment
    ) -> ProtocolState:
        """Enregistre le mode de désinfection actuellement appliqué au bassin."""
        state = self.active()
        state.treatment = TreatmentContext(
            electrolysis_status=electrolysis_status,
            chlorine_treatment=chlorine_treatment,
        )
        state.supply_estimate = self.build_supply_estimate(state.config, state.treatment)
        state.add_event(
            "Contexte traitement : "
            f"electrolyse {electrolysis_status.value}, chlore {chlorine_treatment.value}"
        )
        self.repository.save(state)
        return state

    def record_stabilized_tablets(
        self, count: int, unit_mass_g: float | None, product_label: str
    ) -> ProtocolState:
        """Journalise des galets stabilisés réellement mis dans le doseur."""
        state = self.active()
        if state.treatment.chlorine_treatment is not ChlorineTreatment.STABILIZED_TABLETS:
            raise ValueError(
                "Declarez d'abord --chlorine galets_stabilises avec la commande treatment."
            )
        record = StabilizedTabletRecord(
            count=count, unit_mass_g=unit_mass_g, product_label=product_label
        )
        state.stabilized_tablets.append(record)
        mass = f" de {unit_mass_g:.0f} g" if unit_mass_g is not None else ""
        state.add_event(f"Galets stabilises ajoutes : {count}{mass} ({product_label})")
        self.repository.save(state)
        return state

    def record_cyanuric_acid_measurement(self, cya_ppm: float) -> ProtocolState:
        """Journalise une mesure réelle de CYA, sans l'inférer des galets."""
        state = self.active()
        state.cyanuric_acid_measurements.append(CyanuricAcidMeasurement(cya_ppm=cya_ppm))
        state.add_event(f"CYA mesure : {cya_ppm:.0f} ppm")
        self.repository.save(state)
        return state

    @staticmethod
    def validate_tac_measurement(state: ProtocolState, tac_ppm: float) -> None:
        """Refuse un TAC plus précis que la résolution déclarée du test utilisateur."""
        step = state.config.tac_measurement_step_ppm
        if abs(tac_ppm / step - round(tac_ppm / step)) > 1e-9:
            raise ValueError(
                f"Le TAC doit etre saisi par pas de {step:.0f} ppm (ex. 50, 60, 70, 80)."
            )

    def start(
        self,
        config: ProtocolConfig,
        treatment: TreatmentContext | None = None,
        *,
        replace_active: bool = False,
    ) -> ProtocolState:
        """Crée une archive ou reprend l'archive active existante.

        ``replace_active`` n'efface jamais l'archive active : il autorise
        seulement la création volontaire d'un nouveau protocole daté.
        """
        active = self.repository.active()
        if active and not replace_active:
            if active.supply_estimate is None:
                active.supply_estimate = self.build_supply_estimate(active.config, active.treatment)
                active.add_event("Plan d'approvisionnement genere pour le protocole existant")
                self.repository.save(active)
            return active
        path = self.repository.create_path()
        state = ProtocolState(
            protocol_id=datetime.now().astimezone().isoformat(timespec="seconds"),
            archive_name=path.name,
            config=config,
            treatment=treatment or TreatmentContext(),
            current_ph=config.initial_ph,
            current_tac_ppm=config.initial_tac_ppm,
        )
        state.supply_estimate = self.build_supply_estimate(state.config, state.treatment)
        state.initial_coherence = self.enrich_check_with_treatment(
            state,
            self.chemistry.verify(
                config,
                ph_before=config.initial_ph,
                tac_before_ppm=config.initial_tac_ppm,
                ph_after=config.initial_ph,
                tac_after_ppm=config.initial_tac_ppm,
            ),
        )
        state.add_event("Protocole cree et mesures initiales controlees")
        self.repository.save(state)
        return state

    def prepare_naoh(
        self, requested_ml: float | None = None
    ) -> tuple[ProtocolState, BucketPreparation]:
        """Prépare une dose de NaOH pour l'étape pH active et la met en attente.

        La dose reste sans effet dans les cumuls tant que la mesure après ajout
        n'a pas été enregistrée avec :meth:`record_naoh_measurement`.
        """
        state = self.active()
        if state.step not in {ProtocolStep.PH_TO_INTERMEDIATE, ProtocolStep.PH_TO_TARGET}:
            raise ValueError("La soude n'est pas l'etape active du protocole.")
        if state.pending_naoh:
            raise ValueError("Une dose de NaOH est deja en attente de mesure.")
        target = (
            state.config.intermediate_ph
            if state.step is ProtocolStep.PH_TO_INTERMEDIATE
            else state.config.target_ph
        )
        suggestion = self.chemistry.suggested_naoh_ml(state.current_ph, target)
        preparation = self.chemistry.prepare_bucket(state.config, requested_ml or suggestion)
        phase = "intermediate" if state.step is ProtocolStep.PH_TO_INTERMEDIATE else "final"
        state.pending_naoh = PendingNaOHDose(
            phase=phase,
            ph_before=state.current_ph,
            tac_before_ppm=state.current_tac_ppm,
            naoh_ml=preparation.naoh_ml,
            water_l=preparation.water_l,
        )
        state.add_event(f"Dose NaOH preparee : {preparation.naoh_ml:.0f} mL")
        self.repository.save(state)
        return state, preparation

    def record_naoh_measurement(self, ph: float, tac_ppm: float) -> ProtocolState:
        """Confirme la dose NaOH en attente avec pH/TAC et fait progresser l'étape.

        Le protocole passe au TAC si le palier pH intermédiaire est atteint, ou
        devient terminé lorsque la cible finale est confirmée.
        """
        state = self.active()
        self.validate_tac_measurement(state, tac_ppm)
        pending = state.pending_naoh
        if pending is None:
            raise ValueError("Aucune dose de NaOH en attente.")
        check = self.enrich_check_with_treatment(
            state,
            self.chemistry.verify(
                state.config,
                ph_before=pending.ph_before,
                tac_before_ppm=pending.tac_before_ppm,
                ph_after=ph,
                tac_after_ppm=tac_ppm,
                naoh_ml=pending.naoh_ml,
            ),
        )
        state.naoh_doses.append(
            NaOHDoseRecord(
                phase=pending.phase,
                ph_before=pending.ph_before,
                tac_before_ppm=pending.tac_before_ppm,
                naoh_ml=pending.naoh_ml,
                ph_after=ph,
                tac_after_ppm=tac_ppm,
                coherence=check,
            )
        )
        self.refresh_cumulative_additions(state)
        state.pending_naoh = None
        state.current_ph = ph
        state.current_tac_ppm = tac_ppm
        if state.step is ProtocolStep.PH_TO_INTERMEDIATE and ph >= state.config.intermediate_ph:
            state.step = ProtocolStep.TAC_TO_TARGET
            state.add_event("Palier pH atteint : passage a la correction du TAC")
        elif state.step is ProtocolStep.PH_TO_TARGET and ph >= state.config.target_ph:
            state.step = ProtocolStep.COMPLETE
            state.add_event("pH final atteint : protocole termine")
        else:
            state.add_event(f"Mesures apres NaOH : pH {ph:.2f}, TAC {tac_ppm:.1f} ppm")
        self.repository.save(state)
        return state

    def cancel_pending_naoh(self) -> ProtocolState:
        """Annule une dose de NaOH préparée uniquement si elle n'a pas été ajoutée."""
        state = self.active()
        pending = state.pending_naoh
        if pending is None:
            raise ValueError("Aucune dose de NaOH en attente a annuler.")
        state.pending_naoh = None
        state.add_event(f"Dose NaOH annulee avant ajout : {pending.naoh_ml:.0f} mL")
        self.repository.save(state)
        return state

    def cancel_protocol(self) -> ProtocolState:
        """Archive le protocole actif comme annulé, sans effacer son journal.

        Les préparations en attente sont supprimées du suivi car elles ne sont
        pas des apports confirmés. Les doses et mesures précédentes sont gardées.
        """
        state = self.active()
        state.pending_naoh = None
        state.pending_bicarbonate = None
        state.step = ProtocolStep.CANCELLED
        state.add_event("Protocole annule par l'utilisateur")
        self.repository.save(state)
        return state

    def correct_last_measurement(self, ph: float, tac_ppm: float) -> ProtocolState:
        """Corrige la dernière mesure sans retirer le produit déjà versé.

        Seul le dernier enregistrement NaOH ou bicarbonate est modifiable. Une
        préparation postérieure doit d'abord être annulée pour ne pas rompre la
        chronologie des mesures et les cumuls restent volontairement inchangés.
        """
        state = self.active()
        self.validate_tac_measurement(state, tac_ppm)
        if state.pending_naoh or state.pending_bicarbonate:
            raise ValueError("Annulez d'abord la dose preparee apres la mesure a corriger.")

        latest_naoh = state.naoh_doses[-1] if state.naoh_doses else None
        latest_bicarbonate = state.bicarbonate_doses[-1] if state.bicarbonate_doses else None
        if latest_naoh is None and latest_bicarbonate is None:
            raise ValueError("Aucune mesure enregistree a corriger.")

        if latest_bicarbonate and (
            latest_naoh is None or latest_bicarbonate.recorded_at > latest_naoh.recorded_at
        ):
            record = latest_bicarbonate
            record.ph_after = ph
            record.tac_after_ppm = tac_ppm
            record.coherence = self.enrich_check_with_treatment(
                state,
                self.chemistry.verify(
                    state.config,
                    ph_before=record.ph_before,
                    tac_before_ppm=record.tac_before_ppm,
                    ph_after=ph,
                    tac_after_ppm=tac_ppm,
                    bicarbonate_kg=record.bicarbonate_kg,
                ),
            )
            state.step = (
                ProtocolStep.PH_TO_TARGET
                if tac_ppm >= state.config.target_tac_ppm
                else ProtocolStep.TAC_TO_TARGET
            )
            product = "bicarbonate"
        else:
            assert latest_naoh is not None
            record = latest_naoh
            record.ph_after = ph
            record.tac_after_ppm = tac_ppm
            record.coherence = self.enrich_check_with_treatment(
                state,
                self.chemistry.verify(
                    state.config,
                    ph_before=record.ph_before,
                    tac_before_ppm=record.tac_before_ppm,
                    ph_after=ph,
                    tac_after_ppm=tac_ppm,
                    naoh_ml=record.naoh_ml,
                ),
            )
            if record.phase == "intermediate":
                state.step = (
                    ProtocolStep.TAC_TO_TARGET
                    if ph >= state.config.intermediate_ph
                    else ProtocolStep.PH_TO_INTERMEDIATE
                )
            else:
                state.step = (
                    ProtocolStep.COMPLETE
                    if ph >= state.config.target_ph
                    else ProtocolStep.PH_TO_TARGET
                )
            product = "NaOH"

        state.current_ph = ph
        state.current_tac_ppm = tac_ppm
        self.refresh_cumulative_additions(state)
        state.add_event(f"Derniere mesure {product} corrigee : pH {ph:.2f}, TAC {tac_ppm:.0f} ppm")
        self.repository.save(state)
        return state

    def plan_bicarbonate(self, measured_tac_ppm: float) -> ProtocolState:
        """Calcule l'apport de bicarbonate depuis le TAC réel et le met en attente.

        Cette opération est possible uniquement entre le palier pH et la cible
        TAC. La quantité n'est comptabilisée qu'après ``record_bicarbonate_measurement``.
        """
        state = self.active()
        self.validate_tac_measurement(state, measured_tac_ppm)
        if state.step is not ProtocolStep.TAC_TO_TARGET:
            raise ValueError("Le bicarbonate n'est pas l'etape active du protocole.")
        if state.pending_bicarbonate:
            raise ValueError("Un apport de bicarbonate est deja en attente de mesure.")
        kg = self.chemistry.bicarbonate_kg(state.config, measured_tac_ppm)
        state.current_tac_ppm = measured_tac_ppm
        state.pending_bicarbonate = PendingBicarbonatePlan(
            ph_before=state.current_ph,
            tac_before_ppm=measured_tac_ppm,
            bicarbonate_kg=kg,
        )
        state.add_event(f"Apport bicarbonate prepare : {kg:.2f} kg")
        self.repository.save(state)
        return state

    def record_bicarbonate_measurement(self, ph: float, tac_ppm: float) -> ProtocolState:
        """Confirme un apport bicarbonate et passe à l'étape finale si le TAC suffit."""
        state = self.active()
        self.validate_tac_measurement(state, tac_ppm)
        pending = state.pending_bicarbonate
        if pending is None:
            raise ValueError("Aucun apport de bicarbonate en attente.")
        check = self.enrich_check_with_treatment(
            state,
            self.chemistry.verify(
                state.config,
                ph_before=pending.ph_before,
                tac_before_ppm=pending.tac_before_ppm,
                ph_after=ph,
                tac_after_ppm=tac_ppm,
                bicarbonate_kg=pending.bicarbonate_kg,
            ),
        )
        state.bicarbonate_doses.append(
            BicarbonateRecord(
                ph_before=pending.ph_before,
                tac_before_ppm=pending.tac_before_ppm,
                bicarbonate_kg=pending.bicarbonate_kg,
                ph_after=ph,
                tac_after_ppm=tac_ppm,
                coherence=check,
            )
        )
        self.refresh_cumulative_additions(state)
        state.pending_bicarbonate = None
        state.current_ph = ph
        state.current_tac_ppm = tac_ppm
        if tac_ppm >= state.config.target_tac_ppm:
            state.step = ProtocolStep.PH_TO_TARGET
            state.add_event("TAC cible confirme : passage a l'ajustement final du pH")
        else:
            state.add_event(f"TAC insuffisant : {tac_ppm:.1f} ppm, apport complementaire requis")
        self.repository.save(state)
        return state
