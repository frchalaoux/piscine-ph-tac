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
from .models import ProtocolConfig, ProtocolState, ProtocolStep
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
    if state.step in {ProtocolStep.COMPLETE, ProtocolStep.CANCELLED}:
        return "uv run piscine-ph history"
    if state.pending_naoh:
        return "uv run piscine-ph measure --ph VOTRE_PH --tac VOTRE_TAC"
    if state.pending_bicarbonate:
        return "uv run piscine-ph measure-tac --ph VOTRE_PH --tac VOTRE_TAC"
    if state.step is ProtocolStep.TAC_TO_TARGET:
        return "uv run piscine-ph plan-tac --tac VOTRE_TAC"
    return "uv run piscine-ph dose"


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


def show_bucket_preparation(naoh_ml: float, water_l: float, useful_volume_l: float) -> None:
    """Présente les volumes à préparer dans le seau pour une dose de NaOH."""
    typer.secho("Prochaine dose preparee", fg=typer.colors.GREEN)
    typer.echo(f"Mettre {water_l:.2f} L d'eau dans le seau, puis {naoh_ml:.0f} mL de NaOH.")
    typer.echo(f"Volume utile : {useful_volume_l:.2f} L. Mesurer ensuite pH et TAC du bassin.")


@app.command()
def start(
    volume_m3: float = typer.Option(SETTINGS.protocol.pool_volume_m3, min=0.01),
    initial_ph: float = typer.Option(SETTINGS.protocol.initial_ph, min=0.01, max=13.99),
    intermediate_ph: float = typer.Option(SETTINGS.protocol.intermediate_ph, min=0.01, max=13.99),
    target_ph: float = typer.Option(SETTINGS.protocol.target_ph, min=0.01, max=13.99),
    initial_tac: float = typer.Option(SETTINGS.protocol.initial_tac_ppm, min=0.01),
    bucket_l: float = typer.Option(SETTINGS.protocol.bucket_volume_l, min=0.01),
    force: bool = typer.Option(
        False, help="Archive un nouveau protocole meme si un autre est actif."
    ),
) -> None:
    """Crée un protocole ou reprend l'archive active ; ``--force`` crée un nouveau."""
    try:
        protocol_service = service()
        existing = protocol_service.repository.active()
        config = ProtocolConfig(
            pool_volume_m3=volume_m3,
            initial_ph=initial_ph,
            intermediate_ph=intermediate_ph,
            target_ph=target_ph,
            initial_tac_ppm=initial_tac,
            bucket_volume_l=bucket_l,
        )
        state = protocol_service.start(config, replace_active=force)
    except ValueError as error:
        raise typer.BadParameter(str(error)) from error
    if existing and not force:
        typer.secho(f"Protocole actif repris : {state.archive_name}", fg=typer.colors.GREEN)
        typer.echo(f"Etape actuelle : {state.step}")
    else:
        typer.secho(f"Protocole cree : {state.archive_name}", fg=typer.colors.GREEN)
    if state.initial_coherence and state.initial_coherence.warnings:
        for warning in state.initial_coherence.warnings:
            typer.secho(f"Alerte initiale : {warning}", fg=typer.colors.YELLOW)
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
        typer.echo(f"Bicarbonate en attente : {state.pending_bicarbonate.bicarbonate_kg:.2f} kg")
    show_cumulative_additions(state)
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
    typer.echo("Commande suivante : uv run piscine-ph start")


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
    """Calcule et découpe l'apport de bicarbonate depuis le TAC réellement mesuré."""
    try:
        state = service().plan_bicarbonate(tac)
    except ValueError as error:
        typer.echo(str(error))
        raise typer.Exit(1)
    pending = state.pending_bicarbonate
    assert pending is not None
    batches = ChemistryCalculator().bicarbonate_batches_kg(pending.bicarbonate_kg)
    typer.secho(f"Bicarbonate total : {pending.bicarbonate_kg:.2f} kg", fg=typer.colors.GREEN)
    typer.echo(
        "Apports en poudre devant les buses : " + ", ".join(f"{value:.2f} kg" for value in batches)
    )
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
            "TAC sous 80 ppm : refaire plan-tac avec la nouvelle mesure.", fg=typer.colors.YELLOW
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
        typer.echo(f"{error} Lancez : uv run piscine-ph start")
        raise typer.Exit(1)

    typer.secho("GUIDE DU PROTOCOLE", fg=typer.colors.GREEN, bold=True)
    typer.echo(
        f"Etape : {state.step} | pH {state.current_ph:.2f} | TAC {state.current_tac_ppm:.1f} ppm"
    )
    if state.step is ProtocolStep.COMPLETE:
        typer.echo("Le protocole est termine.")
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
        typer.echo("Le bicarbonate affiche precedemment doit etre ajoute puis mesure.")
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
        batches = ChemistryCalculator().bicarbonate_batches_kg(pending.bicarbonate_kg)
        typer.secho(f"Bicarbonate total : {pending.bicarbonate_kg:.2f} kg", fg=typer.colors.GREEN)
        typer.echo("Apports : " + ", ".join(f"{value:.2f} kg" for value in batches))
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
