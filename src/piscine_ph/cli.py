"""Interface de ligne de commande Typer du protocole pH/TAC.

Ce module se limite à présenter les données et à collecter les options. Les
règles de sécurité du workflow, les transitions et les écritures JSON vivent
dans :mod:`piscine_ph.service`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from .chemistry import ChemistryCalculator
from .models import (
    DisinfectionMethod,
    ElectrolysisStatus,
    NaOHConcentrationSource,
    PendingBicarbonatePlan,
    PhRegulatorStatus,
    ProtocolConfig,
    ProtocolMode,
    ProtocolState,
    ProtocolStep,
    StabilizedTabletStatus,
    TreatmentContext,
)
from .repository import JsonProtocolRepository
from .service import ProtocolService
from .settings import SETTINGS

app = typer.Typer(no_args_is_help=True, help="Suivi progressif de correction pH/TAC.")


def service(root: Path = Path("data/protocoles")) -> ProtocolService:
    """Construit le service CLI utilisant le répertoire d'archives indiqué.

    L'argument permet aux tests ou à une future interface d'utiliser un autre
    répertoire, alors que la CLI normale conserve ``data/protocoles``.
    """
    return ProtocolService(JsonProtocolRepository(root))


def show_check(state: ProtocolState) -> None:
    """Affiche le dernier contrôle de cohérence disponible dans ``state``.

    Le dernier ajout, NaOH ou bicarbonate, est sélectionné par son horodatage.
    Un pH théorique absent est une limite connue du modèle, pas une erreur CLI.
    """
    check = state.naoh_doses[-1].coherence if state.naoh_doses else None
    if state.bicarbonate_doses and (
        check is None or state.bicarbonate_doses[-1].recorded_at > state.naoh_doses[-1].recorded_at
    ):
        check = state.bicarbonate_doses[-1].coherence
    if not check:
        return
    if check.expected_ph is None:
        typer.echo(f"Controle : TAC theorique {check.expected_tac_ppm:.1f} ppm.")
        typer.secho(
            "Prediction de pH indisponible : le modele carbonate ne s'applique pas a ces mesures.",
            fg=typer.colors.YELLOW,
        )
    else:
        typer.echo(
            f"Controle : pH attendu {check.expected_ph:.2f}, TAC theorique {check.expected_tac_ppm:.1f} ppm."
        )
    typer.echo("Le TAC mesure est lu par pas de 10 ppm ; ne cherchez pas une precision inferieure.")
    for warning in check.warnings:
        typer.secho(f"Alerte : {warning}", fg=typer.colors.YELLOW)


def next_command(state: ProtocolState) -> str:
    """Retourne la commande suivante selon l'etat concret du protocole."""
    return ProtocolService.next_command(state)


def show_next_command(state: ProtocolState) -> None:
    """Affiche la commande logique suivante, calculée par :func:`next_command`."""
    typer.secho(f"Commande suivante : {next_command(state)}", fg=typer.colors.CYAN)


def show_cumulative_additions(state: ProtocolState) -> None:
    """Affiche les produits confirmés et leur contribution TAC théorique cumulée."""
    cumulative = state.cumulative_additions
    typer.echo(
        "Cumul verse : "
        f"NaOH {cumulative.naoh_solution_ml:.0f} mL ({cumulative.naoh_moles:.3f} mol), "
        f"NaHCO3 {cumulative.bicarbonate_kg:.2f} kg ({cumulative.bicarbonate_moles:.2f} mol)."
    )
    typer.echo(
        "Contribution TAC theorique cumulee : "
        f"+{cumulative.theoretical_tac_from_naoh_ppm:.1f} ppm (NaOH), "
        f"+{cumulative.theoretical_tac_from_bicarbonate_ppm:.1f} ppm (NaHCO3)."
    )


def show_treatment(state: ProtocolState) -> None:
    """Affiche le contexte de désinfection et les mesures de stabilisant."""
    treatment = state.treatment
    typer.echo(
        "Traitement declare : "
        f"desinfection active {treatment.disinfection_method.value}.\n"
        f"Electrolyseur au sel : {treatment.electrolysis_status.value}.\n"
        f"Regulateur pH : {treatment.ph_regulator_status.value}.\n"
        f"Doseur de galets stabilises : {treatment.stabilized_tablet_status.value}."
    )
    if state.stabilized_tablets:
        count = sum(record.count for record in state.stabilized_tablets)
        typer.echo(f"Galets stabilises journalises : {count}.")
    if state.cyanuric_acid_measurements:
        measurement = state.cyanuric_acid_measurements[-1]
        typer.echo(
            f"Dernier CYA : {measurement.cya_ppm:.0f} ppm ({measurement.recorded_at:%Y-%m-%d})."
        )
    for warning in ProtocolService.treatment_warnings(state):
        typer.secho(f"Alerte traitement : {warning}", fg=typer.colors.YELLOW)


