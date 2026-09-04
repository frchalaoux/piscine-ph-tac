"""Bilans de matière et modèle carbonate simplifié à 25 °C.

Ces calculs préparent les apports et signalent des incohérences ; ils ne pilotent
jamais automatiquement une dose. Les mesures réelles du bassin restent la
référence opérationnelle.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from .models import CoherenceCheck, CumulativeAdditions, ProtocolConfig
from .settings import SETTINGS


@dataclass(frozen=True)
class BucketPreparation:
    """Volumes sûrs à préparer dans un seau pour une dose de NaOH.

    ``useful_volume_l`` exclut volontairement la garde libre du seau.
    """

    naoh_ml: float
    water_l: float
    useful_volume_l: float


class ChemistryCalculator:
    """Calcule les bilans NaOH/NaHCO3 et contrôle la cohérence pH/TAC.

    Les constantes décrivent une approximation carbonate à 25 °C, regroupée ici
    pour rendre les unités, tolérances et limites vérifiables.
    """

    # Masses molaires (g/mol) employées dans les conversions de matière.
    molar_mass_naoh_g_mol: ClassVar[float] = 39.997
    molar_mass_nahco3_g_mol: ClassVar[float] = 84.0066
    # Masse équivalente de CaCO3 (g/équivalent), unité usuelle du TAC.
    equivalent_mass_caco3_g_eq: ClassVar[float] = 50.043
    # Constantes d'acidité du système carbonate et produit ionique de l'eau à 25 °C.
    k1: ClassVar[float] = 10**-6.35
    k2: ClassVar[float] = 10**-10.33
    kw: ClassVar[float] = 1e-14
    # Limites de préparation : garde libre et fraction maximale de NaOH du volume utile.
    bucket_freeboard_fraction: ClassVar[float] = 0.20
    naoh_max_fraction_of_useful_volume: ClassVar[float] = 0.10
    # Tolérances de contrôle, adaptées à la précision des mesures du protocole.
    ph_tolerance: ClassVar[float] = 0.40
    tac_tolerance_ppm: ClassVar[float] = 10.0
    # Domaine borné et nombre d'itérations de la dichotomie du modèle pH.
    ph_solver_min: ClassVar[float] = 2.0
    ph_solver_max: ClassVar[float] = 12.5
    ph_solver_iterations: ClassVar[int] = 80
    # Au-delà, le carbone inféré rend le modèle carbonate fermé inexploitable.
    maximum_usable_carbon_mol_l: ClassVar[float] = 0.01

    def naoh_molarity(self, config: ProtocolConfig) -> float:
        """Convertit la concentration massique de NaOH (g/L) en mol/L."""
        return config.naoh_concentration_g_l / self.molar_mass_naoh_g_mol

    def useful_bucket_volume_l(self, config: ProtocolConfig) -> float:
        """Retourne le volume utilisable après réservation de la garde libre."""
        return config.bucket_volume_l * (1 - self.bucket_freeboard_fraction)

    def prepare_bucket(self, config: ProtocolConfig, requested_naoh_ml: float) -> BucketPreparation:
        """Calcule eau et soude sans dépasser les limites opérationnelles du seau.

        Le volume de soude est limité pour garder un mélange manipulable. Cette
        fonction ne remplace pas les consignes de sécurité du fabricant.
        """
        useful_volume_l = self.useful_bucket_volume_l(config)
        maximum_ml = useful_volume_l * self.naoh_max_fraction_of_useful_volume * 1_000
        if not 0 < requested_naoh_ml <= maximum_ml:
            raise ValueError(
                f"La dose doit etre comprise entre 0 et {maximum_ml:.0f} mL pour ce seau."
            )
        return BucketPreparation(
            naoh_ml=requested_naoh_ml,
            water_l=useful_volume_l - requested_naoh_ml / 1_000,
            useful_volume_l=useful_volume_l,
        )

    def suggested_naoh_ml(self, current_ph: float, target_ph: float) -> float:
        """Retourne un repère de 250, 100 ou 50 mL selon l'écart de pH.

        Cette suggestion doit être adaptée à la réaction réellement observée.
        """
        gap = target_ph - current_ph
        if gap > SETTINGS.workflow.naoh_large_gap_ph:
            return SETTINGS.workflow.naoh_large_dose_ml
        if gap > SETTINGS.workflow.naoh_medium_gap_ph:
            return SETTINGS.workflow.naoh_medium_dose_ml
        return SETTINGS.workflow.naoh_small_dose_ml

    def bicarbonate_kg(self, config: ProtocolConfig, current_tac_ppm: float) -> float:
        """Calcule la masse théorique de NaHCO3 pour atteindre le TAC cible.

        La conversion utilise les ppm équivalent CaCO3 et un équivalent par mole
        de bicarbonate. Un TAC déjà au-dessus de la cible donne zéro.
        """
        increase_ppm = max(0.0, config.target_tac_ppm - current_tac_ppm)
        return (
            increase_ppm
            * config.pool_volume_m3
            * (self.molar_mass_nahco3_g_mol / self.equivalent_mass_caco3_g_eq)
            / 1_000
        )

    def bicarbonate_batches_kg(
        self, total_kg: float, maximum_kg: float | None = None
    ) -> list[float]:
        """Découpe un apport total en portions au plus égales à ``maximum_kg``.

        Sans valeur explicite, la taille de portion est l'option opérationnelle
        ``bicarbonate_batch_max_kg`` de ``defaults.json``.
        """
        if maximum_kg is None:
            maximum_kg = SETTINGS.workflow.bicarbonate_batch_max_kg
        if maximum_kg <= 0:
            raise ValueError("La masse maximale d'un apport doit etre strictement positive.")
        batches: list[float] = []
        remaining = round(total_kg, 3)
        while remaining > maximum_kg:
            batches.append(maximum_kg)
            remaining = round(remaining - maximum_kg, 3)
        if remaining:
            batches.append(remaining)
        return batches

    def tac_eq_l(self, tac_ppm: float) -> float:
        """Convertit un TAC en ppm CaCO3 en équivalents par litre."""
        return tac_ppm / (self.equivalent_mass_caco3_g_eq * 1_000)

    def tac_ppm(self, alkalinity_eq_l: float) -> float:
        """Convertit une alcalinité en équivalents par litre en ppm CaCO3."""
        return alkalinity_eq_l * self.equivalent_mass_caco3_g_eq * 1_000

    def carbonate_fractions(self, ph: float) -> tuple[float, float, float]:
        """Retourne les fractions alpha de CO2, HCO3- et CO3-- à un pH donné."""
        h = 10 ** (-ph)
        denominator = h * h + self.k1 * h + self.k1 * self.k2
        return h * h / denominator, self.k1 * h / denominator, self.k1 * self.k2 / denominator

    def carbon_from_ph_tac(self, ph: float, tac_ppm: float) -> float:
        """Infère le carbone inorganique dissous avec le modèle carbonate fermé."""
        _, bicarbonate, carbonate = self.carbonate_fractions(ph)
        h = 10 ** (-ph)
        return (self.tac_eq_l(tac_ppm) - self.kw / h + h) / (bicarbonate + 2 * carbonate)

    def alkalinity_from_carbon_ph(self, carbon_mol_l: float, ph: float) -> float:
        """Calcule l'alcalinité d'un système carbonate fermé à pH imposé."""
        _, bicarbonate, carbonate = self.carbonate_fractions(ph)
        h = 10 ** (-ph)
        return carbon_mol_l * (bicarbonate + 2 * carbonate) + self.kw / h - h

    def ph_from_carbon_alkalinity(self, carbon_mol_l: float, alkalinity_eq_l: float) -> float:
        """Résout par dichotomie le pH compatible avec carbone et alcalinité fixés."""
        low, high = self.ph_solver_min, self.ph_solver_max
        for _ in range(self.ph_solver_iterations):
            midpoint = (low + high) / 2
            if self.alkalinity_from_carbon_ph(carbon_mol_l, midpoint) < alkalinity_eq_l:
                low = midpoint
            else:
                high = midpoint
        return (low + high) / 2

    def verify(
        self,
        config: ProtocolConfig,
        *,
        ph_before: float,
        tac_before_ppm: float,
        ph_after: float,
        tac_after_ppm: float,
        naoh_ml: float = 0.0,
        bicarbonate_kg: float = 0.0,
    ) -> CoherenceCheck:
        """Compare une mesure après ajout au bilan d'un système carbonate fermé.

        La prédiction de pH est désactivée si le carbone inféré est irréaliste.
        Le contrôle retourne alors le TAC théorique et les avertissements, sans
        bloquer le protocole ni remplacer les mesures réelles.
        """
        volume_l = config.pool_volume_m3 * 1_000
        carbon_before = self.carbon_from_ph_tac(ph_before, tac_before_ppm)
        naoh_eq_l = (naoh_ml / 1_000) * self.naoh_molarity(config) / volume_l
        bicarbonate_eq_l = (bicarbonate_kg * 1_000 / self.molar_mass_nahco3_g_mol) / volume_l
        expected_tac = self.tac_ppm(self.tac_eq_l(tac_before_ppm) + naoh_eq_l + bicarbonate_eq_l)
        warnings: list[str] = []
        expected_ph: float | None = None
        ph_difference: float | None = None
        # À très faible pH, un TAC positif peut faire déduire un carbone dissous
        # absurde : ne pas afficher alors une prédiction de pH trompeuse.
        if carbon_before > self.maximum_usable_carbon_mol_l:
            warnings.append("Le couple pH/TAC implique un carbone dissous anormalement eleve.")
            warnings.append(
                "Le modele carbonate ferme ne peut pas predire utilement le pH dans ce cas."
            )
        else:
            expected_ph = self.ph_from_carbon_alkalinity(
                carbon_before + bicarbonate_eq_l, self.tac_eq_l(expected_tac)
            )
            ph_difference = ph_after - expected_ph
            if abs(ph_difference) > self.ph_tolerance:
                warnings.append("L'ecart de pH depasse la tolerance du modele.")
        if abs(tac_after_ppm - expected_tac) > self.tac_tolerance_ppm:
            warnings.append("L'ecart de TAC depasse la tolerance du modele.")
        return CoherenceCheck(
            expected_ph=expected_ph,
            expected_tac_ppm=expected_tac,
            ph_difference=ph_difference,
            tac_difference_ppm=tac_after_ppm - expected_tac,
            inferred_carbon_mol_l=carbon_before,
            is_consistent=not warnings,
            warnings=warnings,
        )

    def cumulative_additions(
        self, config: ProtocolConfig, naoh_solution_ml: float, bicarbonate_kg: float
    ) -> CumulativeAdditions:
        """Retourne les apports confirmés et leur contribution théorique au TAC.

        L'appelant ne doit fournir que les doses effectivement mesurées ; une
        préparation en attente ne doit jamais figurer dans ce cumul.
        """
        volume_l = config.pool_volume_m3 * 1_000
        naoh_moles = (naoh_solution_ml / 1_000) * self.naoh_molarity(config)
        bicarbonate_moles = bicarbonate_kg * 1_000 / self.molar_mass_nahco3_g_mol
        tac_from_naoh = self.tac_ppm(naoh_moles / volume_l)
        tac_from_bicarbonate = self.tac_ppm(bicarbonate_moles / volume_l)
        return CumulativeAdditions(
            naoh_solution_ml=naoh_solution_ml,
            naoh_moles=naoh_moles,
            bicarbonate_kg=bicarbonate_kg,
            bicarbonate_moles=bicarbonate_moles,
            theoretical_tac_from_naoh_ppm=tac_from_naoh,
            theoretical_tac_from_bicarbonate_ppm=tac_from_bicarbonate,
            theoretical_tac_total_ppm=tac_from_naoh + tac_from_bicarbonate,
        )
