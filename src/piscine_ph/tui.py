"""Interface Textual de ``piscine-ph``.

La TUI est une couche de présentation : elle appelle directement
``ProtocolService`` afin de partager les validations, les garde-fous et les
archives JSON avec les commandes Typer. Elle ne déduit jamais une action à
partir du texte affiché par la CLI.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)

from .models import (
    ChlorineTreatment,
    ElectrolysisStatus,
    PhRegulatorStatus,
    ProtocolStep,
    StabilizedTabletStatus,
)
from .repository import JsonProtocolRepository
from .service import ProtocolService


def _choices(enum_type: type[ElectrolysisStatus]) -> list[tuple[str, str]]:
    """Transforme une énumération de contexte en options Textual lisibles."""
    return [(item.value.replace("_", " "), item.value) for item in enum_type]


class PiscinePhTui(App[None]):
    """TUI à menus pour consulter et journaliser un protocole existant."""

    TITLE = "piscine-ph"
    SUB_TITLE = "Suivi prudent pH / TAC / chlore"
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("r", "refresh", "Actualiser"),
        ("q", "quit", "Quitter"),
    ]
    CSS = """
    TabbedContent { height: 1fr; }
    TabPane { padding: 1 2; }
    #dashboard, #help { height: 1fr; }
    #measure-form, #treatment-form { width: 70; max-width: 100%; }
    Input, Select { margin: 1 0; }
    Button { margin: 1 0; }
    #history-table { height: 1fr; }
    .warning { color: $warning; }
    .success { color: $success; }
    """

    def __init__(self, root: Path = Path("data/protocoles")) -> None:
        super().__init__()
        self.protocol_service = ProtocolService(JsonProtocolRepository(root))

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="dashboard"):
            with TabPane("Tableau de bord", id="dashboard"), VerticalScroll(id="dashboard"):
                yield Static("Chargement…", id="dashboard-status")
                yield Button("Actualiser", id="refresh-dashboard", variant="primary")
            with TabPane("Mesures", id="measurements"):
                yield Static("Chargement…", id="measurement-instructions")
                with Container(id="measure-form"):
                    yield Input(placeholder="pH mesuré (ex. 7.30)", id="measurement-ph")
                    yield Input(placeholder="TAC mesuré en ppm (ex. 80)", id="measurement-tac")
                    yield Input(
                        placeholder="Chlore libre en ppm (surveillance pH haut)",
                        id="measurement-chlorine",
                    )
                    yield Button("Enregistrer la mesure", id="save-measurement", variant="success")
            with TabPane("Traitement", id="treatment"):
                yield Static(
                    "Documenter les appareils ne les pilote pas. Les changements physiques "
                    "doivent respecter leur notice.",
                    classes="warning",
                )
                with Container(id="treatment-form"):
                    yield Select(_choices(ElectrolysisStatus), prompt="Électrolyse", id="electrolysis")
                    yield Select(_choices(ChlorineTreatment), prompt="Désinfectant", id="chlorine")
                    yield Select(_choices(PhRegulatorStatus), prompt="Régulateur pH", id="ph-regulator")
                    yield Select(_choices(StabilizedTabletStatus), prompt="État des galets", id="tablets")
                    yield Button("Enregistrer le contexte", id="save-treatment", variant="primary")
            with TabPane("Historique", id="history"):
                yield Static("Archives JSON connues :")
                yield DataTable(id="history-table")
                yield Button("Actualiser l'historique", id="refresh-history")
            with TabPane("Aide et sécurité", id="help"):
                yield Static(
                    "Cette interface ne calcule aucune dose d'acide ou de chlore.\n\n"
                    "• Utilisez Mesures pour enregistrer les valeurs réellement lues.\n"
                    "• Utilisez Traitement pour déclarer l'état des appareils et galets.\n"
                    "• Les commandes CLI restent disponibles pour créer ou doser les protocoles "
                    "historiques de hausse pH/TAC.\n\n"
                    "Raccourcis : r actualiser, q quitter.",
                    id="help",
                )
        yield Footer()

    def on_mount(self) -> None:
        """Initialise les vues après le montage des widgets."""
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Archive", "Étape", "pH", "TAC")
        self.refresh_views()

    def action_refresh(self) -> None:
        """Raccourci clavier pour relire les données persistées."""
        self.refresh_views()
        self.notify("Affichage actualisé.")

    def refresh_views(self) -> None:
        """Actualise le tableau de bord, le formulaire et l'historique."""
        self._refresh_dashboard_and_forms()
        self._refresh_history()

    def _refresh_dashboard_and_forms(self) -> None:
        dashboard = self.query_one("#dashboard-status", Static)
        instructions = self.query_one("#measurement-instructions", Static)
        chlorine_input = self.query_one("#measurement-chlorine", Input)
        try:
            state = self.protocol_service.active()
        except ValueError:
            dashboard.update(
                "Aucun protocole actif. Créez-en un avec la CLI :\n"
                "piscine-ph start …\n\n"
                "L'onglet Historique reste disponible."
            )
            instructions.update("Aucun protocole actif : aucune mesure ne peut être enregistrée.")
            chlorine_input.display = False
            return

        treatment = state.treatment
        lines = [
            f"Archive : {state.archive_name}",
            f"Étape : {state.step.value}",
            f"Dernières mesures : pH {state.current_ph:.2f} · TAC {state.current_tac_ppm:.0f} ppm",
            (
                "Traitement : "
                f"électrolyse {treatment.electrolysis_status.value}, "
                f"régulateur pH {treatment.ph_regulator_status.value}, "
                f"chlore {treatment.chlorine_treatment.value}, "
                f"galets {treatment.stabilized_tablet_status.value}."
            ),
        ]
        actions = self.protocol_service.water_actions(state)
        if actions:
            lines.extend(["", "Surveillance :", *[f"• {action}" for action in actions]])
        dashboard.update("\n".join(lines))

        self._set_treatment_values(state)
        if state.step is ProtocolStep.HIGH_PH_MONITORING:
            instructions.update(
                "Surveillance pH haut : saisissez pH, TAC et chlore libre. "
                "Aucun produit ne sera calculé ni ajouté."
            )
            chlorine_input.display = True
        elif state.pending_naoh:
            instructions.update("Mesure après NaOH : saisissez pH et TAC. Le champ chlore libre est inutile.")
            chlorine_input.display = False
        elif state.pending_bicarbonate:
            instructions.update(
                "Mesure après bicarbonate : saisissez pH et TAC. Le champ chlore libre est inutile."
            )
            chlorine_input.display = False
        else:
            instructions.update(
                "Aucune mesure n'est actuellement attendue. Utilisez la CLI pour préparer l'action "
                "suivante, puis revenez confirmer la mesure ici."
            )
            chlorine_input.display = False

    def _set_treatment_values(self, state) -> None:
        """Affiche les valeurs persistées dans les sélecteurs de contexte."""
        self.query_one("#electrolysis", Select).value = state.treatment.electrolysis_status.value
        self.query_one("#chlorine", Select).value = state.treatment.chlorine_treatment.value
        self.query_one("#ph-regulator", Select).value = state.treatment.ph_regulator_status.value
        self.query_one("#tablets", Select).value = state.treatment.stabilized_tablet_status.value

    def _refresh_history(self) -> None:
        """Relit les archives sans modifier leur contenu."""
        table = self.query_one("#history-table", DataTable)
        table.clear()
        for state in self.protocol_service.repository.archives():
            table.add_row(
                state.archive_name,
                state.step.value,
                f"{state.current_ph:.2f}",
                f"{state.current_tac_ppm:.0f} ppm",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route les boutons vers les opérations de présentation correspondantes."""
        match event.button.id:
            case "refresh-dashboard" | "refresh-history":
                self.refresh_views()
            case "save-measurement":
                self._save_measurement()
            case "save-treatment":
                self._save_treatment()

    def _save_measurement(self) -> None:
        """Valide les champs et délègue la mutation au service métier."""
        try:
            ph = float(self.query_one("#measurement-ph", Input).value)
            tac = float(self.query_one("#measurement-tac", Input).value)
            state = self.protocol_service.active()
            if state.step is ProtocolStep.HIGH_PH_MONITORING:
                chlorine = float(self.query_one("#measurement-chlorine", Input).value)
                self.protocol_service.record_water_measurement(ph, tac, chlorine)
            elif state.pending_naoh:
                self.protocol_service.record_naoh_measurement(ph, tac)
            elif state.pending_bicarbonate:
                self.protocol_service.record_bicarbonate_measurement(ph, tac)
            else:
                raise ValueError("Aucune mesure de confirmation n'est attendue à cette étape.")
        except ValueError as error:
            self.notify(str(error), severity="error")
            return
        self.notify("Mesure enregistrée.", severity="information")
        self._clear_measurement_fields()
        self.refresh_views()

    def _save_treatment(self) -> None:
        """Enregistre seulement le contexte explicitement choisi dans les menus."""
        try:
            electrolysis = ElectrolysisStatus(str(self.query_one("#electrolysis", Select).value))
            chlorine = ChlorineTreatment(str(self.query_one("#chlorine", Select).value))
            regulator = PhRegulatorStatus(str(self.query_one("#ph-regulator", Select).value))
            tablets = StabilizedTabletStatus(str(self.query_one("#tablets", Select).value))
            self.protocol_service.set_treatment(electrolysis, chlorine, regulator, tablets)
        except ValueError as error:
            self.notify(str(error), severity="error")
            return
        self.notify("Contexte de traitement enregistré.")
        self.refresh_views()

    def _clear_measurement_fields(self) -> None:
        for widget_id in ("#measurement-ph", "#measurement-tac", "#measurement-chlorine"):
            self.query_one(widget_id, Input).value = ""