def show_water_actions(state: ProtocolState) -> None:
    """Affiche le dernier constat de surveillance sans le transformer en dosage."""
    if state.water_measurements:
        measurement = state.water_measurements[-1]
        typer.echo(
            "Derniere mesure eau : "
            f"pH {measurement.ph:.2f}, TAC {measurement.tac_ppm:.0f} ppm, "
            f"chlore libre {measurement.free_chlorine_ppm:.1f} ppm."
        )
    for action in ProtocolService.water_actions(state):
        typer.secho(f"Surveillance : {action}", fg=typer.colors.YELLOW)


def show_supply_estimate(state: ProtocolState) -> None:
    """Affiche le repère d'achat archivé, sans le présenter comme un dosage."""
    estimate = state.supply_estimate
    if estimate is None:
        return
    margin = (
        " ; marge galets stabilises incluse" if estimate.includes_stabilized_chlorine_margin else ""
    )
    typer.secho("Approvisionnement indicatif (pas une dose) :", fg=typer.colors.CYAN)
    typer.echo(
        f"Soude {state.config.naoh_concentration_g_l:.0f} g/L : "
        f"{estimate.naoh_solution_recommended_l:.0f} L a acheter "
        "(repere prudent, non predictif)."
    )
    typer.echo(
        f"Bicarbonate : {estimate.bicarbonate_recommended_kg:.0f} kg a acheter "
        f"(besoin theorique {estimate.bicarbonate_theoretical_kg:.2f} kg, "
        f"TAC de depart {estimate.basis_tac_ppm:.0f} ppm{margin})."
    )


def show_naoh_declaration(state: ProtocolState) -> None:
    """Affiche la concentration réellement archivée et son mode de détermination."""
    config = state.config
    detail = config.naoh_concentration_source.value
    if config.naoh_concentration_source is NaOHConcentrationSource.MASS_PERCENT:
        detail = (
            f"{config.naoh_label_percent:.1f} % m/m, densite {config.naoh_density_g_ml:.3f} g/mL"
        )
    elif config.naoh_concentration_source is NaOHConcentrationSource.VOLUME_PERCENT:
        detail = f"{config.naoh_label_percent:.1f} % m/v"
    typer.secho(
        f"Soude archivee : {config.naoh_concentration_g_l:.0f} g/L ({detail}).",
        fg=typer.colors.CYAN,
    )


def prompted_choice(question: str, choices: list[str], default: int = 1) -> int:
    """Affiche des choix numérotés et redemande tant que l'entrée est invalide."""
    typer.echo(question)
    for index, choice in enumerate(choices, start=1):
        typer.echo(f"  {index}. {choice}")
    while True:
        selected = typer.prompt("Votre choix", default=default, type=int)
        if 1 <= selected <= len(choices):
            return selected
        typer.secho("Choix invalide. Recommencez.", fg=typer.colors.YELLOW)


def prompt_naoh_concentration() -> tuple[
    float, NaOHConcentrationSource, float | None, float | None
]:
    """Guide la conversion de l'étiquette vers la seule unité utilisée par le modèle."""
    typer.secho("SOUDE — CONCENTRATION", fg=typer.colors.CYAN, bold=True)
    typer.echo("Utiliser l'etiquette ou la FDS ; le poids du bidon plein seul ne suffit pas.")
    typer.echo("Repere de lecture — exemples seulement, pas des valeurs par defaut :")
    typer.echo("  - '300 g/L' : choisir 1 et saisir 300.")
    typer.echo("  - '30 % m/m' avec densite '1,33 g/mL' : choisir 2, saisir 30 puis 1,33.")
    typer.echo("    Le programme calculera alors 399 g/L.")
    typer.echo("  - '30 % m/v' : choisir 3 et saisir 30 ; cela correspond a 300 g/L.")
    typer.secho(
        "Si l'unite ou la densite n'est pas indiquee, arretez-vous et consultez la FDS du produit ; "
        "ne la devinez pas.",
        fg=typer.colors.YELLOW,
    )
    choice = prompted_choice(
        "Comment la concentration est-elle indiquee ?",
        [
            "Valeur directe en g/L",
            "Pourcentage massique (% m/m) et densite en g/mL",
            "Pourcentage volumique (% m/v)",
        ],
    )
    if choice == 1:
        concentration = typer.prompt("Concentration NaOH en g/L (etiquette ou FDS)", type=float)
        return concentration, NaOHConcentrationSource.GRAMS_PER_LITRE, None, None
    percent = typer.prompt("Pourcentage de NaOH indique sur l'etiquette", type=float)
    if choice == 2:
        density = typer.prompt("Densite en g/mL indiquee par la FDS (ne pas deviner)", type=float)
        concentration = percent * density * 10
        typer.secho(
            f"Conversion retenue : {percent:.1f} % m/m x {density:.3f} g/mL = "
            f"{concentration:.0f} g/L.",
            fg=typer.colors.GREEN,
        )
        return concentration, NaOHConcentrationSource.MASS_PERCENT, percent, density
    concentration = percent * 10
    typer.secho(
        f"Conversion retenue : {percent:.1f} % m/v = {concentration:.0f} g/L.",
        fg=typer.colors.GREEN,
    )
    return concentration, NaOHConcentrationSource.VOLUME_PERCENT, percent, None


