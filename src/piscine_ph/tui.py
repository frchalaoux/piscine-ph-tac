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
    ProductDeclarationSource,
    ProtocolConfig,
    ProtocolMode,
    ProtocolStep,
    SodiumCarbonateAssessmentRecord,
    SodiumCarbonateProduct,
    StabilizedTabletProduct,
    StabilizedTabletStatus,
    TreatmentContext,
)
from .repository import JsonProtocolRepository
from .service import ProtocolService
from .settings import SETTINGS


def _choices(enum_type: type[ElectrolysisStatus]) -> list[tuple[str, str]]:
    """Transforme une énumération de contexte en options Textual lisibles."""
    return [(item.value.replace("_", " "), item.value) for item in enum_type]


def _treatment_choices(enum_type) -> list[tuple[str, str]]:
    return [("Non renseigné — à déclarer" if item.value == "inconnu"
             else item.value.replace("_", " "), item.value) for item in enum_type]


def _field(label: str, widget: Input | Select, *, classes: str | None = None) -> ComposeResult:
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
    #menu-protocols { width: 24; margin: 0 1 0 0; }
    VerticalScroll { height: 1fr; }
    #guided-content, #dashboard-content, #measure-form, #treatment-form, #protocol-form, #tac-form,
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
        self._follow_up_parent_archive: str | None = None
        self._manual_mode = False
        self._treatment_form_base = TreatmentContext()
        self._pending_start_page: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="menu-bar"):
            yield Button("Accueil", id="menu-dashboard", variant="primary")
            yield Select(
                [
                    ("Mesurer l’eau", "measurements"),
                    ("Corriger le pH", "protocol"),
                    ("Corriger le TAC", "tac"),
                    ("Gérer la désinfection", "treatment"),
                ],
                prompt="Protocoles",
                id="menu-protocols",
            )
            yield Button("Archives", id="menu-history")
            yield Button("Aide", id="menu-help")
        with TabbedContent(initial="guided"):
            with (
                TabPane("Assistant guidé", id="guided"),
                VerticalScroll(id="guided-scroll"),
                Container(id="guided-content"),
            ):
                yield Static("Assistant guidé", classes="page-title")
                yield Static(
                    "Ce parcours indique une seule prochaine action. Il ne verse jamais de produit "
                    "et demande toujours votre mesure de confirmation.",
                    classes="section-detail",
                )
                yield Static("Chargement…", id="guided-step")
                yield Button("Continuer", id="guided-continue", variant="primary")
                yield Button("Voir l’archive active", id="guided-view-active-json")
                yield Button(
                    "Arrêter le protocole…", id="guided-cancel-protocol", variant="error"
                )
                yield Static("", id="guided-summary", markup=False)
                yield Checkbox(
                    "Mode manuel : ne pas revenir automatiquement à l’assistant",
                    id="guided-manual-mode",
                )
                yield Static("Choisir un parcours", id="guided-choices-title",
                             classes="section-title guided-choice")
                with Horizontal(classes="action-row guided-choice"):
                    yield Button("Mesurer l’eau", id="guided-measurements")
                    yield Button("Corriger le pH", id="guided-ph")
                    yield Button("Corriger le TAC", id="guided-tac")
                    yield Button("Désinfection", id="guided-disinfection")
            with (
                TabPane("Tableau de bord", id="dashboard"),
                VerticalScroll(id="dashboard-scroll"),
                Container(id="dashboard-content"),
            ):
                yield Static(
                    "Qu’avez-vous mesuré, et que voulez-vous corriger ?", classes="page-title"
                )
                yield Static(
                    "Mesurer l’eau, corriger le pH ou le TAC, et gérer la désinfection sont "
                    "des parcours distincts. Une nouvelle mesure est toujours requise entre deux lots.",
                    classes="section-detail",
                )
                yield Static("Action à suivre", classes="section-title")
                yield Static("Chargement…", id="dashboard-action")
                yield Button("Arrêter le protocole…", id="cancel-protocol", variant="error")
                yield Button("Voir le JSON actif", id="view-active-json")
                with Horizontal(classes="action-row"):
                    yield Button("Mesurer l’eau", id="dashboard-measurements")
                    yield Button("Corriger le pH", id="dashboard-ph")
                    yield Button("Corriger le TAC", id="dashboard-tac")
                    yield Button("Désinfection", id="dashboard-disinfection")
                yield Button(
                    "Actualiser le tableau de bord", id="refresh-dashboard", variant="primary"
                )
                yield Static("Chargement…", id="dashboard-status")
            with (
                TabPane("Corriger le pH", id="protocol"),
                VerticalScroll(id="protocol-scroll"),
                Container(id="protocol-form"),
            ):
                yield Static("Corriger le pH", classes="page-title")
                yield Static(
                    "Déclarez le produit réellement utilisé. La correction pH reste liée au TAC : "
                    "une mesure pH/TAC est obligatoire avant toute nouvelle action.",
                    classes="section-detail",
                )
                with CopyableCollapsible(
                    title="1. Ouvrir une correction pH ou une étude (`start`)", collapsed=False
                ):
                    yield from _field(
                        "Type de protocole",
                        Select(
                            [
                                ("Remonter le pH avec la soude", ProtocolMode.RAISE_PH_TAC.value),
                                (
                                    "Abaisser le pH avec l’acide sulfurique 15 %",
                                    ProtocolMode.LOWER_PH_MONITORING.value,
                                ),
                                (
                                    "Étude pH+ carbonate (sans dose)",
                                    ProtocolMode.SODIUM_CARBONATE_ASSESSMENT.value,
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
                    yield Static("Mesures et objectifs", classes="section-title")
                    yield from _field(
                        "Volume du bassin (m³)",
                        Input(value=str(SETTINGS.protocol.pool_volume_m3), id="new-volume"),
                        classes="ph-study-only",
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
                    yield from _field(
                        "TAC cible (ppm)",
                        Input(value=str(SETTINGS.protocol.target_tac_ppm), id="new-target-tac"),
                        classes="carbonate-only",
                    )
                    yield Static(
                        "Produit carbonate — étude sans dose",
                        classes="section-title carbonate-only",
                    )
                    yield Static(
                        "Lire l’étiquette ou la FDS. Aucun lot ne sera préparé ni proposé.",
                        classes="section-detail carbonate-only",
                    )
                    yield from _field(
                        "Libellé du produit Na₂CO₃",
                        Input(id="new-carbonate-label"),
                        classes="carbonate-only",
                    )
                    yield from _field(
                        "Pureté Na₂CO₃ (%)",
                        Input(id="new-carbonate-purity"),
                        classes="carbonate-only",
                    )
                    yield from _field(
                        "Source de la pureté",
                        Select(
                            [("Étiquette", "etiquette"), ("FDS", "fds")],
                            value="etiquette",
                            id="new-carbonate-source",
                        ),
                        classes="carbonate-only",
                    )
                    yield Static("", id="carbonate-study-result", classes="carbonate-only")
                    yield Static(
                        "L’état des appareils et la désinfection se déclarent après création dans "
                        "l’onglet Traitement.",
                        classes="section-detail not-carbonate",
                    )
                    yield Checkbox(
                        "Forcer une nouvelle archive malgré un protocole actif",
                        id="new-force",
                        classes="not-carbonate",
                    )
                    yield Button("Créer / reprendre", id="start-protocol", variant="success")
                yield Static(
                    "Après chaque lot, passez par Mesurer l’eau avant de préparer une nouvelle action.",
                    classes="section-detail",
                )
                with CopyableCollapsible(
                    title="2. Préparer ou annuler une dose de soude (`dose`)",
                    classes="raise-only",
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
                with CopyableCollapsible(
                    title="3. Préparer ou annuler un lot d’acide (`dose-acid`)",
                    classes="lower-only",
                ):
                    yield Static(
                        "Le volume est calculé automatiquement selon la notice archivée et plafonné à "
                        "0,1 pH. Aucun volume n’est à choisir ; mesurer ensuite pH et TAC.",
                        classes="section-detail",
                        id="acid-auto-lot-info",
                    )
                    yield Button("Préparer le lot d’acide", id="prepare-acid", variant="primary")
                    yield Button(
                        "Annuler un lot d’acide non versé…", id="cancel-acid", variant="warning"
                    )
                with CopyableCollapsible(
                    title="4. Corriger une mesure confirmée (`correct-last-measurement`)",
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
                    title="5. Déclarer la soude (`configure-naoh`)", classes="raise-only"
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
                TabPane("Corriger le TAC", id="tac"),
                VerticalScroll(id="tac-scroll"),
                Container(id="tac-form"),
            ):
                yield Static("Corriger le TAC", classes="page-title")
                yield Static(
                    "Ce parcours prépare uniquement une hausse au bicarbonate. Une baisse du TAC n’est "
                    "pas calculée automatiquement ; ne la déduisez pas de cette interface.",
                    classes="section-detail",
                )
                with CopyableCollapsible(
                    title="1. Ouvrir une correction TAC au bicarbonate (`start`)", collapsed=False
                ):
                    yield from _field(
                        "Volume du bassin (m³)",
                        Input(value=str(SETTINGS.protocol.pool_volume_m3), id="tac-volume"),
                    )
                    yield from _field("pH mesuré", Input(value="7.2", id="tac-ph"))
                    yield from _field(
                        "TAC mesuré (ppm)",
                        Input(value=str(SETTINGS.protocol.initial_tac_ppm), id="tac-initial"),
                    )
                    yield from _field(
                        "TAC cible (ppm)",
                        Input(value=str(SETTINGS.protocol.target_tac_ppm), id="tac-target"),
                    )
                    yield Checkbox(
                        "Forcer une nouvelle archive malgré un protocole actif", id="tac-force"
                    )
                    yield Button("Ouvrir la correction TAC", id="start-tac", variant="success")
                with CopyableCollapsible(
                    title="2. Préparer ou annuler un lot de bicarbonate (`plan-tac`)"
                ):
                    yield Static(
                        "Le bicarbonate ne sert qu’à la hausse du TAC. Mesurer pH et TAC après chaque lot.",
                        classes="section-detail",
                    )
                    yield from _field("TAC mesuré avant bicarbonate (ppm)", Input(id="plan-tac"))
                    yield Button(
                        "Préparer un lot de bicarbonate", id="prepare-tac", variant="primary"
                    )
                    yield Button(
                        "Annuler un lot bicarbonate non versé…", id="cancel-tac", variant="warning"
                    )
            with (
                TabPane("Mesurer l’eau", id="measurements"),
                VerticalScroll(id="measurements-scroll"),
                Container(id="measure-form"),
            ):
                yield Static("Mesurer l’eau", classes="page-title")
                yield Static("Chargement…", id="measurement-page-intro", classes="section-detail")
                yield Static("", id="measurement-summary", markup=False)
                with CopyableCollapsible(title="Mesures déjà enregistrées", id="measurement-log"):
                    yield Static("", id="measurement-log-content", markup=False)
                with CopyableCollapsible(
                    title="Nouveau relevé d’eau", collapsed=False, id="water-start-section"
                ):
                    yield Static(
                        "Ce parcours enregistre pH et TAC, avec chlore libre facultatif, sans calculer "
                        "d’acide ou de chlore. Relevez d’abord les valeurs dans le bassin, puis "
                        "utilisez ce formulaire ; il reste utilisable même si les cibles sont atteintes.",
                        classes="section-detail",
                    )
                    yield from _field("pH mesuré", Input(value="7.2", id="water-start-ph"))
                    yield from _field(
                        "pH de référence (constat seulement)", Input(value="7.2", id="water-target-ph")
                    )
                    yield from _field("TAC mesuré (ppm)", Input(value="80", id="water-start-tac"))
                    yield from _field(
                        "Chlore libre minimum (ppm, étiquette)",
                        Input(value="1", id="water-chlorine-min"),
                    )
                    yield from _field(
                        "Chlore libre maximum (ppm, étiquette)",
                        Input(value="4", id="water-chlorine-max"),
                    )
                    yield Checkbox(
                        "Forcer une nouvelle archive malgré un protocole actif", id="water-force"
                    )
                    yield Button("Enregistrer ce premier relevé", id="start-water-monitoring")
                yield Static(
                    "Mesure de suivi",
                    id="measurement-followup-title",
                    classes="section-title measurement-followup",
                )
                yield Static("Chargement…", id="measurement-instructions", classes="measurement-followup")
                yield Static(
                    "Commande CLI équivalente : —",
                    id="measurement-command",
                    classes="section-detail measurement-followup",
                )
                yield from _field(
                    "pH mesuré dans le bassin",
                    Input(id="measurement-ph"),
                    classes="measurement-followup",
                )
                yield from _field(
                    "TAC mesuré (ppm)",
                    Input(id="measurement-tac"),
                    classes="measurement-followup",
                )
                yield from _field(
                    "Chlore libre mesuré (ppm)",
                    Input(id="measurement-chlorine"),
                    classes="chlorine-measurement-field measurement-followup",
                )
                yield Button(
                    "Enregistrer cette mesure",
                    id="save-measurement",
                    variant="success",
                    classes="measurement-followup",
                )
            with (
                TabPane("Gérer la désinfection", id="treatment"),
                VerticalScroll(id="treatment-scroll"),
                Container(id="treatment-form"),
            ):
                yield Static("Gérer la désinfection", classes="page-title")
                with CopyableCollapsible(
                    title="1. Déclarer la désinfection et les appareils", collapsed=False,
                    id="treatment-context-section",
                ):
                    yield Static("Contexte non renseigné : déclarez votre installation avant "
                                 "de démarrer, ou reprenez un contexte archivé à vérifier.",
                                 id="treatment-context-status", markup=False)
                    yield Button("Choisir un contexte dans Archives", id="choose-treatment-archive")
                    yield Static(
                        "Une seule source est active. Les trois appareils restent déclarés séparément.",
                        classes="section-detail",
                    )
                    yield from _field(
                        "Désinfection active",
                        Select(_treatment_choices(DisinfectionMethod), id="disinfection",
                               value=DisinfectionMethod.UNKNOWN.value, allow_blank=False),
                    )
                    yield from _field(
                        "Électrolyseur au sel",
                        Select(_treatment_choices(ElectrolysisStatus), id="electrolysis",
                               value=ElectrolysisStatus.UNKNOWN.value, allow_blank=False),
                    )
                    yield from _field(
                        "Doseur de galets stabilisés",
                        Select(_treatment_choices(StabilizedTabletStatus), id="tablets",
                               value=StabilizedTabletStatus.UNKNOWN.value, allow_blank=False),
                    )
                    yield from _field(
                        "Régulateur de pH",
                        Select(_treatment_choices(PhRegulatorStatus), id="ph-regulator",
                               value=PhRegulatorStatus.UNKNOWN.value, allow_blank=False),
                    )
                    yield Button("Enregistrer le contexte", id="save-treatment", variant="primary")
                yield Static("", id="treatment-summary", markup=False)
                yield Button("Ajouter une nouvelle mesure", id="treatment-measurements")
                yield Button("Voir les mesures et paramètres archivés", id="treatment-view-json")
                yield Button("Terminer ce suivi et choisir la suite", id="complete-disinfection")
                yield Static(
                    "Ces menus documentent l'installation ; ils ne commandent jamais un appareil.",
                    classes="warning",
                )
                with CopyableCollapsible(
                    title="2. Démarrer la gestion de la désinfection (`start`)", collapsed=False,
                    id="disinfection-start-section",
                ):
                    yield Static(
                        "Archive les seuils de chlore de l’étiquette, puis demande des mesures. "
                        "Aucune dose de chlore n’est calculée.",
                        classes="section-detail",
                    )
                    yield from _field("pH mesuré", Input(value="7.2", id="disinfection-start-ph"))
                    yield from _field(
                        "TAC mesuré (ppm)", Input(value="80", id="disinfection-start-tac")
                    )
                    yield from _field(
                        "Chlore libre minimum (ppm, étiquette)",
                        Input(value="1", id="disinfection-chlorine-min"),
                    )
                    yield from _field(
                        "Chlore libre maximum (ppm, étiquette)",
                        Input(value="4", id="disinfection-chlorine-max"),
                    )
                    yield Checkbox(
                        "Forcer une nouvelle archive malgré un protocole actif",
                        id="disinfection-force",
                    )
                    yield Button("Démarrer la gestion de la désinfection", id="start-disinfection")
                with CopyableCollapsible(
                    title="3. Journaliser une recharge de galets (`record-tablets`)"
                ):
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
                with CopyableCollapsible(title="4. Enregistrer une mesure CYA (`measure-cya`)"):
                    yield from _field("CYA mesuré (ppm)", Input(id="cya"))
                    yield Button("Enregistrer le CYA", id="record-cya")
            with (
                TabPane("Archives", id="history"),
                VerticalScroll(id="history-scroll"),
                Container(id="history-content"),
            ):
                yield Static("Archives de protocoles", classes="page-title")
                yield Static(
                    "Les suivis actifs, terminés ou annulés sont conservés ici. "
                    "Sélectionnez une ligne ou une archive pour lire ses mesures et paramètres.",
                    classes="section-detail",
                )
                yield DataTable(id="history-table")
                yield Select([], prompt="Archive JSON à consulter", id="json-archive")
                yield Static("", id="archive-summary", markup=False)
                with CopyableCollapsible(title="Toutes les mesures de cette archive"):
                    yield Static("", id="archive-measurements", markup=False)
                yield Button("Voir le JSON sélectionné", id="view-archive-json")
                yield Button("Reprendre ce contexte de traitement…", id="use-archive-treatment")
                yield Button("Enchaîner depuis cette archive", id="follow-up-archive", variant="success")
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
                        "Accueil : état et action suivante.\nMesurer l’eau : relever et archiver pH, TAC et, si disponible, chlore libre.\n"
                        "Corriger le pH : soude, acide ou étude carbonate sans dose.\n"
                        "Corriger le TAC : bicarbonate et re-mesure obligatoire.\n"
                        "Gérer la désinfection : appareils, galets et CYA.\nArchives : tous les JSON."
                    )
                with CopyableCollapsible(title="Correspondance complète avec la CLI"):
                    yield Static(
                        "`start` : Corriger le pH ou Corriger le TAC / Ouvrir le parcours\n"
                        "`status` : Accueil / Actualiser\n"
                        "`configure-naoh`, `dose`, `dose-acid` : Corriger le pH\n"
                        "`plan-tac`, `cancel-tac-plan` : Corriger le TAC\n"
                        "`treatment`, `record-tablets`, `measure-cya` : Gérer la désinfection\n"
                        "`record-water`, `measure`, `measure-acid`, `measure-tac` : Mesurer l’eau\n"
                        "`cancel-dose`, `cancel-acid-dose`, `correct-last-measurement` : parcours pH\n"
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
        table.cursor_type = "row"
        table.add_columns("Archive", "Suite de", "Étape", "pH", "TAC")
        self._update_start_mode(ProtocolMode.RAISE_PH_TAC)
        self.refresh_views()
        self._open_page("guided")

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
        self._refresh_guided()

    def _saved_values(self, state) -> str:
        """Expose les valeurs persistées sans réutiliser les champs de création."""
        config = state.config
        lines = [
            f"Dernières mesures enregistrées : pH {state.current_ph:.2f} · TAC {state.current_tac_ppm:.0f} ppm",
            f"Au démarrage : pH {config.initial_ph:.2f} · TAC {config.initial_tac_ppm:.0f} ppm",
            (f"Seuils de chlore libre enregistrés : min {config.free_chlorine_min_ppm:g} · "
             f"max {config.free_chlorine_max_ppm:g} ppm (étiquette)"),
        ]
        if state.water_measurements:
            last = state.water_measurements[-1]
            chlorine = (f"{last.free_chlorine_ppm:g} ppm"
                        if last.free_chlorine_ppm is not None else "non mesuré")
            lines.append(f"Dernier relevé du {last.recorded_at:%d/%m/%Y %H:%M} : "
                         f"chlore libre {chlorine}")
        else:
            lines.append("Aucun relevé de chlore libre enregistré.")
        lines.append(f"Fichier : {(self.protocol_service.repository.root / state.archive_name).resolve()}")
        return "\n".join(lines)

    @staticmethod
    def _measurement_log(state) -> str:
        lines = []
        for measurement in state.water_measurements:
            chlorine = (f"{measurement.free_chlorine_ppm:g} ppm"
                        if measurement.free_chlorine_ppm is not None else "non mesuré")
            lines.append(f"{measurement.recorded_at:%d/%m/%Y %H:%M:%S} · "
                         f"pH {measurement.ph:.2f} · TAC {measurement.tac_ppm:g} ppm · "
                         f"chlore libre {chlorine}")
        return "\n".join(lines) or "Aucun relevé d’eau enregistré après le démarrage."

    def _refresh_archive_details(self) -> None:
        value = self.query_one("#json-archive", Select).value
        state = (self.protocol_service.repository.archive(str(value))
                 if value is not Select.BLANK else None)
        self.query_one("#archive-summary", Static).update(
            self._saved_values(state) if state else "Sélectionnez une archive pour lire ses valeurs."
        )
        self.query_one("#archive-measurements", Static).update(
            self._measurement_log(state) if state else ""
        )

    def _refresh_guided(self) -> None:
        """Présente l'unique prochaine étape du parcours par défaut."""
        step = self.query_one("#guided-step", Static)
        continue_button = self.query_one("#guided-continue", Button)
        active_json_button = self.query_one("#guided-view-active-json", Button)
        cancel_button = self.query_one("#guided-cancel-protocol", Button)
        try:
            state = self.protocol_service.active()
        except ValueError:
            self.query_one("#guided-summary", Static).display = False
            self.query_one("#guided-choices-title", Static).update("Choisir un parcours")
            missing = self.protocol_service.missing_treatment_fields(self._treatment_from_form())
            step.update(
                "Étape 1 — Déclarez la désinfection et les appareils avant tout protocole. "
                "Un appareil absent doit être déclaré non installé."
                if missing else
                "Étape 1 — Contexte prêt. Choisissez le parcours à démarrer."
            )
            continue_button.display = bool(missing)
            continue_button.label = "Déclarer la désinfection et les appareils"
            active_json_button.display = False
            cancel_button.display = False
            for widget in self.query(".guided-choice"):
                widget.display = True
            return

        continue_button.display = True
        active_json_button.display = True
        cancel_button.display = True
        self.query_one("#guided-summary", Static).display = True
        self.query_one("#guided-summary", Static).update(
            f"Dernières valeurs : pH {state.current_ph:.2f} · TAC {state.current_tac_ppm:g} ppm. "
            "Les mesures et paramètres enregistrés sont consultables dans Mesurer l’eau et Archives."
        )
        self.query_one("#guided-choices-title", Static).update("Accès aux parcours et aux mesures")
        for widget in self.query(".guided-choice"):
            widget.display = True
        action = self.protocol_service.guided_action(state)
        step.update(action.instruction)
        continue_button.label = action.label

    def _continue_guided(self) -> None:
        """Ouvre l'écran qui contient l'unique action proposée par l'assistant."""
        try:
            state = self.protocol_service.active()
        except ValueError:
            self._open_page("treatment")
            return
        action = self.protocol_service.guided_action(state)
        if action.trigger == "prepare_acid":
            self._prepare_acid()
        elif action.trigger == "prepare_naoh":
            self._prepare_guided_naoh()
        elif action.trigger == "follow_up":
            self._start_water_follow_up(state, action)
        elif action.trigger == "complete_water":
            self._complete_water_monitoring()
        else:
            self._open_page(action.destination)
            self.call_after_refresh(self._focus_guided_action, action.destination)

    def _start_water_follow_up(self, state, action) -> None:
        """Termine le relevé puis ouvre le parcours déterminé avec ses mesures liées."""
        try:
            parent = self.protocol_service.complete_water_monitoring()
        except ValueError as error:
            self._show_error(error)
            return
        self._prepare_follow_up(parent)
        if action.protocol_mode is not None:
            selector = self.query_one("#new-mode", Select)
            selector.value = action.protocol_mode.value
            self._update_start_mode(action.protocol_mode)
        self._open_page(action.destination)
        self.call_after_refresh(self._focus_follow_up_start, action.destination)
        self.notify(
            f"Relevé {parent.archive_name} terminé et lié au parcours suivant. "
            "Vérifiez les valeurs préremplies avant de créer ce nouveau parcours.",
            severity="information",
        )

    def _complete_water_monitoring(self) -> None:
        """Ferme un relevé dont l'analyse ne propose aucune correction automatisée."""
        try:
            state = self.protocol_service.complete_water_monitoring()
        except ValueError as error:
            self._show_error(error)
            return
        self.notify(f"Relevé d’eau terminé : {state.archive_name}")
        self.refresh_views()
        self._open_page("history")

    def _complete_disinfection_monitoring(self) -> None:
        try:
            parent = self.protocol_service.complete_disinfection_monitoring()
        except ValueError as error:
            self._show_error(error)
            return
        self._prepare_follow_up(parent)
        self.refresh_views()
        self._open_page("guided")
        self.notify("Suivi terminé et conservé dans Archives. Choisissez la suite ; "
                    "les valeurs préremplies restent à vérifier.")

    def _open_measurement_start(self) -> None:
        """Ouvre le relevé d'eau sur la première valeur à saisir."""
        self._open_page("measurements")
        self.call_after_refresh(self._focus_measurement_start)

    def _focus_measurement_start(self) -> None:
        if self.query_one(TabbedContent).active != "measurements":
            return
        field_id = ("water-start-ph" if self.query_one("#water-start-section").display
                    else "measurement-ph")
        field = self.query_one(f"#{field_id}", Input)
        field.scroll_visible(animate=False)
        field.focus()

    def _focus_follow_up_start(self, destination: str) -> None:
        input_id = {
            "protocol": "new-ph",
            "tac": "tac-ph",
            "treatment": "disinfection-start-ph",
        }.get(destination)
        if input_id is None:
            return
        field = self.query_one(f"#{input_id}", Input)
        field.scroll_visible(animate=False)
        field.focus()

    def _focus_guided_action(self, destination: str) -> None:
        """Place le curseur sur la valeur attendue au lieu d'ouvrir un formulaire général."""
        if destination == "treatment":
            state = self.protocol_service.repository.active()
            if state and self.protocol_service.missing_treatment_fields(state.treatment):
                self.query_one("#treatment-context-section", CopyableCollapsible).collapsed = False
                field = self.query_one("#disinfection", Select)
                field.scroll_visible(animate=False)
                field.focus()
            return
        input_id = {
            "measurements": "measurement-ph",
            "tac": "plan-tac",
        }.get(destination)
        if input_id is None:
            return
        field = self.query_one(f"#{input_id}", Input)
        field.scroll_visible(animate=False)
        field.focus()

    def _workflow_advanced(self) -> None:
        """Actualise puis ramène au guidage, sauf en mode manuel explicite."""
        self.refresh_views()
        if not self._manual_mode:
            self._open_page("guided")

    def _refresh_dashboard_and_forms(self) -> None:
        dashboard = self.query_one("#dashboard-status", Static)
        dashboard_action = self.query_one("#dashboard-action", Static)
        measurement_intro = self.query_one("#measurement-page-intro", Static)
        water_start = self.query_one("#water-start-section", CopyableCollapsible)
        followup_title = self.query_one("#measurement-followup-title", Static)
        followup_widgets = self.query(".measurement-followup")
        instructions = self.query_one("#measurement-instructions", Static)
        measurement_command = self.query_one("#measurement-command", Static)
        chlorine_input = self.query_one("#measurement-chlorine", Input)
        chlorine_field = self.query_one(".chlorine-measurement-field", Container)
        cancel_button = self.query_one("#cancel-protocol", Button)
        for selector in ("#measurement-summary", "#measurement-log", "#treatment-summary",
                         "#treatment-measurements", "#treatment-view-json", "#complete-disinfection"):
            self.query_one(selector).display = False
        self.query_one("#disinfection-start-section").display = True
        try:
            state = self.protocol_service.active()
        except ValueError:
            measurement_intro.update(
                "Nouveau relevé : mesurez d’abord l’eau du bassin, puis saisissez ces valeurs pour "
                "créer son archive."
            )
            water_start.display = True
            for widget in followup_widgets:
                widget.display = False
            dashboard_action.update(
                "Ouvrez une correction pH ou TAC, ou une surveillance, avant de saisir une mesure."
            )
            dashboard.update(
                "Aucun protocole actif. Ouvrez une correction pH ou TAC, ou utilisez la CLI :\n"
                "piscine-ph start …\n\n"
                "L'onglet Historique reste disponible."
            )
            instructions.update("Aucun protocole actif : aucune mesure ne peut être enregistrée.")
            measurement_command.update("Commande CLI équivalente : —")
            chlorine_input.display = False
            chlorine_field.display = False
            cancel_button.display = False
            return

        cancel_button.display = True
        for selector in ("#measurement-summary", "#measurement-log", "#treatment-summary",
                         "#treatment-measurements", "#treatment-view-json"):
            self.query_one(selector).display = True
        self.query_one("#measurement-summary", Static).update(self._saved_values(state))
        self.query_one("#measurement-log-content", Static).update(self._measurement_log(state))
        self.query_one("#treatment-summary", Static).update(
            self._saved_values(state) + "\n\nBilan du suivi :\n"
            + "\n".join(self.protocol_service.water_actions(state))
        )
        is_disinfection = state.config.mode is ProtocolMode.DISINFECTION_MONITORING
        self.query_one("#disinfection-start-section").display = not is_disinfection
        self.query_one("#complete-disinfection").display = is_disinfection
        self.query_one("#complete-disinfection", Button).disabled = not state.water_measurements
        water_start.display = False
        for widget in followup_widgets:
            widget.display = True

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
        if state.parent_archive_name:
            lines.insert(1, f"Suite de : {state.parent_archive_name}")
        if state.pending_naoh:
            lines.append(f"Dose NaOH en attente : {state.pending_naoh.naoh_ml:.0f} mL.")
        if state.pending_acid:
            lines.append(
                f"Lot d’acide sulfurique 15 % en attente : {state.pending_acid.acid_ml:.0f} mL."
            )
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
            dashboard_action.update(f"Étape suivante : {self.protocol_service.next_command(state)}")
        dashboard.update("\n".join(lines))

        self._set_treatment_values(state)
        if state.step is ProtocolStep.HIGH_PH_MONITORING:
            if state.config.mode is ProtocolMode.WATER_MONITORING:
                measurement_intro.update(
                    "Relevé en cours : ajoutez une nouvelle mesure au relevé déjà créé."
                )
                followup_title.update("Ajouter une mesure au relevé")
                instructions.update(
                    "Saisissez pH et TAC ; le chlore libre est facultatif. "
                    "Aucun produit ne sera calculé ni ajouté."
                )
            else:
                measurement_intro.update(
                    "Surveillance en cours : ajoutez la prochaine mesure demandée par le protocole."
                )
                followup_title.update("Nouvelle mesure de surveillance")
                instructions.update(
                    "Surveillance : saisissez pH, TAC et chlore libre. "
                    "Aucun produit ne sera calculé ni ajouté."
                )
            measurement_command.update("Commande CLI équivalente : record-water")
            chlorine_input.display = True
            chlorine_field.display = True
        elif state.pending_naoh:
            measurement_intro.update(
                "Confirmation en cours : relevez l’eau après le lot de soude déjà versé."
            )
            followup_title.update("Mesure de confirmation après soude")
            instructions.update(
                "Mesure après NaOH : saisissez pH et TAC. Le champ chlore libre est inutile."
            )
            measurement_command.update("Commande CLI équivalente : measure")
            chlorine_input.display = False
            chlorine_field.display = False
        elif state.pending_acid:
            measurement_intro.update(
                "Confirmation en cours : relevez l’eau après le lot d’acide déjà versé."
            )
            followup_title.update("Mesure de confirmation après acide")
            instructions.update(
                "Mesure après acide : saisissez pH et TAC. Le champ chlore libre est inutile."
            )
            measurement_command.update("Commande CLI équivalente : measure-acid")
            chlorine_input.display = False
            chlorine_field.display = False
        elif state.pending_bicarbonate:
            measurement_intro.update(
                "Confirmation en cours : relevez l’eau après le lot de bicarbonate déjà versé."
            )
            followup_title.update("Mesure de confirmation après bicarbonate")
            instructions.update(
                "Mesure après bicarbonate : saisissez pH et TAC. Le champ chlore libre est inutile."
            )
            measurement_command.update("Commande CLI équivalente : measure-tac")
            chlorine_input.display = False
            chlorine_field.display = False
        else:
            measurement_intro.update(
                "Protocole en cours : cette page ne sert qu’aux mesures que le protocole attend."
            )
            followup_title.update("Aucune mesure attendue")
            instructions.update(
                "Aucune mesure n'est actuellement attendue. Utilisez Corriger le pH ou Corriger le TAC "
                "pour préparer l'action suivante, puis revenez confirmer la mesure ici."
            )
            measurement_command.update(
                "Commande CLI équivalente : mesure non disponible à cette étape"
            )
            chlorine_input.display = False
            chlorine_field.display = False

    def _set_treatment_values(self, state) -> None:
        """Affiche les valeurs persistées dans les sélecteurs de contexte."""
        self._treatment_form_base = state.treatment.model_copy(deep=True)
        self.query_one("#electrolysis", Select).value = state.treatment.electrolysis_status.value
        self.query_one("#disinfection", Select).value = state.treatment.disinfection_method.value
        self.query_one("#ph-regulator", Select).value = state.treatment.ph_regulator_status.value
        self.query_one("#tablets", Select).value = state.treatment.stabilized_tablet_status.value
        missing = self.protocol_service.missing_treatment_fields(state.treatment)
        self.query_one("#treatment-context-section", CopyableCollapsible).collapsed = not missing
        self.query_one("#treatment-context-status", Static).update(
            f"Contexte enregistré dans {state.archive_name}. "
            + ("À renseigner : " + ", ".join(missing) + "." if missing
               else "Les quatre paramètres sont renseignés ; vérifiez leur état actuel.")
        )

    def _treatment_from_form(self) -> TreatmentContext:
        values = self._treatment_form_base.model_dump()
        values.update(
            electrolysis_status=self.query_one("#electrolysis", Select).value,
            disinfection_method=self.query_one("#disinfection", Select).value,
            ph_regulator_status=self.query_one("#ph-regulator", Select).value,
            stabilized_tablet_status=self.query_one("#tablets", Select).value,
        )
        if values["disinfection_method"] != DisinfectionMethod.STABILIZED_TABLETS.value:
            values["stabilized_tablet_product"] = StabilizedTabletProduct.UNKNOWN
        return TreatmentContext.model_validate(values)

    def _prepare_archived_treatment(self) -> None:
        value = self.query_one("#json-archive", Select).value
        state = self.protocol_service.repository.archive(str(value))
        if state is None:
            self.notify("Sélectionnez une archive pour reprendre son contexte.", severity="warning")
            return
        self._set_treatment_values(state)
        self.query_one("#treatment-context-status", Static).update(
            f"Contexte repris de {state.archive_name}, non encore enregistré. "
            "Vérifiez les valeurs puis cliquez sur Enregistrer le contexte "
            "(ou démarrez le nouveau parcours)."
        )
        self.query_one("#treatment-context-section", CopyableCollapsible).collapsed = False
        self._open_page("treatment")
        self.call_after_refresh(self.query_one("#treatment-context-section").scroll_visible,
                                animate=False)

    def _refresh_history(self) -> None:
        """Relit les archives sans modifier leur contenu."""
        table = self.query_one("#history-table", DataTable)
        archive_select = self.query_one("#json-archive", Select)
        table.clear()
        states = self.protocol_service.repository.archives()
        selected = archive_select.value
        archive_select.set_options([(state.archive_name, state.archive_name) for state in states])
        if states:
            archive_select.value = (selected if any(state.archive_name == selected for state in states)
                                    else states[0].archive_name)
        self._refresh_archive_details()
        for state in states:
            table.add_row(
                state.archive_name,
                state.parent_archive_name or "—",
                state.step.value,
                f"{state.current_ph:.2f}",
                f"{state.current_tac_ppm:.0f} ppm",
                key=state.archive_name,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "history-table" and event.row_key.value is not None:
            self.query_one("#json-archive", Select).value = event.row_key.value
            self.query_one("#archive-summary").scroll_visible(animate=False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Route les boutons vers les opérations de présentation correspondantes."""
        match event.button.id:
            case "menu-dashboard":
                self._open_page("guided")
            case "guided-measurements" | "dashboard-measurements" | "treatment-measurements":
                self._open_measurement_start()
            case "guided-ph":
                self._open_page("protocol")
            case "guided-tac":
                self._open_page("tac")
            case "guided-disinfection":
                self._open_page("treatment")
            case "guided-continue":
                self._continue_guided()
            case "guided-view-active-json":
                self._show_active_json()
            case "treatment-view-json":
                self._show_active_json()
            case "choose-treatment-archive":
                self._open_page("history")
            case "use-archive-treatment":
                self._prepare_archived_treatment()
            case "complete-disinfection":
                self._complete_disinfection_monitoring()
            case "guided-cancel-protocol":
                self.push_screen(CancelProtocolScreen(), self._confirm_protocol_cancellation)
            case "dashboard-ph":
                self._open_page("protocol")
            case "dashboard-tac":
                self._open_page("tac")
            case "dashboard-disinfection":
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
            case "follow-up-archive":
                self._select_follow_up_archive()
            case "save-measurement":
                self._save_measurement()
            case "start-water-monitoring":
                self._start_water_monitoring()
            case "save-treatment":
                self._save_treatment()
            case "start-disinfection":
                self._start_disinfection_monitoring()
            case "cancel-protocol":
                self.push_screen(CancelProtocolScreen(), self._confirm_protocol_cancellation)
            case "start-protocol":
                self._start_protocol()
            case "start-tac":
                self._start_tac_protocol()
            case "prepare-dose":
                self._prepare_naoh()
            case "cancel-dose":
                self._ask_to_cancel_pending("dose")
            case "prepare-acid":
                self._prepare_acid()
            case "cancel-acid":
                self._ask_to_cancel_pending("acid")
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

    def _select_follow_up_archive(self) -> None:
        """Prépare une nouvelle archive explicitement liée à une archive terminale."""
        value = self.query_one("#json-archive", Select).value
        if value is Select.BLANK:
            self.notify("Choisissez une archive à enchaîner.", severity="warning")
            return
        parent = self.protocol_service.repository.archive(str(value))
        if parent is None:
            self.notify("Cette archive est introuvable ou illisible.", severity="error")
            return
        if parent.step not in {ProtocolStep.COMPLETE, ProtocolStep.CANCELLED}:
            self.notify("Terminez ou annulez cette archive avant de l’enchaîner.", severity="warning")
            return
        if self.protocol_service.repository.active() is not None:
            self.notify("Terminez ou annulez le protocole actif avant d’enchaîner.", severity="warning")
            return
        self._prepare_follow_up(parent)
        self._open_page("guided")
        self.notify(
            f"Suite de {parent.archive_name} préparée : les dernières valeurs sont préremplies, "
            "mais doivent être vérifiées par une nouvelle mesure.",
            severity="information",
        )

    def _prepare_follow_up(self, parent) -> None:
        """Préremplit les formulaires et mémorise le lien vers une archive parent terminale."""
        self._follow_up_parent_archive = parent.archive_name
        self._set_treatment_values(parent)
        values = {
            "new-ph": f"{parent.current_ph:.2f}",
            "new-tac": f"{parent.current_tac_ppm:.0f}",
            "new-volume": f"{parent.config.pool_volume_m3:g}",
            "tac-ph": f"{parent.current_ph:.2f}",
            "tac-initial": f"{parent.current_tac_ppm:.0f}",
            "tac-volume": f"{parent.config.pool_volume_m3:g}",
            "water-start-ph": f"{parent.current_ph:.2f}",
            "water-start-tac": f"{parent.current_tac_ppm:.0f}",
            "disinfection-start-ph": f"{parent.current_ph:.2f}",
            "disinfection-start-tac": f"{parent.current_tac_ppm:.0f}",
            "water-chlorine-min": f"{parent.config.free_chlorine_min_ppm:g}",
            "water-chlorine-max": f"{parent.config.free_chlorine_max_ppm:g}",
            "disinfection-chlorine-min": f"{parent.config.free_chlorine_min_ppm:g}",
            "disinfection-chlorine-max": f"{parent.config.free_chlorine_max_ppm:g}",
        }
        for input_id, input_value in values.items():
            self.query_one(f"#{input_id}", Input).value = input_value

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
            self._saved_values(state),
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
                + (f"chlore libre {measurement.free_chlorine_ppm:.1f} ppm"
                   if measurement.free_chlorine_ppm is not None else "chlore libre non mesuré")
            )
        successors = self.protocol_service.repository.successors(state.archive_name)
        if successors:
            lines.append("Suites : " + ", ".join(successor.archive_name for successor in successors))
        actions = self.protocol_service.water_actions(state)
        if actions:
            lines.extend(["Décision :", *[f"• {action}" for action in actions]])
        else:
            lines.append(f"Étape suivante : {self.protocol_service.next_command(state)}")
        return "\n".join(lines)

    def _open_page(self, page_id: str) -> None:
        """Ouvre une page depuis la barre de menus persistante."""
        if (page_id in {"protocol", "tac", "measurements"}
                and self.protocol_service.repository.active() is None
                and self.protocol_service.missing_treatment_fields(self._treatment_from_form())):
            self._pending_start_page = page_id
            page_id = "treatment"
            self.query_one("#treatment-context-section", CopyableCollapsible).collapsed = False
        # Libérer le bouton avant de masquer sa page : sinon Textual reporte
        # le focus dans cette même page et son TabPane.Focused la réactive.
        self.set_focus(None)
        self.query_one(TabbedContent).active = page_id
        for menu_page in ("dashboard", "history", "help"):
            button = self.query_one(f"#menu-{menu_page}", Button)
            button.variant = "primary" if menu_page == page_id or (
                menu_page == "dashboard" and page_id == "guided"
            ) else "default"

    def _active_scroll(self) -> VerticalScroll:
        """Retourne la zone de défilement de la page actuellement affichée."""
        page_id = self.query_one(TabbedContent).active
        return self.query_one(f"#{page_id}-scroll", VerticalScroll)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Ouvre un parcours ou explique les contraintes du choix pH."""
        if event.select.id == "json-archive":
            self._refresh_archive_details()
            return
        if event.select.id == "menu-protocols":
            if event.value is not Select.BLANK:
                self._open_page(str(event.value))
                event.select.clear()
            return
        if event.select.id != "new-mode":
            return
        self._update_start_mode(ProtocolMode(str(event.value)))

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        """Laisse un utilisateur expérimenté conserver le contexte de son écran."""
        if event.checkbox.id == "guided-manual-mode":
            self._manual_mode = event.value

    def _update_start_mode(self, mode: ProtocolMode) -> None:
        """N'affiche que les mesures et opérations du parcours choisi."""
        is_carbonate_study = mode is ProtocolMode.SODIUM_CARBONATE_ASSESSMENT
        is_raise = mode is ProtocolMode.RAISE_PH_TAC
        is_lower = mode is ProtocolMode.LOWER_PH_MONITORING
        for widget in self.query(".raise-only"):
            widget.display = is_raise
        for widget in self.query(".lower-only"):
            widget.display = is_lower
        for widget in self.query(".carbonate-only"):
            widget.display = is_carbonate_study
        for widget in self.query(".ph-study-only"):
            widget.display = is_raise or is_lower or is_carbonate_study
        for widget in self.query(".not-carbonate"):
            widget.display = not is_carbonate_study
        guidance = self.query_one("#new-mode-guidance", Static)
        if is_lower:
            guidance.update(
                "Correction pH vers le bas : l’acide sulfurique 15 % déclaré est préparé par "
                "étapes de 0,1 pH avec mesure obligatoire."
            )
        elif is_carbonate_study:
            guidance.update(
                "Étude carbonate : archivez le produit, sa pureté et sa source. Le résultat "
                "borne le TAC et alerte sur le pH ; il ne crée jamais de dose."
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
                chlorine_text = self.query_one("#measurement-chlorine", Input).value.strip()
                chlorine = float(chlorine_text) if chlorine_text else None
                state = self.protocol_service.record_water_measurement(ph, tac, chlorine)
            elif state.pending_naoh:
                state = self.protocol_service.record_naoh_measurement(ph, tac)
            elif state.pending_acid:
                state = self.protocol_service.record_sulfuric_acid_measurement(ph, tac)
            elif state.pending_bicarbonate:
                state = self.protocol_service.record_bicarbonate_measurement(ph, tac)
            else:
                raise ValueError("Aucune mesure de confirmation n'est attendue à cette étape.")
        except ValueError as error:
            self._show_error(error)
            return
        self.notify("Mesure enregistrée.", severity="information")
        self._clear_measurement_fields()
        if state.step is ProtocolStep.COMPLETE:
            self._prepare_follow_up(state)
        self._workflow_advanced()
        if state.config.mode is ProtocolMode.DISINFECTION_MONITORING and not self._manual_mode:
            self._open_page("treatment")
            self.query_one("#treatment-scroll", VerticalScroll).scroll_home(animate=False)

    def _save_treatment(self) -> None:
        """Enregistre seulement le contexte explicitement choisi dans les menus."""
        try:
            context = self._treatment_from_form()
            self.protocol_service.require_treatment_context(context)
            if self.protocol_service.repository.active() is None:
                self._treatment_form_base = context
                self.query_one("#treatment-context-status", Static).update(
                    "Contexte préparé : il sera enregistré au démarrage du nouveau parcours."
                )
                self.query_one("#treatment-context-section", CopyableCollapsible).collapsed = True
                destination = self._pending_start_page or "guided"
                self._pending_start_page = None
                self.refresh_views()
                self._open_page(destination)
                return
            self.protocol_service.set_treatment(
                context.electrolysis_status, context.disinfection_method,
                context.ph_regulator_status, context.stabilized_tablet_status,
                context.stabilized_tablet_product,
            )
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
            if mode is ProtocolMode.SODIUM_CARBONATE_ASSESSMENT:
                config_values.update(
                    pool_volume_m3=float(self.query_one("#new-volume", Input).value),
                    target_tac_ppm=float(self.query_one("#new-target-tac", Input).value),
                    sodium_carbonate_product=SodiumCarbonateProduct(
                        label=self.query_one("#new-carbonate-label", Input).value.strip(),
                        purity_percent=float(self.query_one("#new-carbonate-purity", Input).value),
                        purity_source=ProductDeclarationSource(
                            str(self.query_one("#new-carbonate-source", Select).value)
                        ),
                    ),
                )
            else:
                config_values.update(
                    pool_volume_m3=float(self.query_one("#new-volume", Input).value),
                    intermediate_ph=float(self.query_one("#new-intermediate-ph", Input).value),
                    bucket_volume_l=float(self.query_one("#new-bucket", Input).value),
                )
            config = ProtocolConfig(**config_values)
            state = self.protocol_service.start(
                config,
                self._treatment_from_form(),
                replace_active=self.query_one("#new-force", Checkbox).value,
                follow_up_from=self._follow_up_parent_archive,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._clear_used_follow_up(state)
        if state.sodium_carbonate_assessment:
            self._show_sodium_carbonate_assessment(state.sodium_carbonate_assessment)
            self.notify(f"Étude carbonate archivée : {state.archive_name}")
        else:
            self.notify(f"Protocole actif : {state.archive_name}")
        self._workflow_advanced()

    def _start_tac_protocol(self) -> None:
        """Ouvre le parcours distinct de hausse du TAC au bicarbonate."""
        try:
            config = ProtocolConfig(
                mode=ProtocolMode.RAISE_TAC,
                pool_volume_m3=float(self.query_one("#tac-volume", Input).value),
                initial_ph=float(self.query_one("#tac-ph", Input).value),
                initial_tac_ppm=float(self.query_one("#tac-initial", Input).value),
                target_tac_ppm=float(self.query_one("#tac-target", Input).value),
            )
            state = self.protocol_service.start(
                config,
                self._treatment_from_form(),
                replace_active=self.query_one("#tac-force", Checkbox).value,
                follow_up_from=self._follow_up_parent_archive,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._clear_used_follow_up(state)
        self.notify(f"Correction TAC active : {state.archive_name}")
        self._workflow_advanced()

    def _start_water_monitoring(self) -> None:
        """Crée le parcours de mesures eau sans calculer une correction."""
        try:
            config = ProtocolConfig(
                mode=ProtocolMode.WATER_MONITORING,
                initial_ph=float(self.query_one("#water-start-ph", Input).value),
                target_ph=float(self.query_one("#water-target-ph", Input).value),
                initial_tac_ppm=float(self.query_one("#water-start-tac", Input).value),
                free_chlorine_min_ppm=float(self.query_one("#water-chlorine-min", Input).value),
                free_chlorine_max_ppm=float(self.query_one("#water-chlorine-max", Input).value),
            )
            state = self.protocol_service.start(
                config,
                self._treatment_from_form(),
                replace_active=self.query_one("#water-force", Checkbox).value,
                follow_up_from=self._follow_up_parent_archive,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._clear_used_follow_up(state)
        self.notify(f"Surveillance de l’eau active : {state.archive_name}")
        self._workflow_advanced()

    def _start_disinfection_monitoring(self) -> None:
        """Crée le parcours autonome de gestion de la désinfection."""
        try:
            config = ProtocolConfig(
                mode=ProtocolMode.DISINFECTION_MONITORING,
                initial_ph=float(self.query_one("#disinfection-start-ph", Input).value),
                initial_tac_ppm=float(self.query_one("#disinfection-start-tac", Input).value),
                free_chlorine_min_ppm=float(
                    self.query_one("#disinfection-chlorine-min", Input).value
                ),
                free_chlorine_max_ppm=float(
                    self.query_one("#disinfection-chlorine-max", Input).value
                ),
            )
            state = self.protocol_service.start(
                config,
                self._treatment_from_form(),
                replace_active=self.query_one("#disinfection-force", Checkbox).value,
                follow_up_from=self._follow_up_parent_archive,
            )
        except ValueError as error:
            self._show_error(error)
            return
        self._clear_used_follow_up(state)
        self.notify(f"Gestion de la désinfection active : {state.archive_name}")
        self._workflow_advanced()

    def _clear_used_follow_up(self, state) -> None:
        """Oublie la sélection seulement après la création de son archive fille."""
        if state.parent_archive_name == self._follow_up_parent_archive:
            self._follow_up_parent_archive = None

    def _show_sodium_carbonate_assessment(self, record: SodiumCarbonateAssessmentRecord) -> None:
        """Affiche le résultat persistant de l'étude sans le transformer en lot."""
        lines = [
            "ÉTUDE CARBONATE DE SODIUM — AUCUNE DOSE",
            (
                f"Produit archivé : {record.product.label} (Na₂CO₃, "
                f"{record.product.purity_percent:.1f} %, source {record.product.purity_source.value})."
            ),
            f"Mesures : pH {record.ph_measured:.2f} · TAC {record.tac_measured_ppm:.0f} ppm.",
        ]
        if record.can_be_considered:
            lines.append(
                f"Plafond théorique avant la cible TAC : {record.tac_limited_product_kg:.2f} kg "
                "(ce n’est pas une dose ni un lot)."
            )
            if record.expected_ph_at_tac_limit is not None:
                lines.append(
                    f"pH théorique à ce plafond : {record.expected_ph_at_tac_limit:.2f} · "
                    f"TAC théorique : {record.expected_tac_ppm:.0f} ppm."
                )
        else:
            lines.append("Carbonate écarté pour ces mesures : aucun lot n’est proposé.")
        lines.extend(f"Alerte : {warning}" for warning in record.warnings)
        self.query_one("#carbonate-study-result", Static).update("\n".join(lines))

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
        self._workflow_advanced()

    def _prepare_guided_naoh(self) -> None:
        """Prépare la suggestion NaOH sans demander de volume dans le parcours guidé."""
        try:
            state, preparation = self.protocol_service.prepare_naoh()
        except ValueError as error:
            self._show_error(error)
            return
        self.notify(
            f"Dose préparée : {preparation.naoh_ml:.0f} mL de NaOH dans "
            f"{preparation.water_l:.2f} L d’eau. Archive : {state.archive_name}",
            severity="information",
            timeout=12,
        )
        self._workflow_advanced()

    def _prepare_acid(self) -> None:
        """Prépare le lot automatique et plafonné du parcours pH bas."""
        try:
            state = self.protocol_service.prepare_sulfuric_acid()
            pending = state.pending_acid
            if pending is None:
                self.notify("pH cible déjà atteint : aucun lot d’acide préparé.")
            else:
                self.notify(
                    f"Lot d’acide préparé : {pending.acid_ml:.0f} mL maximum. "
                    "Mesurer pH et TAC avant toute autre action.",
                    timeout=12,
                )
        except ValueError as error:
            self._show_error(error)
            return
        self._workflow_advanced()

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
        self._workflow_advanced()

    def _ask_to_cancel_pending(self, kind: str) -> None:
        """Demande la même confirmation que les commandes d'annulation CLI."""
        try:
            state = self.protocol_service.active()
            if kind == "dose":
                pending = state.pending_naoh
                if pending is None:
                    raise ValueError("Aucune dose de NaOH en attente à annuler.")
                message = f"Confirmer que les {pending.naoh_ml:.0f} mL n’ont PAS été versés dans le bassin."
            elif kind == "acid":
                pending = state.pending_acid
                if pending is None:
                    raise ValueError("Aucun lot d’acide en attente à annuler.")
                message = (
                    f"Confirmer que les {pending.acid_ml:.0f} mL d’acide n’ont PAS été versés "
                    "dans le bassin."
                )
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
            elif kind == "acid":
                self.protocol_service.cancel_pending_acid()
                label = "Lot d’acide annulé."
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
