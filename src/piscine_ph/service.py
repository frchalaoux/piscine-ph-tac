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
    AcidDoseRecord,
    BicarbonateRecord,
    CoherenceCheck,
    CyanuricAcidMeasurement,
    DisinfectionMethod,
    ElectrolysisStatus,
    NaOHConcentrationSource,
    NaOHDoseRecord,
    PendingAcidDose,
    PendingBicarbonatePlan,
    PendingNaOHDose,
    PhRegulatorStatus,
    ProtocolConfig,
    ProtocolMode,
    ProtocolState,
    ProtocolStep,
    StabilizedTabletProduct,
    StabilizedTabletRecord,
    StabilizedTabletStatus,
    SupplyEstimate,
    TreatmentContext,
    WaterMeasurement,
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

    # Notice IRRIPOOL PH- LIQUIDE 15 % : 75 mL / 10 m³ / baisse de 0,1 pH.
    # Un seul lot ne vise jamais plus de 0,1 pH afin d'imposer une re-mesure.
    SULFURIC_ACID_15_ML_PER_10_M3_PER_0_1_PH = 75.0
    MAX_ACID_BATCH_PH = 0.1

    def active(self) -> ProtocolState:
        """Retourne le protocole actif ou explique à l'appelant comment en créer un."""
        state = self.repository.active()
        if state is None:
            raise ValueError("Aucun protocole actif. Lancez d'abord la commande start.")
        if state.supply_estimate is None and state.config.mode is ProtocolMode.RAISE_PH_TAC:
            state.supply_estimate = self.build_supply_estimate(state.config, state.treatment)
            state.add_event("Plan d'approvisionnement genere pour le protocole existant")
            self.repository.save(state)
        return state

    @staticmethod
    def next_command(state: ProtocolState) -> str:
        """Retourne l'action CLI équivalente à l'étape persistée.

        La CLI et la TUI emploient cette même indication pour que le guide
        interactif ne diverge pas des menus.
        """
        if state.step in {ProtocolStep.COMPLETE, ProtocolStep.CANCELLED}:
            return "piscine-ph history"
        if state.pending_naoh:
            return "piscine-ph measure --ph VOTRE_PH --tac VOTRE_TAC"
        if state.pending_acid:
            return "piscine-ph measure-acid --ph VOTRE_PH --tac VOTRE_TAC"
        if state.pending_bicarbonate:
            return "piscine-ph measure-tac --ph VOTRE_PH --tac VOTRE_TAC"
        if state.step is ProtocolStep.HIGH_PH_MONITORING:
            if (
                state.config.mode is ProtocolMode.DISINFECTION_MONITORING
                and state.treatment.disinfection_method is DisinfectionMethod.STABILIZED_TABLETS
                and state.water_measurements
            ):
                latest_measurement = state.water_measurements[-1]
                chlorine = latest_measurement.free_chlorine_ppm
                cya_is_high = (
                    bool(state.cyanuric_acid_measurements)
                    and state.cyanuric_acid_measurements[-1].cya_ppm >= 50
                )
                if chlorine is not None and chlorine < state.config.free_chlorine_min_ppm and not cya_is_high:
                    if (
                        state.treatment.stabilized_tablet_product
                        is StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC
                    ):
                        return "piscine-ph plan-tablets"
                    return "piscine-ph plan-tablets --m3-per-tablet VALEUR_ETIQUETTE"
            chlorine_option = (
                " --free-chlorine VOTRE_CHLORE"
                if state.config.mode
                in {ProtocolMode.HIGH_PH_MONITORING, ProtocolMode.DISINFECTION_MONITORING}
                else ""
            )
            return (
                f"piscine-ph record-water --ph VOTRE_PH --tac VOTRE_TAC{chlorine_option}"
            )
        if state.step is ProtocolStep.TAC_TO_TARGET:
            return "piscine-ph plan-tac --tac VOTRE_TAC"
        if state.step is ProtocolStep.ACID_TO_TARGET:
            return "piscine-ph dose-acid"
        return "piscine-ph dose"

    def refresh_cumulative_additions(self, state: ProtocolState) -> None:
        """Recalcule le cumul depuis les apports confirmés par une mesure.

        Ce recalcul plutôt qu'un incrément évite qu'une correction de lecture ou
        une annulation fasse dériver les quantités réellement comptabilisées.
        """
        naoh_ml = sum(dose.naoh_ml for dose in state.naoh_doses)
        acid_ml = sum(dose.acid_ml for dose in state.acid_doses)
        bicarbonate_kg = sum(dose.bicarbonate_kg for dose in state.bicarbonate_doses)
        state.cumulative_additions = self.chemistry.cumulative_additions(
            state.config, naoh_ml, bicarbonate_kg
        )
        state.cumulative_additions.sulfuric_acid_15_ml = acid_ml

    @staticmethod
    def treatment_warnings(state: ProtocolState) -> list[str]:
        """Retourne les limites du modèle liées au traitement déclaré.

        Les bilans stœchiométriques NaOH/NaHCO3 demeurent utilisables. En
        revanche, les galets stabilisés ajoutent de l'acidité et du cyanurate,
        deux phénomènes absents du modèle carbonate fermé.
        """
        treatment = state.treatment
        warnings: list[str] = []
        if treatment.uses_stabilized_chlorine:
            warnings.append(
                "Chlore stabilise declare : le CYA et son alcalinite ne sont pas modelises ; "
                "la prediction de pH est indicative."
            )
        if treatment.stabilized_tablet_product in {
            StabilizedTabletProduct.TRICHLOR_MULTIFUNCTION_GCCHL4EC,
            StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC,
        }:
            product_name = (
                "GCCHL4EC (galets multifonctions)"
                if treatment.stabilized_tablet_product
                is StabilizedTabletProduct.TRICHLOR_MULTIFUNCTION_GCCHL4EC
                else "GCCHLLEC (chlore lent)"
            )
            warnings.append(
                f"Galets {product_name} declares : trichlore (chlore actif 72 % minimum). "
                "Ne jamais les melanger avec l'acide sulfurique ni aucun autre produit."
            )
        if treatment.electrolysis_status is ElectrolysisStatus.STOPPED:
            warnings.append(
                "Electrolyse arretee : la hausse habituelle de pH liee a la cellule n'est plus attendue."
            )
        if treatment.ph_regulator_status is PhRegulatorStatus.STOPPED:
            warnings.append(
                "Regulateur de pH arrete : aucune correction automatique du pH n'est attendue."
            )
        if (
            treatment.electrolysis_status is ElectrolysisStatus.STOPPED
            and treatment.disinfection_method is DisinfectionMethod.STABILIZED_TABLETS
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

    @staticmethod
    def water_actions(state: ProtocolState) -> list[str]:
        """Retourne des actions de surveillance, sans jamais calculer une dose.

        Les bornes de chlore sont celles déclarées à la création de l'archive,
        donc doivent venir de l'étiquette du désinfectant. Le plan n'ordonne ni
        ajout d'acide ni ajout de chlore : ces produits et leurs dosages restent
        propres à l'installation et à leur notice.
        """
        monitoring_modes = {
            ProtocolMode.HIGH_PH_MONITORING,
            ProtocolMode.LOWER_PH_MONITORING,
            ProtocolMode.DISINFECTION_MONITORING,
        }
        if state.config.mode not in monitoring_modes:
            return []
        actions: list[str] = []
        ph = state.current_ph
        if state.config.mode is ProtocolMode.DISINFECTION_MONITORING:
            actions.append(
                f"Constat pH : pH {ph:.2f} enregistre pour le contexte. "
                "Ce protocole de desinfection ne calcule aucune correction de pH."
            )
        elif ph > state.config.target_ph:
            actions.append(
                f"Decision pH : pH {ph:.2f} au-dessus de la cible {state.config.target_ph:.2f}. "
                "Ne pas ajouter d'acide automatiquement ; verifier la mesure et la consigne du regulateur."
            )
            if state.config.mode is ProtocolMode.LOWER_PH_MONITORING:
                actions.append(
                    "Acide sulfurique 15 % declare : appliquer exclusivement la notice du produit, "
                    "avec filtration et re-mesure ; ne jamais le melanger au chlore stabilise."
                )
        elif ph == state.config.target_ph:
            actions.append(
                f"Decision pH : pH {ph:.2f} conforme a la cible {state.config.target_ph:.2f}. "
                "Aucune correction de pH n'est a effectuer sur la base de cette mesure ; "
                "continuer la surveillance habituelle."
            )
        else:
            actions.append(
                f"Decision pH : pH {ph:.2f} sous la cible {state.config.target_ph:.2f}. "
                "Ce parcours pH haut ne permet pas de choisir une correction ; ne rien ajouter "
                "automatiquement et reevaluer les mesures avant toute action."
            )
        if ph > 7.8:
            actions.append(
                "pH au-dessus de 7,8 : il sort de la plage usuelle 7,0-7,8 et le chlore est moins efficace."
            )
        if state.current_tac_ppm != state.config.target_tac_ppm:
            actions.append(
                f"Decision TAC : TAC mesure {state.current_tac_ppm:.0f} ppm, cible archivee "
                f"{state.config.target_tac_ppm:.0f} ppm. Le noter et suivre la notice ; "
                "aucun bicarbonate n'est planifie dans ce parcours."
            )
        else:
            actions.append(
                f"Decision TAC : TAC {state.current_tac_ppm:.0f} ppm conforme a la cible archivee. "
                "Aucune correction du TAC n'est indiquee par ce parcours."
            )
        if not state.water_measurements:
            if state.config.mode in {
                ProtocolMode.HIGH_PH_MONITORING,
                ProtocolMode.DISINFECTION_MONITORING,
            }:
                return actions + ["Mesurer le chlore libre avant de decider du traitement."]
            return actions

        chlorine = state.water_measurements[-1].free_chlorine_ppm
        if chlorine is None:
            if state.config.mode is ProtocolMode.DISINFECTION_MONITORING:
                return actions + ["Mesurer le chlore libre avant de decider du traitement."]
            return actions
        minimum = state.config.free_chlorine_min_ppm
        if chlorine < minimum:
            actions.append(
                f"Decision chlore : chlore libre {chlorine:.1f} ppm sous la borne basse {minimum:.1f} ppm : "
                "restaurer la desinfection uniquement suivant l'etiquette et re-mesurer."
            )
            if state.treatment.electrolysis_status is ElectrolysisStatus.STOPPED:
                actions.append(
                    "Electrolyse arretee : ne pas supposer que le chlore remontera sans action conforme "
                    "a la notice de l'installation."
                )
            if state.treatment.stabilized_tablet_status is StabilizedTabletStatus.CONSUMED:
                actions.append(
                    "Galets declares consommes : ne pas compter sur le doseur actuel pour remonter le chlore."
                )
        elif chlorine > state.config.free_chlorine_max_ppm:
            actions.append(
                f"Decision chlore : chlore libre {chlorine:.1f} ppm au-dessus de la borne haute declaree "
                f"{state.config.free_chlorine_max_ppm:.1f} ppm : ne pas ajouter de chlore ; "
                "suivre l'etiquette avant la baignade et re-mesurer."
            )
            if state.treatment.stabilized_tablet_status is StabilizedTabletStatus.ACTIVE:
                actions.append(
                    "Galets encore en place : verifier le doseur et la notice avant toute recharge."
                )
        else:
            actions.append(
                "Decision chlore : chlore libre dans la plage declaree. Aucune action de desinfection "
                "n'est a effectuer sur la base de cette mesure ; ne pas ajouter de galet par automatisme."
            )
        if chlorine > 10:
            actions.append(
                "Au-dela de 10 ppm, un test DPD peut etre decolore et afficher a tort une valeur basse ou nulle ; "
                "confirmer la mesure selon la notice du test."
            )
        return actions

    def build_supply_estimate(
        self, config: ProtocolConfig, treatment: TreatmentContext
    ) -> SupplyEstimate:
        """Construit un repère d'achat à partir du protocole, sans prédire le pH.

        La soude est un stock prudent configurable : la consommation réelle ne
        peut pas être déduite du seul pH de départ. Le bicarbonate est fondé sur
        le bilan TAC initial, complété par une marge d'achat explicite.
        """
        theoretical_bicarbonate_kg = self.chemistry.bicarbonate_kg(config, config.initial_tac_ppm)
        stabilized = treatment.disinfection_method is DisinfectionMethod.STABILIZED_TABLETS
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
        self,
        electrolysis_status: ElectrolysisStatus,
        disinfection_method: DisinfectionMethod,
        ph_regulator_status: PhRegulatorStatus | None = None,
        stabilized_tablet_status: StabilizedTabletStatus | None = None,
        stabilized_tablet_product: StabilizedTabletProduct | None = None,
    ) -> ProtocolState:
        """Enregistre le mode de désinfection actuellement appliqué au bassin."""
        state = self.active()
        state.treatment = TreatmentContext(
            electrolysis_status=electrolysis_status,
            disinfection_method=disinfection_method,
            ph_regulator_status=ph_regulator_status or state.treatment.ph_regulator_status,
            stabilized_tablet_status=stabilized_tablet_status
            or state.treatment.stabilized_tablet_status,
            stabilized_tablet_product=stabilized_tablet_product
            or state.treatment.stabilized_tablet_product,
        )
        if state.config.mode is ProtocolMode.RAISE_PH_TAC:
            state.supply_estimate = self.build_supply_estimate(state.config, state.treatment)
        state.add_event(
            "Contexte traitement : "
            f"desinfection active {disinfection_method.value}, "
            f"electrolyseur {electrolysis_status.value}, "
            f"regulateur pH {state.treatment.ph_regulator_status.value}, "
            f"galets {state.treatment.stabilized_tablet_status.value}"
        )
        self.repository.save(state)
        return state

    def set_naoh_concentration(
        self,
        concentration_g_l: float,
        source: NaOHConcentrationSource,
        label_percent: float | None = None,
        density_g_ml: float | None = None,
    ) -> ProtocolState:
        """Corrige la concentration du produit pour un protocole déjà commencé.

        Cette correction s'applique à tous les apports de soude confirmés de
        l'archive. C'est le comportement attendu lorsque le même bidon a été
        employé depuis le début ; le cumul en moles et les contrôles associés
        sont alors recalculés sans perdre les mesures ni les volumes versés.
        """
        state = self.active()
        if state.pending_naoh:
            raise ValueError(
                "Confirmez la dose de NaOH en attente, ou annulez-la si elle n'a pas ete versee, "
                "avant de changer la concentration."
            )

        previous = state.config.naoh_concentration_g_l
        values = state.config.model_dump()
        values.update(
            naoh_concentration_g_l=concentration_g_l,
            naoh_concentration_source=source,
            naoh_label_percent=label_percent,
            naoh_density_g_ml=density_g_ml,
        )
        state.config = ProtocolConfig.model_validate(values)
        for dose in state.naoh_doses:
            dose.coherence = self.enrich_check_with_treatment(
                state,
                self.chemistry.verify(
                    state.config,
                    ph_before=dose.ph_before,
                    tac_before_ppm=dose.tac_before_ppm,
                    ph_after=dose.ph_after,
                    tac_after_ppm=dose.tac_after_ppm,
                    naoh_ml=dose.naoh_ml,
                ),
            )
        self.refresh_cumulative_additions(state)
        state.supply_estimate = self.build_supply_estimate(state.config, state.treatment)
        state.add_event(
            "Concentration NaOH corrigee pour les apports confirmes : "
            f"{previous:.0f} vers {concentration_g_l:.0f} g/L ({source.value})"
        )
        self.repository.save(state)
        return state

    def record_stabilized_tablets(
        self, count: int, unit_mass_g: float | None, product_label: str
    ) -> ProtocolState:
        """Journalise des galets stabilisés réellement mis dans le doseur."""
        state = self.active()
        if state.treatment.disinfection_method is not DisinfectionMethod.STABILIZED_TABLETS:
            raise ValueError(
                "Declarez d'abord --disinfection galets_stabilises avec la commande treatment."
            )
        record = StabilizedTabletRecord(
            count=count, unit_mass_g=unit_mass_g, product_label=product_label
        )
        state.stabilized_tablets.append(record)
        state.treatment.stabilized_tablet_status = StabilizedTabletStatus.ACTIVE
        mass = f" de {unit_mass_g:.0f} g" if unit_mass_g is not None else ""
        state.add_event(f"Galets stabilises ajoutes : {count}{mass} ({product_label})")
        if state.treatment.stabilized_tablet_product in {
            StabilizedTabletProduct.TRICHLOR_MULTIFUNCTION_GCCHL4EC,
            StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC,
        }:
            state.add_event(
                "Securite galets au trichlore : ne jamais melanger avec l'acide sulfurique "
                "ni placer les produits dans le meme recipient ou doseur"
            )
        self.repository.save(state)
        return state

    def tablet_guidance(self, m3_per_tablet: float | None = None) -> tuple[ProtocolState, int, float]:
        """Retourne une charge initiale de galets issue de l'étiquette, sans l'enregistrer.

        Le galet n'est jamais rechargé automatiquement : sa dissolution dépend de
        la température, de la filtration et du doseur. Une mesure de chlore libre
        et une vérification du CYA restent donc préalables.
        """
        state = self.active()
        if state.treatment.disinfection_method is not DisinfectionMethod.STABILIZED_TABLETS:
            raise ValueError("Ce conseil est reserve aux galets stabilises declares dans treatment.")
        if not state.water_measurements or state.water_measurements[-1].free_chlorine_ppm is None:
            raise ValueError("Enregistrez d'abord une mesure de chlore libre avec record-water.")
        chlorine = state.water_measurements[-1].free_chlorine_ppm
        assert chlorine is not None
        if chlorine >= state.config.free_chlorine_min_ppm:
            raise ValueError(
                "Le chlore libre est deja dans ou au-dessus de la plage declaree ; ne rechargez pas "
                "les galets automatiquement."
            )
        if state.cyanuric_acid_measurements and state.cyanuric_acid_measurements[-1].cya_ppm >= 50:
            raise ValueError(
                "CYA a 50 ppm ou plus : ne pas planifier de galets stabilises ; suivre le renouvellement "
                "d'eau et l'etiquette."
            )
        ratio = m3_per_tablet
        if ratio is None:
            if (
                state.treatment.stabilized_tablet_product
                is StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC
            ):
                ratio = 25.0
            else:
                raise ValueError(
                    "Saisissez le volume par galet lu sur l'etiquette avec --m3-per-tablet ; "
                    "aucun ratio fiable n'est archive pour ce produit."
                )
        if ratio <= 0:
            raise ValueError("Le volume couvert par un galet doit etre positif.")
        return state, ceil(state.config.pool_volume_m3 / ratio), ratio

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
            if active.supply_estimate is None and active.config.mode is ProtocolMode.RAISE_PH_TAC:
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
            step=(
                ProtocolStep.TAC_TO_TARGET
                if config.mode is ProtocolMode.RAISE_TAC
                else (
                    ProtocolStep.ACID_TO_TARGET
                    if config.mode is ProtocolMode.LOWER_PH_MONITORING
                    else (
                    ProtocolStep.HIGH_PH_MONITORING
                    if config.mode
                    in {
                        ProtocolMode.HIGH_PH_MONITORING,
                        ProtocolMode.DISINFECTION_MONITORING,
                    }
                    else ProtocolStep.PH_TO_INTERMEDIATE
                    )
                )
            ),
        )
        if config.mode is ProtocolMode.RAISE_PH_TAC:
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
        elif config.mode is ProtocolMode.RAISE_TAC:
            state.add_event(
                "Correction TAC creee : bicarbonate calcule en lots, avec mesure de confirmation"
            )
        elif config.mode is ProtocolMode.LOWER_PH_MONITORING:
            state.add_event(
                "Correction pH bas creee : lots d'acide sulfurique 15 % limites a 0,1 pH, "
                "avec mesure obligatoire et sans melange avec le chlore stabilise"
            )
        elif config.mode is ProtocolMode.DISINFECTION_MONITORING:
            state.add_event(
                "Surveillance desinfectant creee : les galets sont journalises, sans nombre de galets calcule"
            )
        else:
            state.add_event(
                "Surveillance pH haut creee : aucune dose d'acide ou de chlore n'est calculee"
            )
        self.repository.save(state)
        return state

    def record_water_measurement(
        self, ph: float, tac_ppm: float, free_chlorine_ppm: float | None = None
    ) -> ProtocolState:
        """Archive une mesure eau complète pour le parcours de surveillance."""
        state = self.active()
        if state.step is not ProtocolStep.HIGH_PH_MONITORING:
            raise ValueError("La mesure eau sans dose est reservee aux protocoles de surveillance.")
        if (
            state.config.mode is ProtocolMode.DISINFECTION_MONITORING
            and free_chlorine_ppm is None
        ):
            raise ValueError("Le chlore libre est requis pour le protocole de desinfection.")
        self.validate_tac_measurement(state, tac_ppm)
        measurement = WaterMeasurement(ph=ph, tac_ppm=tac_ppm, free_chlorine_ppm=free_chlorine_ppm)
        state.water_measurements.append(measurement)
        state.current_ph = ph
        state.current_tac_ppm = tac_ppm
        state.add_event(
            f"Mesure surveillance : pH {ph:.2f}, TAC {tac_ppm:.0f} ppm, "
            f"chlore libre {free_chlorine_ppm:.1f} ppm"
            if free_chlorine_ppm is not None
            else f"Mesure surveillance : pH {ph:.2f}, TAC {tac_ppm:.0f} ppm"
        )
        for action in self.water_actions(state):
            state.add_event(f"Conclusion de surveillance : {action}")
        self.repository.save(state)
        return state

    def prepare_sulfuric_acid(self, requested_ml: float | None = None) -> ProtocolState:
        """Prépare un lot d'acide 15 % issu de la notice, jamais supérieur à -0,1 pH.

        La quantité est un repère produit et non un modèle chimique du bassin.
        Elle est donc plafonnée, sans second lot possible avant mesure pH/TAC.
        """
        state = self.active()
        if state.step is not ProtocolStep.ACID_TO_TARGET:
            raise ValueError("L'acide sulfurique n'est pas l'etape active du protocole.")
        if state.pending_acid:
            raise ValueError("Un lot d'acide est deja en attente de mesure.")
        if state.treatment.ph_regulator_status is PhRegulatorStatus.RUNNING:
            raise ValueError(
                "Arretez ou isolez le regulateur pH avant une correction manuelle d'acide."
            )
        if (
            state.treatment.disinfection_method is DisinfectionMethod.STABILIZED_TABLETS
            and state.treatment.stabilized_tablet_status is StabilizedTabletStatus.ACTIVE
        ):
            raise ValueError(
                "Suspendre ou retirer les galets au trichlore et le declarer avec treatment "
                "avant tout ajout d'acide sulfurique."
            )
        gap = state.current_ph - state.config.target_ph
        if gap <= 0:
            state.step = ProtocolStep.COMPLETE
            state.add_event("pH cible deja atteint : aucun acide prepare")
            self.repository.save(state)
            return state
        correction_ph = min(gap, self.MAX_ACID_BATCH_PH)
        maximum_ml = (
            self.SULFURIC_ACID_15_ML_PER_10_M3_PER_0_1_PH
            * (state.config.pool_volume_m3 / 10)
            * (correction_ph / 0.1)
        )
        acid_ml = requested_ml if requested_ml is not None else maximum_ml
        if acid_ml > maximum_ml + 1e-9:
            raise ValueError(
                f"Le lot ne peut pas exceder {maximum_ml:.0f} mL : la notice impose une correction "
                "par etapes de 0,1 pH maximum."
            )
        state.pending_acid = PendingAcidDose(
            ph_before=state.current_ph,
            tac_before_ppm=state.current_tac_ppm,
            acid_ml=acid_ml,
            target_ph_for_batch=max(state.current_ph - correction_ph, state.config.target_ph),
        )
        state.add_event(
            f"Lot acide sulfurique 15 % prepare : {acid_ml:.0f} mL pour une baisse cible maximale de "
            f"{correction_ph:.1f} pH"
        )
        self.repository.save(state)
        return state

    def record_sulfuric_acid_measurement(self, ph: float, tac_ppm: float) -> ProtocolState:
        """Confirme un lot acide avec mesures réelles et n'autorise ensuite qu'un nouveau petit lot."""
        state = self.active()
        self.validate_tac_measurement(state, tac_ppm)
        pending = state.pending_acid
        if pending is None:
            raise ValueError("Aucun lot d'acide en attente.")
        state.acid_doses.append(
            AcidDoseRecord(
                ph_before=pending.ph_before,
                tac_before_ppm=pending.tac_before_ppm,
                acid_ml=pending.acid_ml,
                ph_after=ph,
                tac_after_ppm=tac_ppm,
            )
        )
        state.pending_acid = None
        state.current_ph = ph
        state.current_tac_ppm = tac_ppm
        self.refresh_cumulative_additions(state)
        if ph <= state.config.target_ph:
            state.step = ProtocolStep.COMPLETE
            state.add_event("pH cible atteint apres lot acide : ne pas ajouter d'acide supplementaire")
        else:
            state.add_event(
                f"Mesures apres acide : pH {ph:.2f}, TAC {tac_ppm:.0f} ppm ; reevaluer un seul lot"
            )
        self.repository.save(state)
        return state

    def cancel_pending_acid(self) -> ProtocolState:
        """Annule un lot d'acide non versé, sans masquer les mesures précédentes."""
        state = self.active()
        pending = state.pending_acid
        if pending is None:
            raise ValueError("Aucun lot d'acide en attente a annuler.")
        state.pending_acid = None
        state.add_event(f"Lot acide annule avant ajout : {pending.acid_ml:.0f} mL")
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

    def cancel_pending_bicarbonate(self) -> ProtocolState:
        """Annule un lot de bicarbonate préparé uniquement s'il n'a pas été ajouté."""
        state = self.active()
        pending = state.pending_bicarbonate
        if pending is None:
            raise ValueError("Aucun lot de bicarbonate en attente a annuler.")
        state.pending_bicarbonate = None
        state.add_event(f"Lot bicarbonate annule avant ajout : {pending.bicarbonate_kg:.2f} kg")
        self.repository.save(state)
        return state

    def cancel_protocol(self) -> ProtocolState:
        """Archive le protocole actif comme annulé, sans effacer son journal.

        Les préparations en attente sont supprimées du suivi car elles ne sont
        pas des apports confirmés. Les doses et mesures précédentes sont gardées.
        """
        state = self.active()
        state.pending_naoh = None
        state.pending_acid = None
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
        if state.pending_naoh or state.pending_acid or state.pending_bicarbonate:
            raise ValueError("Annulez d'abord la dose preparee apres la mesure a corriger.")

        latest_naoh = state.naoh_doses[-1] if state.naoh_doses else None
        latest_acid = state.acid_doses[-1] if state.acid_doses else None
        latest_bicarbonate = state.bicarbonate_doses[-1] if state.bicarbonate_doses else None
        if latest_naoh is None and latest_acid is None and latest_bicarbonate is None:
            raise ValueError("Aucune mesure enregistree a corriger.")

        latest = max(
            (record for record in (latest_naoh, latest_acid, latest_bicarbonate) if record is not None),
            key=lambda record: record.recorded_at,
        )
        if latest is latest_bicarbonate:
            record = latest_bicarbonate
            assert record is not None
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
            if tac_ppm >= state.config.target_tac_ppm:
                state.step = (
                    ProtocolStep.COMPLETE
                    if state.config.mode is ProtocolMode.RAISE_TAC
                    else ProtocolStep.PH_TO_TARGET
                )
            else:
                state.step = ProtocolStep.TAC_TO_TARGET
            product = "bicarbonate"
        elif latest is latest_acid:
            record = latest_acid
            assert record is not None
            record.ph_after = ph
            record.tac_after_ppm = tac_ppm
            state.step = (
                ProtocolStep.COMPLETE if ph <= state.config.target_ph else ProtocolStep.ACID_TO_TARGET
            )
            product = "acide sulfurique"
        else:
            record = latest_naoh
            assert record is not None
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
        total_kg = self.chemistry.bicarbonate_kg(state.config, measured_tac_ppm)
        kg = min(total_kg, SETTINGS.workflow.bicarbonate_batch_max_kg)
        state.current_tac_ppm = measured_tac_ppm
        state.pending_bicarbonate = PendingBicarbonatePlan(
            ph_before=state.current_ph,
            tac_before_ppm=measured_tac_ppm,
            bicarbonate_kg=kg,
            bicarbonate_total_kg=total_kg,
        )
        state.add_event(
            f"Lot bicarbonate prepare : {kg:.2f} kg (besoin calcule : {total_kg:.2f} kg)"
        )
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
            if state.config.mode is ProtocolMode.RAISE_TAC:
                state.step = ProtocolStep.COMPLETE
                state.add_event("TAC cible confirme : protocole de correction TAC termine")
            else:
                state.step = ProtocolStep.PH_TO_TARGET
                state.add_event("TAC cible confirme : passage a l'ajustement final du pH")
        else:
            state.add_event(f"TAC insuffisant : {tac_ppm:.1f} ppm, apport complementaire requis")
        self.repository.save(state)
        return state