def prompt_treatment_context() -> tuple[TreatmentContext, float | None]:
    """Collecte le traitement qui influence les avertissements et le stock conseillé."""
    typer.secho("TRAITEMENT EN COURS", fg=typer.colors.CYAN, bold=True)
    electrolysis_choice = prompted_choice(
        "Etat de l'electrolyse ?", ["Arretee", "En marche", "Inconnu"], default=3
    )
    electrolysis = {
        1: ElectrolysisStatus.STOPPED,
        2: ElectrolysisStatus.RUNNING,
        3: ElectrolysisStatus.UNKNOWN,
    }[electrolysis_choice]
    disinfection_choice = prompted_choice(
        "Quelle desinfection est active ?",
        [
            "Electrolyse au sel",
            "Galets stabilises",
            "Dichlore stabilise",
            "Chlore non stabilise",
            "Inconnue",
        ],
        default=5,
    )
    disinfection = {
        1: DisinfectionMethod.SALT_ELECTROLYSIS,
        2: DisinfectionMethod.STABILIZED_TABLETS,
        3: DisinfectionMethod.STABILIZED_DICHLOR,
        4: DisinfectionMethod.UNSTABILIZED_CHLORINE,
        5: DisinfectionMethod.UNKNOWN,
    }[disinfection_choice]
    regulator_choice = prompted_choice(
        "Etat du regulateur de pH ?", ["Arrete", "En marche", "Inconnu"], default=3
    )
    regulator = {
        1: PhRegulatorStatus.STOPPED,
        2: PhRegulatorStatus.RUNNING,
        3: PhRegulatorStatus.UNKNOWN,
    }[regulator_choice]
    tablets = StabilizedTabletStatus.UNKNOWN
    if disinfection is DisinfectionMethod.STABILIZED_TABLETS:
        tablet_choice = prompted_choice(
            "Etat des galets dans le doseur ?",
            ["En place", "Consommes", "Suspendus", "Non necessaires", "Inconnu"],
            default=5,
        )
        tablets = {
            1: StabilizedTabletStatus.ACTIVE,
            2: StabilizedTabletStatus.CONSUMED,
            3: StabilizedTabletStatus.PAUSED,
            4: StabilizedTabletStatus.NOT_NEEDED,
            5: StabilizedTabletStatus.UNKNOWN,
        }[tablet_choice]
    cya = None
    if disinfection in {
        DisinfectionMethod.STABILIZED_TABLETS,
        DisinfectionMethod.STABILIZED_DICHLOR,
    } and typer.confirm("Avez-vous une mesure CYA recente a enregistrer ?", default=False):
        cya = typer.prompt("CYA mesure en ppm", type=float)
    return (
        TreatmentContext(
            electrolysis_status=electrolysis,
            disinfection_method=disinfection,
            ph_regulator_status=regulator,
            stabilized_tablet_status=tablets,
        ),
        cya,
    )


def show_bucket_preparation(naoh_ml: float, water_l: float, useful_volume_l: float) -> None:
    """Présente les volumes à préparer dans le seau pour une dose de NaOH."""
    typer.secho("Prochaine dose preparee", fg=typer.colors.GREEN)
    typer.echo(f"Mettre {water_l:.2f} L d'eau dans le seau, puis {naoh_ml:.0f} mL de NaOH.")
    typer.echo(f"Volume utile : {useful_volume_l:.2f} L. Mesurer ensuite pH et TAC du bassin.")


