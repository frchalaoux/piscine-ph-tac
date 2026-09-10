"""Interface Textual de ``piscine-ph``.

La TUI est une couche de présentation : elle appelle directement
``ProtocolService`` afin de partager les validations, les garde-fous et les
archives JSON avec les commandes Typer. Elle ne déduit jamais une action à
partir du texte affiché par la CLI.
"""

from __future__ import annotations

from pathlib import Path
from sys import platform
from typing import ClassVar

from pydantic import ValidationError
from textual import events, on
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import (
    Button,
    Checkbox,
    Collapsible,
    DataTable,
    Footer,
    Header,
    Input,
    Select,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets._collapsible import CollapsibleTitle

from .models import (
    DisinfectionMethod,
    ElectrolysisStatus,
    NaOHConcentrationSource,
    PhRegulatorStatus,
    ProtocolConfig,
    ProtocolMode,
    ProtocolStep,
    StabilizedTabletStatus,
    TreatmentContext,
)
from .repository import JsonProtocolRepository
from .service import ProtocolService
from .settings import SETTINGS


def _choices(enum_type: type[ElectrolysisStatus]) -> list[tuple[str, str]]:
    """Transforme une énumération de contexte en options Textual lisibles."""
    return [(item.value.replace("_", " "), item.value) for item in enum_type]


def _field(
    label: str, widget: Input | Select, *, classes: str | None = None
) -> ComposeResult:
    """Associe un libellé permanent à un champ, même s'il est prérempli."""
    field_classes = "field" if classes is None else f"field {classes}"
    with Container(classes=field_classes):
        yield Static(label, classes="field-label")
        yield widget


class CopyableCollapsibleTitle(CollapsibleTitle):
    """En-tête de section repliable que l'on peut sélectionner et copier."""

    ALLOW_SELECT = True

    @on(events.Click)
    def prevent_toggle_after_selection(self, event: events.Click) -> None:
        """Conserve le clic d'ouverture, sauf après une sélection au glisser."""
        if event.widget is self and self.text_selection is not None:
            event.stop()
            event.prevent_default()


class CopyableCollapsible(Collapsible):
    """Collapsible dont le titre reste une commande tout en étant copiable."""

    def __init__(
        self,
        *children: Widget,
        title: str = "Toggle",
        collapsed: bool = True,
        collapsed_symbol: str = "▶",
        expanded_symbol: str = "▼",
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ) -> None:
        super().__init__(
            *children,
            title=title,
            collapsed=collapsed,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self._title = CopyableCollapsibleTitle(
            label=title,
            collapsed_symbol=collapsed_symbol,
            expanded_symbol=expanded_symbol,
            collapsed=collapsed,
        )


class CancelProtocolScreen(ModalScreen[bool]):
    """Demande une confirmation avant d'archiver un protocole comme annulé."""

    CSS = """
    CancelProtocolScreen { align: center middle; }
    #cancel-dialog { width: 64; max-width: 90%; height: auto; padding: 1 2; border: thick $error; }
    #cancel-dialog Button { margin: 1 1 0 0; }
    """

    def compose(self) -> ComposeResult:
        with Container(id="cancel-dialog"):
            yield Static("Arrêter ce protocole ?", classes="section-title")
            yield Static(
                "Les mesures et doses déjà journalisées seront conservées dans l'archive. "
                "Les préparations non confirmées seront retirées.",
            )
            yield Button("Conserver le protocole", id="keep-protocol")
            yield Button("Arrêter le protocole", id="confirm-cancel-protocol", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-cancel-protocol")


class CancelPendingScreen(ModalScreen[bool]):
    """Demande confirmation qu'une préparation n'a pas été versée."""

    CSS = """
    CancelPendingScreen { align: center middle; }
    #pending-cancel-dialog { width: 64; max-width: 90%; height: auto; padding: 1 2; border: thick $warning; }
    #pending-cancel-dialog Button { margin: 1 1 0 0; }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message

    def compose(self) -> ComposeResult:
        with Container(id="pending-cancel-dialog"):
            yield Static("Annuler une préparation ?", classes="section-title")
            yield Static(self.message)
            yield Button("Conserver la préparation", id="keep-pending")
            yield Button("Oui, rien n’a été versé", id="confirm-pending-cancel", variant="warning")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-pending-cancel")


class JsonViewerScreen(ModalScreen[None]):
    """Affiche un résumé lisible puis une archive brute non modifiable."""

    CSS = """
    JsonViewerScreen { align: center middle; }
    #json-dialog { width: 96%; max-width: 120; height: 90%; padding: 1 2; border: thick $primary; }
    #json-content-scroll { height: 1fr; margin: 1 0; }
    #json-content { width: auto; }
    #json-dialog Button { margin: 1 0 0 0; }
    """

    def __init__(self, path: Path, summary: str, content: str) -> None:
        super().__init__()
        self.path = path
        self.summary = summary
        self.content = content

    def compose(self) -> ComposeResult:
        with Container(id="json-dialog"):
            yield Static("Résumé du protocole", classes="section-title")
            yield Static(str(self.path.resolve()), classes="section-detail")
            yield Static(self.summary, id="json-summary")
            yield Static("JSON brut — lecture seule", classes="section-title")
            yield Static(
                f"Sélectionnez le texte puis utilisez {self.app.COPY_KEY_LABEL} pour le copier."
            )
            with VerticalScroll(id="json-content-scroll"):
                yield Static(self.content, id="json-content")
            yield Button("Fermer", id="close-json")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close-json":
            self.dismiss()


class PiscinePhTui(App[None]):
    """TUI à menus pour consulter et journaliser un protocole existant."""

    TITLE = "piscine-ph"
    SUB_TITLE = "Suivi prudent pH / TAC / chlore"
    REFRESH_KEY: ClassVar[str] = "super+r" if platform == "darwin" else "ctrl+r"
    REFRESH_KEY_LABEL: ClassVar[str] = "⌘R" if platform == "darwin" else "Ctrl+R"
    COPY_KEY_LABEL: ClassVar[str] = "⌘C" if platform == "darwin" else "Ctrl+C"
    SCROLL_DOWN_KEY: ClassVar[str] = "super+down" if platform == "darwin" else "ctrl+down"
    SCROLL_UP_KEY: ClassVar[str] = "super+up" if platform == "darwin" else "ctrl+up"
    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        (REFRESH_KEY, "refresh", "Actualiser"),
        (SCROLL_DOWN_KEY, "scroll_page_down", "Page suivante"),
        (SCROLL_UP_KEY, "scroll_page_up", "Page précédente"),
        ("q", "quit", "Quitter"),
    ]
    CSS = """
    TabbedContent { height: 1fr; }
    TabPane { padding: 0; }
    TabbedContent > Tabs { display: none; }
    #menu-bar { height: 3; padding: 0 1; background: $panel; }
    #menu-bar Button { margin: 0 1 0 0; min-width: 12; }
    VerticalScroll { height: 1fr; }
    #dashboard-content, #measure-form, #treatment-form, #protocol-form,
    #history-content, #help-content, #commands-content {
        width: 72;
        max-width: 100%;
        height: auto;
        padding: 1 2;
    }
    #protocol-form { padding-bottom: 3; }
    .field { height: auto; }
    #protocol-form .field-label { margin-top: 0; }
    #protocol-form CopyableCollapsible { padding-bottom: 0; }
    #protocol-form CopyableCollapsible Contents { padding: 0 0 0 2; }
    #protocol-form Input, #protocol-form Select { margin: 0; }
    #protocol-form Button { margin: 0 1 0 0; }
    .form-section { margin-top: 1; padding: 1 2; border: tall $primary-background; }
    .page-title { text-style: bold; color: $accent; margin-bottom: 1; }
    .section-title { text-style: bold; color: $accent; }
    .section-detail { color: $text-muted; margin-bottom: 1; }
    .field-label { text-style: bold; margin-top: 1; }
    .action-row { height: auto; }
    Input, Select { margin: 0 0 1 0; }
    Button { margin: 1 1 0 0; }
    #history-table { height: 16; margin: 1 0; }
    .warning { color: $warning; }
    .success { color: $success; }
    """

    def __init__(self, root: Path = Path("data/protocoles")) -> None:
        super().__init__()
        self.protocol_service = ProtocolService(JsonProtocolRepository(root))
        self._pending_cancellation: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="menu-bar"):
            yield Button("Accueil", id="menu-dashboard", variant="primary")
            yield Button("Protocole", id="menu-protocol")
            yield Button("Mesures", id="menu-measurements")
            yield Button("Traitement", id="menu-treatment")
            yield Button("Archives", id="menu-history")
            yield Button("Aide", id="menu-help")
        with TabbedContent(initial="dashboard"):
            with (
                TabPane("Tableau de bord", id="dashboard"),
                VerticalScroll(id="dashboard-scroll"),
                Container(id="dashboard-content"),
            ):
                yield Static("Protocole actif", classes="page-title")
                yield Static(
                    "Retrouvez les dernières mesures, l'action attendue et les alertes.",
                    classes="section-detail",
                )
                yield Static("Action à suivre", classes="section-title")
                yield Static("Chargement…", id="dashboard-action")
                yield Button(
                    "Actualiser le tableau de bord", id="refresh-dashboard", variant="primary"
                )
                yield Button("Voir le JSON actif", id="view-active-json")
                yield Button("Arrêter le protocole…", id="cancel-protocol", variant="error")
                yield Static("Chargement…", id="dashboard-status")
            with (
                TabPane("Protocole", id="protocol"),
                VerticalScroll(id="protocol-scroll"),
                Container(id="protocol-form"),
            ):
                yield Static("Actions de protocole", classes="page-title")
                yield Static(
                    "Choisissez d’abord le parcours. Seules les mesures et préparations utiles "
                    "à ce parcours seront affichées.",
                    classes="section-detail",
                )
                with CopyableCollapsible(
                    title="1. Créer ou reprendre un protocole (`start`)", collapsed=False
                ):
                    yield from _field(
                        "Type de protocole",
                        Select(
                            [
                                ("Correction pH/TAC (pH bas)", ProtocolMode.RAISE_PH_TAC.value),
                                (
                                    "Surveillance pH haut (sans dosage)",
                                    ProtocolMode.HIGH_PH_MONITORING.value,
                                ),
                            ],
                            value=ProtocolMode.RAISE_PH_TAC.value,
                            id="new-mode",
                        ),
                    )
                    yield Static(
                        "Correction pH/TAC : remonter un pH bas avec des préparations guidées.",
                        id="new-mode-guidance",
                        classes="section-detail",
                    )
                    yield Static("Mesures et objectifs de la correction", classes="section-title raise-only")
                    yield from _field(
                        "Volume du bassin (m³)",
                        Input(value=str(SETTINGS.protocol.pool_volume_m3), id="new-volume"),
                        classes="raise-only",
                    )
                    yield from _field(
                        "pH initial mesuré",
                        Input(value=str(SETTINGS.protocol.initial_ph), id="new-ph"),
                    )
                    yield from _field(
                        "Palier pH intermédiaire (pH bas)",
                        Input(
                            value=str(SETTINGS.protocol.intermediate_ph), id="new-intermediate-ph"
                        ),
                        classes="raise-only",
                    )
                    yield from _field(
                        "pH cible",
                        Input(value=str(SETTINGS.protocol.target_ph), id="new-target-ph"),
                    )
                    yield from _field(
                        "TAC initial mesuré (ppm)",
                        Input(value=str(SETTINGS.protocol.initial_tac_ppm), id="new-tac"),
                    )
                    yield from _field(
                        "Volume du seau (L)",
                        Input(value=str(SETTINGS.protocol.bucket_volume_l), id="new-bucket"),
                        classes="raise-only",
                    )
                    yield Static("Mesures et bornes de surveillance", classes="section-title monitor-only")
                    yield from _field(
                        "Chlore libre minimum (ppm, selon l’étiquette)",
                        Input(value="1", id="new-chlorine-min"),
                        classes="monitor-only",
                    )
                    yield from _field(
                        "Chlore libre maximum (ppm, selon l’étiquette)",
                        Input(value="4", id="new-chlorine-max"),
                        classes="monitor-only",
                    )
                    yield Static(
                        "L’état des appareils et la désinfection se déclarent après création dans "
                        "l’onglet Traitement.",
                        classes="section-detail",
                    )
                    yield Checkbox(
                        "Forcer une nouvelle archive malgré un protocole actif", id="new-force"
                    )
                    yield Button("Créer / reprendre", id="start-protocol", variant="success")
                yield Static(
                    "Après création : renseignez Traitement, puis journalisez les mesures dans Mesures.",
                    classes="section-detail monitor-only",
                )
                with CopyableCollapsible(
                    title="2. Préparer ou annuler une dose (`dose`, `plan-tac`)", classes="raise-only"
                ):
                    yield Static(
                        "Ne préparez qu'une action compatible avec l'étape indiquée au tableau de bord.",
                        classes="section-detail",
                    )
                    yield from _field(
                        "Volume de NaOH choisi (mL, vide = suggestion)", Input(id="dose-naoh")
                    )
                    yield Button("Préparer la dose NaOH", id="prepare-dose", variant="primary")
                    yield Button(
                        "Annuler une dose NaOH non versée…", id="cancel-dose", variant="warning"
                    )
                    yield from _field("TAC mesuré avant bicarbonate (ppm)", Input(id="plan-tac"))
                    yield Button(
                        "Préparer un lot de bicarbonate", id="prepare-tac", variant="primary"
                    )
                    yield Button(
                        "Annuler un lot bicarbonate non versé…", id="cancel-tac", variant="warning"
                    )
                with CopyableCollapsible(
                    title="3. Corriger une mesure confirmée (`correct-last-measurement`)",
                    classes="raise-only",
                ):
                    yield Static(
                        "Cette action ne retire jamais un produit déjà versé.",
                        classes="section-detail",
                    )
                    yield from _field("pH corrigé", Input(id="correct-ph"))
                    yield from _field("TAC corrigé (ppm)", Input(id="correct-tac"))
                    yield Button("Corriger la dernière mesure", id="correct-measurement")
                with CopyableCollapsible(
                    title="4. Déclarer la soude (`configure-naoh`)", classes="raise-only"
                ):
                    yield Static(
                        "À utiliser uniquement si le même bidon a servi à tous les apports confirmés.",
                        classes="section-detail",
                    )
                    yield from _field(
                        "Forme indiquée sur l’étiquette",
                        Select(
                            [
                                ("g par litre", NaOHConcentrationSource.GRAMS_PER_LITRE.value),
                                (
                                    "pourcentage massique",
                                    NaOHConcentrationSource.MASS_PERCENT.value,
                                ),
                                (
                                    "pourcentage volumique",
                                    NaOHConcentrationSource.VOLUME_PERCENT.value,
                                ),
                            ],
                            value=NaOHConcentrationSource.GRAMS_PER_LITRE.value,
                            id="naoh-source",
                        ),
                    )
                    yield from _field("Valeur (g/L ou pourcentage)", Input(id="naoh-value"))
                    yield from _field("Densité (g/mL, seulement % m/m)", Input(id="naoh-density"))
                    yield Button("Mettre à jour la soude", id="configure-naoh")
            with (
                TabPane("Mesures", id="measurements"),
                VerticalScroll(id="measurements-scroll"),
                Container(id="measure-form"),
            ):
                yield Static("Enregistrer une mesure", classes="page-title")
                yield Static("Chargement…", id="measurement-instructions")
                yield Static(
                    "Commande CLI équivalente : —",
                    id="measurement-command",
                    classes="section-detail",
                )
                yield from _field("pH mesuré dans le bassin", Input(id="measurement-ph"))
                yield from _field("TAC mesuré (ppm)", Input(id="measurement-tac"))
                yield from _field(
                    "Chlore libre mesuré (ppm, pH haut seulement)",
                    Input(id="measurement-chlorine"),
                )
                yield Button("Enregistrer la mesure", id="save-measurement", variant="success")
            with (
                TabPane("Traitement", id="treatment"),
                VerticalScroll(id="treatment-scroll"),
                Container(id="treatment-form"),
            ):
                yield Static("Traitement et appareils", classes="page-title")
                yield Static(
                    "Ces menus documentent l'installation ; ils ne commandent jamais un appareil.",
                    classes="warning",
                )
                with CopyableCollapsible(
                    title="1. Déclarer la désinfection et les appareils", collapsed=False
                ):
                    yield Static(
                        "Une seule source est active. Les trois appareils restent déclarés séparément.",
                        classes="section-detail",
                    )
                    yield from _field(
                        "Désinfection active",
                        Select(_choices(DisinfectionMethod), id="disinfection"),
                    )
                    yield from _field(
                        "Électrolyseur au sel",
                        Select(_choices(ElectrolysisStatus), id="electrolysis"),
                    )
                    yield from _field(
                        "Doseur de galets stabilisés",
                        Select(_choices(StabilizedTabletStatus), id="tablets"),
                    )
                    yield from _field(
                        "Régulateur de pH",
                        Select(_choices(PhRegulatorStatus), id="ph-regulator"),
                    )
                    yield Button("Enregistrer le contexte", id="save-treatment", variant="primary")
                with CopyableCollapsible(title="2. Journaliser une recharge de galets (`record-tablets`)"):
                    yield Static(
                        "Journal uniquement : il ne calcule pas le CYA.",
                        classes="section-detail",
                    )
                    yield from _field("Nombre de galets ajoutés", Input(id="tablets-count"))
                    yield from _field("Masse unitaire (g, facultative)", Input(id="tablets-mass"))
                    yield from _field(
                        "Libellé produit", Input(value="galet stabilisé", id="tablets-product")
                    )
                    yield Button("Enregistrer les galets ajoutés", id="record-tablets")
                with CopyableCollapsible(title="3. Enregistrer une mesure CYA (`measure-cya`)"):
                    yield from _field("CYA mesuré (ppm)", Input(id="cya"))
                    yield Button("Enregistrer le CYA", id="record-cya")
            with (
                TabPane("Archives", id="history"),
                VerticalScroll(id="history-scroll"),
                Container(id="history-content"),
            ):
                yield Static("Archives de protocoles", classes="page-title")
                yield Static(
                    "Les protocoles terminés ou annulés restent conservés ici.",
                    classes="section-detail",
                )
                yield DataTable(id="history-table")
                yield Select([], prompt="Archive JSON à consulter", id="json-archive")
                yield Button("Voir le JSON sélectionné", id="view-archive-json")
                yield Button("Actualiser les archives", id="refresh-history")
            with (
                TabPane("Aide", id="help"),
                VerticalScroll(id="help-scroll"),
                Container(id="help-content"),
            ):
                yield Static("Aide et sécurité", classes="page-title")
                yield Static(
                    "Cette interface ne calcule aucune dose d'acide ou de chlore. Mesurer dans le bassin, "
                    "suivre les notices des produits et ne jamais mélanger les produits.",
                    classes="warning",
                )
                with CopyableCollapsible(title="Navigation rapide", collapsed=False):
                    yield Static(
                        "Accueil : état et action suivante.\nMesures : mesure actuellement attendue.\n"
                        "Protocole : création, dose, bicarbonate, correction et soude.\n"
                        "Traitement : désinfection, appareils, galets et CYA.\nArchives : tous les JSON."
                    )
                with CopyableCollapsible(title="Correspondance complète avec la CLI"):
                    yield Static(
                        "`start` : Agir pH/TAC / Créer ou reprendre\n"
                        "`status` : Accueil / Actualiser\n"
                        "`configure-naoh` : Agir pH/TAC / Déclarer la soude\n"
                        "`treatment`, `record-tablets`, `measure-cya` : Traitement\n"
                        "`record-water`, `measure`, `measure-tac` : Mesurer\n"
                        "`dose`, `plan-tac`, `cancel-dose`, `cancel-tac-plan`, `correct-last-measurement` : Agir pH/TAC\n"
                        "`cancel-protocol` : Accueil / Arrêter le protocole\n"
                        "`history`, `json` : Archives\n"
                        "`menu` : action suivante affichée à l’accueil ; `tui` : interface ouverte.",
                        id="command-index",
                    )
                with CopyableCollapsible(title="Raccourcis"):
                    yield Static(f"{self.REFRESH_KEY_LABEL} : actualiser l’affichage\nq : quitter")
        yield Footer()

    def on_mount(self) -> None:
        """Initialise les vues après le montage des widgets."""
        table = self.query_one("#history-table", DataTable)
        table.add_columns("Archive", "Étape", "pH", "TAC")
        self._update_start_mode(ProtocolMode.RAISE_PH_TAC)
        self.refresh_views()
        self._open_page("dashboard")

    def action_refresh(self) -> None:
        """Raccourci clavier pour relire les données persistées."""
        self.refresh_views()
        self.notify("Affichage actualisé.")

    def action_scroll_page_down(self) -> None:
        """Fait défiler la page active sans exiger que la molette ait le focus."""
        self._active_scroll().scroll_page_down(animate=False)

    def action_scroll_page_up(self) -> None:
        """Fait remonter la page active sans exiger que la molette ait le focus."""
        self._active_scroll().scroll_page_up(animate=False)

    def refresh_views(self) -> None:
        """Actualise le tableau de bord, le formulaire et l'historique."""
        self._refresh_dashboard_and_forms()
        self._refresh_history()

    def _refresh_dashboard_and_forms(self) -> None:
        dashboard = self.query_one("#dashboard-status", Static)
        dashboard_action = self.query_one("#dashboard-action", Static)
        instructions = self.query_one("#measurement-instructions", Static)
        measurement_command = self.query_one("#measurement-command", Static)
        chlorine_input = self.query_one("#measurement-chlorine", Input)
        cancel_button = self.query_one("#cancel-protocol", Button)
        try:
            state = self.protocol_service.active()
        except ValueError:
            dashboard_action.update(
                "Créez ou reprenez un protocole dans l’onglet Protocole avant de saisir une mesure."
            )
            dashboard.update(
                "Aucun protocole actif. Créez-en un dans l’onglet Protocole ou avec la CLI :\n"
                "piscine-ph start …\n\n"
                "L'onglet Historique reste disponible."
            )
            instructions.update("Aucun protocole actif : aucune mesure ne peut être enregistrée.")
            measurement_command.update("Commande CLI équivalente : —")
            chlorine_input.display = False
            cancel_button.display = False
            return

        cancel_button.display = True

        treatment = state.treatment
        lines = [
            f"Archive : {state.archive_name}",
            f"Étape : {state.step.value}",
            f"Dernières mesures : pH {state.current_ph:.2f} · TAC {state.current_tac_ppm:.0f} ppm",
            (
                "Cumul versé : "
                f"NaOH {state.cumulative_additions.naoh_solution_ml:.0f} mL · "
                f"NaHCO₃ {state.cumulative_additions.bicarbonate_kg:.2f} kg"
            ),
            (
                "Traitement : "
                f"désinfection active {treatment.disinfection_method.value}.\n"
                f"Électrolyseur au sel : {treatment.electrolysis_status.value}.\n"
                f"Doseur de galets stabilisés : {treatment.stabilized_tablet_status.value}.\n"
                f"Régulateur pH : {treatment.ph_regulator_status.value}."
            ),
        ]
        if state.pending_naoh:
            lines.append(f"Dose NaOH en attente : {state.pending_naoh.naoh_ml:.0f} mL.")
        if state.pending_bicarbonate:
            lines.append(
                f"Lot bicarbonate en attente : {state.pending_bicarbonate.bicarbonate_kg:.2f} kg."
            )
        if state.config.mode is ProtocolMode.RAISE_PH_TAC:
            lines.append(f"Soude archivée : {state.config.naoh_concentration_g_l:.0f} g/L.")
        lines.append(f"Action CLI suivante : {self.protocol_service.next_command(state)}")
        actions = self.protocol_service.water_actions(state)
        if actions:
            dashboard_action.update(
                "Surveillance pH haut — aucun dosage d’acide ou de chlore n’est calculé.\n"
                + "\n".join(f"• {action}" for action in actions)
            )
        else:
            dashboard_action.update(
                f"Étape suivante : {self.protocol_service.next_command(state)}"
            )
        dashboard.update("\n".join(lines))

        self._set_treatment_values(state)
        if state.step is ProtocolStep.HIGH_PH_MONITORING:
            instructions.update(
                "Surveillance pH haut : saisissez pH, TAC et chlore libre. "
                "Aucun produit ne sera calculé ni ajouté."
            )
            measurement_command.update("Commande CLI équivalente : record-water")
            chlorine_input.display = True
        elif state.pending_naoh:
            instructions.update(
                "Mesure après NaOH : saisissez pH et TAC. Le champ chlore libre est inutile."
            )
            measurement_command.update("Commande CLI équivalente : measure")
            chlorine_input.display = False
        elif state.pending_bicarbonate:
            instructions.update(
                "Mesure après bicarbonate : saisissez pH et TAC. Le champ chlore libre est inutile."
            )
            measurement_command.update("Commande CLI équivalente : measure-tac")
            chlorine_input.display = False
        else:
            instructions.update(
                "Aucune mesure n'est actuellement attendue. Utilisez l'onglet Protocole pour "
                "préparer l'action suivante, puis revenez confirmer la mesure ici."
            )
            measurement_command.update(
                "Commande CLI équivalente : mesure non disponible à cette étape"
            )
            chlorine_input.display = False

    def _set_treatment_values(self, state) -> None:
        """Affiche les valeurs persistées dans les sélecteurs de contexte."""
        self.query_one("#electrolysis", Select).value = state.treatment.electrolysis_status.value
        self.query_one("#disinfection", Select).value = state.treatment.disinfection_method.value
        self.query_one("#ph-regulator", Select).value = state.treatment.ph_regulator_status.value
        self.query_one("#tablets", Select).value = state.treatment.stabilized_tablet_status.value

    def _refresh_history(self) -> None:
        """Relit les archives sans modifier leur contenu."""
        table = self.query_one("#history-table", DataTable)
        archive_select = self.query_one("#json-archive", Select)
        table.clear()
        states = self.protocol_service.repository.archives()
        archive_select.set_options([(state.archive_name, state.archive_name) for state in states])
        if states:
            archive_select.value = states[0].archive_name
        for state in states:
            table.add_row(
                state.archive_name,
                state.step.value,
                f"{state.current_ph:.2f}",
                f"{state.current_tac_ppm:.0f} ppm",
            )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route les boutons vers les opérations de présentation correspondantes."""
        match event.button.id:
            case "menu-dashboard":
                self._open_page("dashboard")
            case "menu-protocol":
                self._open_page("protocol")
            case "menu-measurements":
                self._open_page("measurements")
            case "menu-treatment":
                self._open_page("treatment")
            case "menu-history":
                self._open_page("history")
            case "menu-help":
                self._open_page("help")
            case "refresh-dashboard" | "refresh-history":
                self.refresh_views()
            case "view-active-json":
                self._show_active_json()
            case "view-archive-json":
                self._show_selected_archive_json()
            case "save-measurement":
                self._save_measurement()
            case "save-treatment":
                self._save_treatment()
            case "cancel-protocol":
                self.push_screen(CancelProtocolScreen(), self._confirm_protocol_cancellation)
            case "start-protocol":
                self._start_protocol()
            case "prepare-dose":
                self._prepare_naoh()
            case "cancel-dose":
                self._ask_to_cancel_pending("dose")
            case "prepare-tac":
                self._prepare_bicarbonate()
            case "cancel-tac":
                self._ask_to_cancel_pending("tac")
            case "correct-measurement":
                self._correct_last_measurement()
            case "configure-naoh":
                self._configure_naoh()
            case "record-tablets":
                self._record_tablets()
            case "record-cya":
                self._record_cya()

    def _show_active_json(self) -> None:
        """Ouvre en lecture seule le fichier de l'archive active."""
        try:
            archive_name = self.protocol_service.active().archive_name
        except ValueError as error:
            self._show_error(error)
            return
        self._show_archive_json(archive_name)

    def _show_selected_archive_json(self) -> None:
        """Ouvre en lecture seule l'archive choisie dans la page Archives."""
        value = self.query_one("#json-archive", Select).value
        if value is Select.BLANK:
            self.notify("Choisissez une archive JSON à consulter.", severity="warning")
            return
        self._show_archive_json(str(value))

    def _show_archive_json(self, archive_name: str) -> None:
        """Lit une archive connue puis ouvre sa fenêtre de consultation."""
        states = self.protocol_service.repository.archives()
        state = next((state for state in states if state.archive_name == archive_name), None)
        if state is None:
            self.notify("Cette archive JSON est introuvable.", severity="error")
            return
        path = self.protocol_service.repository.root / archive_name
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as error:
            self.notify(f"Lecture du JSON impossible : {error}", severity="error")
            return
        self.push_screen(JsonViewerScreen(path, self._json_summary(state), content))

    def _json_summary(self, state) -> str:
        """Produit une lecture opérationnelle, distincte du format JSON d'archive."""
        treatment = state.treatment
        lines = [
            f"Parcours : {state.config.mode.value}",
            f"Étape : {state.step.value}",
            f"Dernières mesures : pH {state.current_ph:.2f} · TAC {state.current_tac_ppm:.0f} ppm",
            (
                "Traitement : "
                f"désinfection {treatment.disinfection_method.value} · "
                f"électrolyse {treatment.electrolysis_status.value} · "
                f"régulateur pH {treatment.ph_regulator_status.value}"
            ),
        ]
        if state.water_measurements:
            measurement = state.water_measurements[-1]
            lines.append(
                "Dernière mesure eau : "
                f"pH {measurement.ph:.2f} · TAC {measurement.tac_ppm:.0f} ppm · "
                f"chlore libre {measurement.free_chlorine_ppm:.1f} ppm"
            )
        actions = self.protocol_service.water_actions(state)
        if actions:
            lines.extend(["Décision :", *[f"• {action}" for action in actions]])
        else:
            lines.append(f"Étape suivante : {self.protocol_service.next_command(state)}")
        return "\n".join(lines)

    def _open_page(self, page_id: str) -> None:
        """Ouvre une page depuis la barre de menus persistante."""
        self.query_one(TabbedContent).active = page_id
        for menu_page in ("dashboard", "protocol", "measurements", "treatment", "history", "help"):
            button = self.query_one(f"#menu-{menu_page}", Button)
            button.variant = "primary" if menu_page == page_id else "default"

    def _active_scroll(self) -> VerticalScroll:
        """Retourne la zone de défilement de la page actuellement affichée."""
        page_id = self.query_one(TabbedContent).active
        return self.query_one(f"#{page_id}-scroll", VerticalScroll)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Explique immédiatement la contrainte pH du parcours choisi."""
        if event.select.id != "new-mode":
            return
        self._update_start_mode(ProtocolMode(str(event.value)))

    def _update_start_mode(self, mode: ProtocolMode) -> None:
        """N'affiche que les mesures et opérations du parcours choisi."""
        is_monitoring = mode is ProtocolMode.HIGH_PH_MONITORING
        for widget in self.query(".raise-only"):
            widget.display = not is_monitoring
        for widget in self.query(".monitor-only"):
            widget.display = is_monitoring
        guidance = self.query_one("#new-mode-guidance", Static)
        if is_monitoring:
            guidance.update(
                "Surveillance pH haut : aucune dose ne sera préparée. Saisissez les mesures "
                "initiales, la cible pH et les bornes de chlore de l’étiquette."
            )
        else:
            guidance.update(
                "Correction pH/TAC : pH initial < palier intermédiaire < cible. "
                "Le seau sert aux préparations de soude."
            )

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
            self._show_error(error)
            return
        self.notify("Mesure enregistrée.", severity="information")
        self._clear_measurement_fields()
        self.refresh_views()

    def _save_treatment(self) -> None:
        """Enregistre seulement le contexte explicitement choisi dans les menus."""
        try:
            electrolysis = ElectrolysisStatus(str(self.query_one("#electrolysis", Select).value))
            disinfection = DisinfectionMethod(str(self.query_one("#disinfection", Select).value))
            regulator = PhRegulatorStatus(str(self.query_one("#ph-regulator", Select).value))
            tablets = StabilizedTabletStatus(str(self.query_one("#tablets", Select).value))
            self.protocol_service.set_treatment(electrolysis, disinfection, regulator, tablets)
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Contexte de traitement enregistré.")
        self.refresh_views()

    def _start_protocol(self) -> None:
        """Exécute l'équivalent TUI de ``start --no-guided``."""
        try:
            mode = ProtocolMode(str(self.query_one("#new-mode", Select).value))
            config_values = {
                "mode": mode,
                "initial_ph": float(self.query_one("#new-ph", Input).value),
                "target_ph": float(self.query_one("#new-target-ph", Input).value),
                "initial_tac_ppm": float(self.query_one("#new-tac", Input).value),
            }
            if mode is ProtocolMode.HIGH_PH_MONITORING:
                config_values.update(
                    free_chlorine_min_ppm=float(
                        self.query_one("#new-chlorine-min", Input).value
                    ),
                    free_chlorine_max_ppm=float(
                        self.query_one("#new-chlorine-max", Input).value
                    ),
                )
            else:
                config_values.update(
                    pool_volume_m3=float(self.query_one("#new-volume", Input).value),
                    intermediate_ph=float(self.query_one("#new-intermediate-ph", Input).value),
                    bucket_volume_l=float(self.query_one("#new-bucket", Input).value),
                )
            config = ProtocolConfig(
                **config_values
            )
            state = self.protocol_service.start(
                config,
                TreatmentContext(),
                replace_active=self.query_one("#new-force", Checkbox).value,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self.notify(f"Protocole actif : {state.archive_name}")
        self.refresh_views()

    def _prepare_naoh(self) -> None:
        """Exécute l'équivalent de ``dose`` et affiche seulement sa préparation."""
        try:
            raw_value = self.query_one("#dose-naoh", Input).value.strip()
            state, preparation = self.protocol_service.prepare_naoh(
                float(raw_value) if raw_value else None
            )
        except ValueError as error:
            self._show_error(error)
            return
        self.notify(
            f"Dose préparée : {preparation.naoh_ml:.0f} mL de NaOH dans "
            f"{preparation.water_l:.2f} L d’eau. Archive : {state.archive_name}",
            severity="information",
            timeout=12,
        )
        self.refresh_views()

    def _prepare_bicarbonate(self) -> None:
        """Exécute l'équivalent de ``plan-tac`` depuis le TAC réellement mesuré."""
        try:
            state = self.protocol_service.plan_bicarbonate(
                float(self.query_one("#plan-tac", Input).value)
            )
            pending = state.pending_bicarbonate
            assert pending is not None
        except ValueError as error:
            self._show_error(error)
            return
        self.notify(
            f"Lot préparé : {pending.bicarbonate_kg:.2f} kg maximum. "
            "Attendre puis mesurer pH et TAC.",
            timeout=12,
        )
        self.refresh_views()

    def _ask_to_cancel_pending(self, kind: str) -> None:
        """Demande la même confirmation que les commandes d'annulation CLI."""
        try:
            state = self.protocol_service.active()
            if kind == "dose":
                pending = state.pending_naoh
                if pending is None:
                    raise ValueError("Aucune dose de NaOH en attente à annuler.")
                message = f"Confirmer que les {pending.naoh_ml:.0f} mL n’ont PAS été versés dans le bassin."
            else:
                pending = state.pending_bicarbonate
                if pending is None:
                    raise ValueError("Aucun lot de bicarbonate en attente à annuler.")
                message = (
                    f"Confirmer que les {pending.bicarbonate_kg:.2f} kg n’ont PAS été versés "
                    "dans le bassin."
                )
        except ValueError as error:
            self._show_error(error)
            return
        self._pending_cancellation = kind
        self.push_screen(CancelPendingScreen(message), self._confirm_pending_cancellation)

    def _confirm_pending_cancellation(self, confirmed: bool) -> None:
        """Retire une préparation non versée lorsque l'utilisateur l'atteste."""
        kind = self._pending_cancellation
        self._pending_cancellation = None
        if not confirmed:
            self.notify("Annulation abandonnée.")
            return
        try:
            if kind == "dose":
                self.protocol_service.cancel_pending_naoh()
                label = "Dose de NaOH annulée."
            else:
                self.protocol_service.cancel_pending_bicarbonate()
                label = "Lot de bicarbonate annulé."
        except ValueError as error:
            self._show_error(error)
            return
        self.notify(label)
        self.refresh_views()

    def _correct_last_measurement(self) -> None:
        """Exécute l'équivalent de ``correct-last-measurement``."""
        try:
            self.protocol_service.correct_last_measurement(
                float(self.query_one("#correct-ph", Input).value),
                float(self.query_one("#correct-tac", Input).value),
            )
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Dernière mesure corrigée.")
        self.refresh_views()

    def _configure_naoh(self) -> None:
        """Convertit l'étiquette puis délègue à ``set_naoh_concentration``."""
        try:
            source = NaOHConcentrationSource(str(self.query_one("#naoh-source", Select).value))
            value = float(self.query_one("#naoh-value", Input).value)
            density_text = self.query_one("#naoh-density", Input).value.strip()
            if source is NaOHConcentrationSource.GRAMS_PER_LITRE:
                concentration, percent, density = value, None, None
            elif source is NaOHConcentrationSource.MASS_PERCENT:
                density = float(density_text)
                concentration, percent = value * density * 10, value
            elif source is NaOHConcentrationSource.VOLUME_PERCENT:
                concentration, percent, density = value * 10, value, None
            else:
                raise ValueError("Choisissez g/L, % m/m ou % m/v pour la soude déclarée.")
            self.protocol_service.set_naoh_concentration(concentration, source, percent, density)
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Déclaration de soude mise à jour.")
        self.refresh_views()

    def _record_tablets(self) -> None:
        """Exécute l'équivalent de ``record-tablets``."""
        try:
            mass_text = self.query_one("#tablets-mass", Input).value.strip()
            self.protocol_service.record_stabilized_tablets(
                int(self.query_one("#tablets-count", Input).value),
                float(mass_text) if mass_text else None,
                self.query_one("#tablets-product", Input).value or "galet stabilisé",
            )
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Ajout de galets enregistré.")
        self.refresh_views()

    def _record_cya(self) -> None:
        """Exécute l'équivalent de ``measure-cya``."""
        try:
            self.protocol_service.record_cyanuric_acid_measurement(
                float(self.query_one("#cya", Input).value)
            )
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Mesure de CYA enregistrée.")
        self.refresh_views()

    def _confirm_protocol_cancellation(self, confirmed: bool) -> None:
        """Archive le protocole seulement après confirmation de la fenêtre modale."""
        if not confirmed:
            self.notify("Arrêt du protocole abandonné.")
            return
        try:
            self.protocol_service.cancel_protocol()
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Protocole arrêté et archivé. Vous pouvez en créer un nouveau.")
        self.refresh_views()

    def _clear_measurement_fields(self) -> None:
        for widget_id in ("#measurement-ph", "#measurement-tac", "#measurement-chlorine"):
            self.query_one(widget_id, Input).value = ""

    def _show_error(self, error: ValueError) -> None:
        """Affiche une erreur métier sans interpréter son texte comme du balisage Rich."""
        self.notify(self._error_message(error), severity="error", markup=False)

    @staticmethod
    def _error_message(error: ValueError) -> str:
        """Réduit une validation Pydantic à une erreur immédiatement exploitable."""
        if isinstance(error, ValidationError):
            messages = [str(item["msg"]).removeprefix("Value error, ") for item in error.errors()]
            return " ".join(messages)
        return str(error)