def show_bicarbonate_plan(pending: PendingBicarbonatePlan) -> None:
    """Présente un seul lot TAC et l'attente obligatoire avant sa confirmation."""
    total_kg = pending.bicarbonate_total_kg or pending.bicarbonate_kg
    wait_minutes = SETTINGS.workflow.bicarbonate_wait_min_minutes
    wait_text = f"{wait_minutes // 60} h" if wait_minutes % 60 == 0 else f"{wait_minutes} min"
    typer.secho(
        f"Bicarbonate requis depuis cette mesure : {total_kg:.2f} kg", fg=typer.colors.GREEN
    )
    typer.echo(f"Lot a ajouter maintenant : {pending.bicarbonate_kg:.2f} kg maximum.")
    typer.secho(
        f"Filtration en marche : attendre au minimum {wait_text} avant de mesurer pH et TAC.",
        fg=typer.colors.YELLOW,
    )
    typer.echo("Ne pas ajouter le lot suivant avant cette mesure et le nouveau calcul.")


@app.command()
def start(
    mode: Annotated[
        ProtocolMode,
        typer.Option(help="Parcours : correction_hausse_ph_tac ou surveillance_ph_haut."),
    ] = ProtocolMode.RAISE_PH_TAC,
    volume_m3: float = typer.Option(SETTINGS.protocol.pool_volume_m3, min=0.01),
    initial_ph: float = typer.Option(SETTINGS.protocol.initial_ph, min=0.01, max=13.99),
    intermediate_ph: float = typer.Option(SETTINGS.protocol.intermediate_ph, min=0.01, max=13.99),
    target_ph: float = typer.Option(SETTINGS.protocol.target_ph, min=0.01, max=13.99),
    initial_tac: float = typer.Option(SETTINGS.protocol.initial_tac_ppm, min=0.01),
    bucket_l: float = typer.Option(SETTINGS.protocol.bucket_volume_l, min=0.01),
    electrolysis: Annotated[
        ElectrolysisStatus, typer.Option(help="Etat initial : inconnu, en_marche ou arretee.")
    ] = ElectrolysisStatus.UNKNOWN,
    disinfection: Annotated[
        DisinfectionMethod,
        typer.Option(
            "--disinfection",
            "--chlorine",
            help=(
                "Desinfection active : electrolyse_au_sel, galets_stabilises, "
                "dichlore_stabilise, chlore_non_stabilise ou inconnu. "
                "--chlorine reste un alias historique."
            ),
        ),
    ] = DisinfectionMethod.UNKNOWN,
    ph_regulator: Annotated[
        PhRegulatorStatus, typer.Option(help="Etat : inconnu, en_marche ou arrete.")
    ] = PhRegulatorStatus.UNKNOWN,
    tablets: Annotated[
        StabilizedTabletStatus,
        typer.Option(
            help="Etat des galets : inconnu, en_place, consommes, suspendus ou non_necessaires."
        ),
    ] = StabilizedTabletStatus.UNKNOWN,
    chlorine_min: float = typer.Option(
        1.0, min=0, help="Borne basse de chlore libre issue de l'etiquette, en ppm."
    ),
    chlorine_max: float = typer.Option(
        4.0, min=0.01, help="Borne haute de chlore libre issue de l'etiquette, en ppm."
    ),
    naoh_g_l: float | None = typer.Option(
        None, min=0.01, help="Concentration directe de NaOH en g/L (mode non guide)."
    ),
    guided: bool = typer.Option(
        True,
        "--guided/--no-guided",
        help="Poser le questionnaire avant la creation d'un nouveau protocole.",
    ),
    force: bool = typer.Option(
        False, help="Archive un nouveau protocole meme si un autre est actif."
    ),
) -> None:
    """Crée un protocole ou reprend l'archive active ; ``--force`` crée un nouveau."""
    try:
        protocol_service = service()
        existing = protocol_service.repository.active()
        initial_cya: float | None = None
        if guided and (existing is None or force):
            typer.secho("QUESTIONNAIRE DE DEMARRAGE", fg=typer.colors.GREEN, bold=True)
            typer.echo("Les valeurs entrees seront archivees avec ce protocole.")
            mode_choice = prompted_choice(
                "Quel parcours utiliser ?",
                ["Correction pH/TAC vers le haut", "Surveillance d'un pH au-dessus de la cible"],
            )
            mode = (
                ProtocolMode.RAISE_PH_TAC if mode_choice == 1 else ProtocolMode.HIGH_PH_MONITORING
            )
            volume_m3 = typer.prompt("Volume du bassin en m3", default=volume_m3, type=float)
            initial_ph = typer.prompt("pH mesure au depart", default=initial_ph, type=float)
            initial_tac = typer.prompt("TAC mesure en ppm CaCO3", default=initial_tac, type=float)
            target_ph = typer.prompt("pH cible", default=target_ph, type=float)
            chlorine_min = typer.prompt(
                "Borne basse chlore libre selon l'etiquette, en ppm",
                default=chlorine_min,
                type=float,
            )
            chlorine_max = typer.prompt(
                "Borne haute chlore libre selon l'etiquette, en ppm",
                default=chlorine_max,
                type=float,
            )
            if mode is ProtocolMode.RAISE_PH_TAC:
                intermediate_ph = typer.prompt(
                    "Palier pH avant correction TAC", default=intermediate_ph, type=float
                )
                concentration, source, percent, density = prompt_naoh_concentration()
            else:
                concentration = SETTINGS.protocol.naoh_concentration_g_l
                source = NaOHConcentrationSource.DEFAULT
                percent = None
                density = None
            treatment, initial_cya = prompt_treatment_context()
        else:
            concentration = naoh_g_l or SETTINGS.protocol.naoh_concentration_g_l
            source = (
                NaOHConcentrationSource.GRAMS_PER_LITRE
                if naoh_g_l is not None
                else NaOHConcentrationSource.DEFAULT
            )
            percent = None
            density = None
            treatment = TreatmentContext(
                electrolysis_status=electrolysis,
                disinfection_method=disinfection,
                ph_regulator_status=ph_regulator,
                stabilized_tablet_status=tablets,
            )
        config = ProtocolConfig(
            mode=mode,
            pool_volume_m3=volume_m3,
            initial_ph=initial_ph,
            intermediate_ph=intermediate_ph,
            target_ph=target_ph,
            initial_tac_ppm=initial_tac,
            bucket_volume_l=bucket_l,
            naoh_concentration_g_l=concentration,
            naoh_concentration_source=source,
            naoh_label_percent=percent,
            naoh_density_g_ml=density,
            free_chlorine_min_ppm=chlorine_min,
            free_chlorine_max_ppm=chlorine_max,
        )
        state = protocol_service.start(
            config,
            treatment=treatment,
            replace_active=force,
        )
        if initial_cya is not None and (existing is None or force):
            state = protocol_service.record_cyanuric_acid_measurement(initial_cya)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    if existing and not force:
        typer.secho(f"Protocole actif repris : {state.archive_name}", fg=typer.colors.GREEN)
        typer.echo(f"Etape actuelle : {state.step}")
    else:
        typer.secho(f"Protocole cree : {state.archive_name}", fg=typer.colors.GREEN)
    if state.config.mode is ProtocolMode.RAISE_PH_TAC:
        show_naoh_declaration(state)
    if state.initial_coherence and state.initial_coherence.warnings:
        for warning in state.initial_coherence.warnings:
            typer.secho(f"Alerte initiale : {warning}", fg=typer.colors.YELLOW)
    show_supply_estimate(state)
    show_water_actions(state)
    show_next_command(state)


@app.command()
def status() -> None:
    """Affiche mesures, préparations en attente, cumul et action suivante."""
    try:
        state = service().active()
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.echo(f"Archive : {state.archive_name}")
    typer.echo(f"Etape : {state.step}")
    typer.echo(
        f"Dernieres mesures : pH {state.current_ph:.2f}, TAC {state.current_tac_ppm:.1f} ppm"
    )
    if state.pending_naoh:
        typer.echo(f"Dose NaOH en attente : {state.pending_naoh.naoh_ml:.0f} mL")
    if state.pending_bicarbonate:
        typer.echo(
            f"Lot bicarbonate en attente : {state.pending_bicarbonate.bicarbonate_kg:.2f} kg"
        )
    show_cumulative_additions(state)
    if state.config.mode is ProtocolMode.RAISE_PH_TAC:
        show_naoh_declaration(state)
    show_treatment(state)
    show_supply_estimate(state)
    show_water_actions(state)
    show_next_command(state)


@app.command("configure-naoh")
def configure_naoh() -> None:
    """Corrige la déclaration de soude d'un protocole déjà en cours.

    Les volumes et mesures déjà confirmés sont conservés. La concentration
    déclarée s'applique au même produit utilisé depuis le début et recalcule
    son cumul théorique ; elle ne doit donc pas être employée après un changement
    de bidon de concentration différente.
    """
    try:
        typer.secho("DECLARATION DE LA SOUDE DU PROTOCOLE EN COURS", fg=typer.colors.GREEN)
        typer.echo(
            "Utilisez cette commande seulement si cette même lessive de soude a ete "
            "employee pour tous les apports deja confirmes."
        )
        concentration, source, percent, density = prompt_naoh_concentration()
        state = service().set_naoh_concentration(concentration, source, percent, density)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    typer.secho(
        "Declaration de soude mise a jour ; les volumes et mesures sont conserves.",
        fg=typer.colors.GREEN,
    )
    show_naoh_declaration(state)
    show_cumulative_additions(state)
    show_next_command(state)


@app.command("treatment")
def treatment(
    electrolysis: Annotated[
        ElectrolysisStatus, typer.Option(help="Etat : inconnu, en_marche ou arretee.")
    ],
    disinfection: Annotated[
        DisinfectionMethod,
        typer.Option(
            "--disinfection",
            "--chlorine",
            help=(
                "Desinfection active : electrolyse_au_sel, galets_stabilises, "
                "dichlore_stabilise, chlore_non_stabilise ou inconnu. "
                "--chlorine reste un alias historique."
            ),
        ),
    ],
    ph_regulator: Annotated[
        PhRegulatorStatus | None,
        typer.Option(help="Etat : inconnu, en_marche ou arrete (omettre pour conserver)."),
    ] = None,
    tablets: Annotated[
        StabilizedTabletStatus | None,
        typer.Option(
            help="Etat des galets : inconnu, en_place, consommes, suspendus ou non_necessaires (omettre pour conserver)."
        ),
    ] = None,
) -> None:
    """Déclare le traitement en cours afin de contextualiser les alertes pH/TAC."""
    try:
        state = service().set_treatment(electrolysis, disinfection, ph_regulator, tablets)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho("Contexte de traitement enregistre.", fg=typer.colors.GREEN)
    show_treatment(state)
    show_supply_estimate(state)
    show_water_actions(state)


@app.command("record-tablets")
def record_tablets(
    count: int = typer.Option(..., min=1, help="Nombre de galets stabilises ajoutes."),
    unit_mass_g: float | None = typer.Option(
        None, min=0.01, help="Masse nominale d'un galet, si connue."
    ),
    product: str = typer.Option("galet stabilise", help="Libelle lu sur l'emballage."),
) -> None:
    """Journalise les galets stabilisés ajoutés, sans estimer leur CYA."""
    try:
        state = service().record_stabilized_tablets(count, unit_mass_g, product)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho("Ajout de galets enregistre.", fg=typer.colors.GREEN)
    show_treatment(state)


@app.command("measure-cya")
def measure_cya(
    cya: float = typer.Option(..., min=0, help="Acide cyanurique mesure, en ppm (mg/L)."),
) -> None:
    """Journalise une mesure de stabilisant (CYA) réellement effectuée."""
    try:
        state = service().record_cyanuric_acid_measurement(cya)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho("Mesure de CYA enregistree.", fg=typer.colors.GREEN)
    show_treatment(state)


@app.command("record-water")
def record_water(
    ph: Annotated[float, typer.Option(min=0.01, max=13.99)],
    tac: Annotated[float, typer.Option(min=0.01)],
    free_chlorine: Annotated[float, typer.Option("--free-chlorine", min=0)],
) -> None:
    """Archive une mesure pH/TAC/chlore sans préparer ni compter un produit."""
    try:
        state = service().record_water_measurement(ph, tac, free_chlorine)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho(
        "Mesure de surveillance enregistree. Aucun dosage n'est calcule.", fg=typer.colors.GREEN
    )
    show_treatment(state)
    show_water_actions(state)
    show_next_command(state)


@app.command("dose")
def dose(naoh_ml: Annotated[float | None, typer.Option(min=0.01)] = None) -> None:
    """Prépare la prochaine dose de NaOH sans la compter comme versée."""
    try:
        state, prep = service().prepare_naoh(naoh_ml)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    show_bucket_preparation(prep.naoh_ml, prep.water_l, prep.useful_volume_l)
    typer.echo(f"Archive mise a jour : {state.archive_name}")
    show_next_command(state)


@app.command("cancel-dose")
def cancel_dose() -> None:
    """Annule une dose de NaOH préparée et non versée après confirmation explicite."""
    try:
        state = service().active()
        pending = state.pending_naoh
        if pending is None:
            raise ValueError("Aucune dose de NaOH en attente a annuler.")
        if not typer.confirm(
            f"Confirmer que les {pending.naoh_ml:.0f} mL n'ont PAS ete verses dans le bassin ?"
        ):
            typer.echo("Annulation abandonnee.")
            return
        state = service().cancel_pending_naoh()
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho(
        "Dose de NaOH annulee. Les mesures precedentes sont conservees.", fg=typer.colors.GREEN
    )
    show_next_command(state)


@app.command("cancel-tac-plan")
def cancel_tac_plan() -> None:
    """Annule un lot de bicarbonate préparé et non versé après confirmation."""
    try:
        state = service().active()
        pending = state.pending_bicarbonate
        if pending is None:
            raise ValueError("Aucun lot de bicarbonate en attente a annuler.")
        if not typer.confirm(
            f"Confirmer que les {pending.bicarbonate_kg:.2f} kg n'ont PAS ete verses dans le bassin ?"
        ):
            typer.echo("Annulation abandonnee.")
            return
        state = service().cancel_pending_bicarbonate()
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho("Lot de bicarbonate annule.", fg=typer.colors.GREEN)
    show_next_command(state)


@app.command("cancel-protocol")
def cancel_protocol() -> None:
    """Archive le protocole actif comme annulé, sans supprimer les données."""
    try:
        state = service().active()
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    if not typer.confirm(
        f"Annuler le protocole {state.archive_name} ? Son historique sera conserve."
    ):
        typer.echo("Annulation abandonnee.")
        return
    service().cancel_protocol()
    typer.secho(
        "Protocole annule et archive. Vous pouvez en creer un nouveau.", fg=typer.colors.GREEN
    )
    typer.echo("Commande suivante : piscine-ph start")


@app.command("correct-last-measurement")
def correct_last_measurement(
    ph: Annotated[float, typer.Option(min=0.01, max=13.99)],
    tac: Annotated[float, typer.Option(min=0.01)],
) -> None:
    """Corrige pH/TAC de la dernière mesure sans retirer le produit versé."""
    try:
        state = service().correct_last_measurement(ph, tac)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho("Derniere mesure corrigee.", fg=typer.colors.GREEN)
    show_check(state)
    show_cumulative_additions(state)
    show_next_command(state)


@app.command("measure")
def measure(
    ph: Annotated[float, typer.Option(min=0.01, max=13.99)],
    tac: Annotated[float, typer.Option(min=0.01)],
) -> None:
    """Enregistre les mesures faites après la dernière dose de NaOH en attente."""
    try:
        state = service().record_naoh_measurement(ph, tac)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho(f"Mesures enregistrees. Etape active : {state.step}", fg=typer.colors.GREEN)
    show_check(state)
    show_cumulative_additions(state)
    show_next_command(state)


@app.command("plan-tac")
def plan_tac(tac: Annotated[float, typer.Option(min=0.01)]) -> None:
    """Prépare un seul lot de bicarbonate depuis le TAC réellement mesuré."""
    try:
        state = service().plan_bicarbonate(tac)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    pending = state.pending_bicarbonate
    assert pending is not None
    show_bicarbonate_plan(pending)
    show_next_command(state)


@app.command("measure-tac")
def measure_tac(
    ph: Annotated[float, typer.Option(min=0.01, max=13.99)],
    tac: Annotated[float, typer.Option(min=0.01)],
) -> None:
    """Enregistre pH/TAC après bicarbonate et vérifie l'atteinte du TAC cible."""
    try:
        state = service().record_bicarbonate_measurement(ph, tac)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    typer.secho(f"Mesures enregistrees. Etape active : {state.step}", fg=typer.colors.GREEN)
    show_check(state)
    show_cumulative_additions(state)
    if state.step.value == "tac_vers_80":
        typer.secho(
            "TAC sous 80 ppm : refaire plan-tac avec la nouvelle mesure pour preparer un seul lot.",
            fg=typer.colors.YELLOW,
        )
    show_next_command(state)


@app.command()
def menu() -> None:
    """Guide interactif qui propose une seule action logique puis rend la main.

    Il s'arrête volontairement lorsqu'une opération physique, une circulation ou
    une mesure du bassin est nécessaire : le programme ne simule pas ces étapes.
    """
    protocol_service = service()
    try:
        state = protocol_service.active()
    except ValueError as error:
        typer.echo(f"{error} Lancez : piscine-ph start")
        raise typer.Exit(1)

    typer.secho("GUIDE DU PROTOCOLE", fg=typer.colors.GREEN, bold=True)
    typer.echo(
        f"Etape : {state.step} | pH {state.current_ph:.2f} | TAC {state.current_tac_ppm:.1f} ppm"
    )
    show_treatment(state)
    if state.step is ProtocolStep.COMPLETE:
        typer.echo("Le protocole est termine.")
        show_next_command(state)
        return

    if state.step is ProtocolStep.HIGH_PH_MONITORING:
        typer.echo("SURVEILLANCE PH HAUT — aucune dose d'acide ou de chlore n'est calculee.")
        show_water_actions(state)
        ph = typer.prompt("pH mesure dans le bassin", type=float)
        tac = typer.prompt("TAC mesure en ppm CaCO3 (pas de 10 ppm)", type=float)
        chlorine = typer.prompt("Chlore libre mesure en ppm", type=float)
        try:
            state = protocol_service.record_water_measurement(ph, tac, chlorine)
        except ValueError as error:
            typer.echo(str(error))
            raise typer.Exit(1)
        typer.secho("Mesure de surveillance enregistree.", fg=typer.colors.GREEN)
        show_water_actions(state)
        show_next_command(state)
        return

    if state.pending_naoh:
        typer.echo("La dose de NaOH affichee precedemment doit etre ajoutee puis mesuree.")
        show_next_command(state)
        if not typer.confirm("Avez-vous deja mesure le pH et le TAC apres cette dose ?"):
            return
        ph = typer.prompt("pH mesure dans le bassin", type=float)
        tac = typer.prompt("TAC mesure en ppm CaCO3 (pas de 10 ppm)", type=float)
        state = protocol_service.record_naoh_measurement(ph, tac)
        typer.secho("Mesures enregistrees.", fg=typer.colors.GREEN)
        show_check(state)
        show_next_command(state)
        return

    if state.pending_bicarbonate:
        typer.echo(
            "Ajouter uniquement le lot de bicarbonate affiche, puis attendre avant de mesurer."
        )
        show_bicarbonate_plan(state.pending_bicarbonate)
        show_next_command(state)
        if not typer.confirm("Avez-vous deja mesure le pH et le TAC apres bicarbonate ?"):
            return
        ph = typer.prompt("pH mesure dans le bassin", type=float)
        tac = typer.prompt("TAC mesure en ppm CaCO3 (pas de 10 ppm)", type=float)
        state = protocol_service.record_bicarbonate_measurement(ph, tac)
        typer.secho("Mesures enregistrees.", fg=typer.colors.GREEN)
        show_check(state)
        show_next_command(state)
        return

    if state.step is ProtocolStep.TAC_TO_TARGET:
        typer.echo("Mesurez le TAC avant de preparer le bicarbonate.")
        tac = typer.prompt("TAC mesure en ppm CaCO3 (pas de 10 ppm)", type=float)
        state = protocol_service.plan_bicarbonate(tac)
        pending = state.pending_bicarbonate
        assert pending is not None
        show_bicarbonate_plan(pending)
        show_next_command(state)
        return

    target = (
        state.config.intermediate_ph
        if state.step is ProtocolStep.PH_TO_INTERMEDIATE
        else state.config.target_ph
    )
    suggested = ChemistryCalculator().suggested_naoh_ml(state.current_ph, target)
    typer.echo(
        f"Dose indicative : {suggested:.0f} mL ; adaptez-la a la reponse precedentement observee."
    )
    naoh_ml = typer.prompt(
        "Volume de NaOH choisi pour le seau, en mL", default=suggested, type=float
    )
    state, preparation = protocol_service.prepare_naoh(naoh_ml)
    show_bucket_preparation(preparation.naoh_ml, preparation.water_l, preparation.useful_volume_l)
    show_next_command(state)


@app.command()
def tui() -> None:
    """Lance l'interface à menus Textual, en complément des commandes scriptables."""
    from .tui import PiscinePhTui

    PiscinePhTui().run()


@app.command()
def history() -> None:
    """Liste les archives lisibles, y compris les protocoles terminés ou annulés."""
    states = service().repository.archives()
    if not states:
        typer.echo("Aucune archive.")
        return
    for state in states:
        typer.echo(
            f"{state.archive_name} | {state.step} | pH {state.current_ph:.2f} | TAC {state.current_tac_ppm:.1f}"
        )


@app.command("json")
def show_json(
    archive: Annotated[
        str | None,
        typer.Argument(help="Nom d'une archive listée par `piscine-ph history` (actif par défaut)."),
    ] = None,
) -> None:
    """Affiche, sans le modifier, le JSON du protocole actif ou d'une archive."""
    protocol_service = service()
    repository = protocol_service.repository
    if archive is None:
        try:
            state = protocol_service.active()
        except ValueError as error:
            typer.echo(str(error))
            raise typer.Exit(1)
    else:
        state = next((state for state in repository.archives() if state.archive_name == archive), None)
        if state is None:
            typer.echo("Archive introuvable. Utilisez `piscine-ph history` pour lister les archives.")
            raise typer.Exit(1)
    try:
        typer.echo((repository.root / state.archive_name).read_text(encoding="utf-8"), nl=False)
    except OSError as error:
        typer.echo(f"Lecture du JSON impossible : {error}")
        raise typer.Exit(1)
