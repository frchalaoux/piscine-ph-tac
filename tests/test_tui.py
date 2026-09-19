"""Tests d'intégration légers de l'interface Textual."""

import asyncio
from sys import platform

import pytest
from conftest import declare_tui_context, declared_treatment
from textual.containers import Container, VerticalScroll
from textual.widgets import Button, Checkbox, Input, Select, Static, TabbedContent

from piscine_ph.models import ProtocolConfig, ProtocolMode, ProtocolStep
from piscine_ph.repository import JsonProtocolRepository
from piscine_ph.service import ProtocolService
from piscine_ph.tui import (
    CopyableCollapsible,
    CopyableCollapsibleTitle,
    JsonViewerScreen,
    PiscinePhTui,
)


def test_tui_explains_how_to_create_a_protocol_when_none_is_active(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            dashboard = app.query_one("#dashboard-status", Static)
            assert "Aucun protocole actif" in str(dashboard.render())

    asyncio.run(scenario())


def test_tui_guided_mode_is_default_and_routes_to_the_single_next_action(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "guided"
            assert "Étape 1" in str(app.query_one("#guided-step", Static).render())

            app._open_page("tac")
            app._start_tac_protocol()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "guided"
            assert "bicarbonate" in str(app.query_one("#guided-step", Static).render())

            app._continue_guided()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tac"

    asyncio.run(scenario())


def test_tui_measure_water_choice_opens_and_focuses_the_measurement_start(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            await pilot.click("#guided-measurements")
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "measurements"
            assert app.focused is app.query_one("#water-start-ph", Input)

    asyncio.run(scenario())


def test_tui_measure_page_distinguishes_a_new_reading_from_a_follow_up(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            assert app.query_one("#water-start-section", CopyableCollapsible).display
            assert not any(widget.display for widget in app.query(".measurement-followup"))

            app._open_measurement_start()
            app.query_one("#water-start-ph", Input).value = "7.2"
            app.query_one("#water-start-tac", Input).value = "80"
            app._start_water_monitoring()
            await pilot.pause()

            assert not app.query_one("#water-start-section", CopyableCollapsible).display
            assert "Ajouter une mesure" in str(
                app.query_one("#measurement-followup-title", Static).render()
            )
            assert app.query_one("#measurement-ph", Input).display

    asyncio.run(scenario())


def test_tui_water_measurement_recommends_and_links_the_next_protocol(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_measurement_start()
            app.query_one("#water-start-ph", Input).value = "6.8"
            app.query_one("#water-target-ph", Input).value = "7.2"
            app.query_one("#water-start-tac", Input).value = "60"
            app._start_water_monitoring()
            await pilot.pause()
            app._continue_guided()
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "6.8"
            app.query_one("#measurement-tac", Input).value = "60"
            app._save_measurement()
            await pilot.pause()
            assert "Corriger le TAC" in str(app.query_one("#guided-step", Static).render())

            app._continue_guided()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tac"
            assert app.focused is app.query_one("#tac-ph", Input)
            assert app.query_one("#tac-initial", Input).value == "60"

            app._start_tac_protocol()
            await pilot.pause()

    asyncio.run(scenario())

    states = JsonProtocolRepository(tmp_path).archives()
    child = next(state for state in states if state.config.mode is ProtocolMode.RAISE_TAC)
    parent = next(state for state in states if state.config.mode is ProtocolMode.WATER_MONITORING)
    assert parent.step is ProtocolStep.COMPLETE
    assert child.parent_archive_name == parent.archive_name


def test_tui_manual_mode_keeps_the_current_working_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app.query_one("#guided-manual-mode", Checkbox).value = True
            await pilot.pause()
            app._open_page("tac")
            app._start_tac_protocol()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tac"

    asyncio.run(scenario())


def test_tui_guided_mode_prepares_the_automatic_acid_lot(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            app.query_one("#new-mode", Select).value = ProtocolMode.LOWER_PH_MONITORING.value
            app.query_one("#new-ph", Input).value = "7.4"
            app.query_one("#new-target-ph", Input).value = "7.2"
            app.query_one("#new-tac", Input).value = "80"
            app._start_protocol()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "guided"
            app._continue_guided()
            await pilot.pause()
            assert "est préparé" in str(app.query_one("#guided-step", Static).render())

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state is not None
    assert state.pending_acid is not None


def test_tui_guided_workflow_chains_ph_tac_ph_until_completion(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            app._start_protocol()
            await pilot.pause()

            app._continue_guided()  # Prépare la première dose NaOH.
            await pilot.pause()
            app._continue_guided()  # Ouvre la mesure de confirmation.
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "6.0"
            app.query_one("#measurement-tac", Input).value = "50"
            app._save_measurement()
            await pilot.pause()
            assert "bicarbonate" in str(app.query_one("#guided-step", Static).render())

            app._continue_guided()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tac"
            app.query_one("#plan-tac", Input).value = "50"
            app._prepare_bicarbonate()
            await pilot.pause()
            app._continue_guided()
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "6.1"
            app.query_one("#measurement-tac", Input).value = "80"
            app._save_measurement()
            await pilot.pause()
            assert "soude" in str(app.query_one("#guided-step", Static).render())

            app._continue_guided()  # Prépare la dernière dose NaOH.
            await pilot.pause()
            app._continue_guided()
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "7.2"
            app.query_one("#measurement-tac", Input).value = "80"
            app._save_measurement()
            await pilot.pause()
            assert "Étape 1" in str(app.query_one("#guided-step", Static).render())

    asyncio.run(scenario())

    archive = JsonProtocolRepository(tmp_path).archives()[0]
    assert archive.step is ProtocolStep.COMPLETE
    assert len(archive.naoh_doses) == 2
    assert len(archive.bicarbonate_doses) == 1


@pytest.mark.parametrize(
    ("choice", "destination"),
    [
        ("measurements", "measurements"),
        ("ph", "protocol"),
        ("tac", "tac"),
        ("disinfection", "treatment"),
    ],
)
def test_tui_guided_workflow_completes_an_acid_correction(
    tmp_path, choice, destination
) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            app.query_one("#new-mode", Select).value = ProtocolMode.LOWER_PH_MONITORING.value
            app.query_one("#new-ph", Input).value = "7.4"
            app.query_one("#new-target-ph", Input).value = "7.2"
            app.query_one("#new-tac", Input).value = "80"
            app._start_protocol()
            await pilot.pause()
            app._continue_guided()  # Prépare l'acide automatiquement.
            await pilot.pause()
            app._continue_guided()  # Ouvre la mesure de confirmation.
            await pilot.pause()
            assert app.focused is app.query_one("#measurement-ph", Input)
            assert not app.query_one(".chlorine-measurement-field", Container).display
            app.query_one("#measurement-ph", Input).value = "7.2"
            app.query_one("#measurement-tac", Input).value = "80"
            app._save_measurement()
            await pilot.pause()
            assert "Étape 1" in str(app.query_one("#guided-step", Static).render())
            button = app.query_one(f"#guided-{choice}", Button)
            button.scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click(button)
            await pilot.pause()
            assert app.query_one(TabbedContent).active == destination
            if choice == "disinfection":
                start = app.query_one("#start-disinfection", Button)
                start.scroll_visible(animate=False)
                await pilot.pause()
                await pilot.click(start)
                await pilot.pause()
                assert app.protocol_service.active().config.mode is ProtocolMode.DISINFECTION_MONITORING

    asyncio.run(scenario())

    archive = next(
        state for state in JsonProtocolRepository(tmp_path).archives()
        if state.config.mode is ProtocolMode.LOWER_PH_MONITORING
    )
    assert archive.step is ProtocolStep.COMPLETE
    assert len(archive.acid_doses) == 1


def test_tui_guided_workflow_keeps_disinfection_in_measurement_only_mode(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("treatment")
            app._start_disinfection_monitoring()
            await pilot.pause()
            app._continue_guided()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "measurements"
            assert app.query_one(".chlorine-measurement-field", Container).display
            app.query_one("#measurement-ph", Input).value = "7.2"
            app.query_one("#measurement-tac", Input).value = "80"
            app.query_one("#measurement-chlorine", Input).value = "2"
            app._save_measurement()
            await pilot.pause()
            assert "chlore libre" in str(app.query_one("#guided-step", Static).render())

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state is not None
    assert state.config.mode is ProtocolMode.DISINFECTION_MONITORING
    assert len(state.water_measurements) == 1
    assert not state.naoh_doses
    assert not state.acid_doses
    assert not state.bicarbonate_doses


def test_tui_top_menu_opens_the_requested_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app.query_one("#menu-protocols", Select).value = "treatment"
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "treatment"

    asyncio.run(scenario())


def test_tui_exposes_the_four_requested_business_entries(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            menu = app.query_one("#menu-protocols", Select)
            assert menu.prompt == "Protocoles"
            assert app.query_one("#dashboard-measurements", Button).label.plain == "Mesurer l’eau"
            assert app.query_one("#dashboard-ph", Button).label.plain == "Corriger le pH"
            assert app.query_one("#dashboard-tac", Button).label.plain == "Corriger le TAC"
            assert app.query_one("#dashboard-disinfection", Button).label.plain == "Désinfection"
            menu.value = "tac"
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "tac"

    asyncio.run(scenario())


def test_tui_uses_the_platform_refresh_shortcut(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            key = "super+r" if platform == "darwin" else "ctrl+r"
            scroll_down_key = "super+down" if platform == "darwin" else "ctrl+down"
            assert app._bindings.key_to_bindings[key][0].action == "refresh"
            assert app._bindings.key_to_bindings[scroll_down_key][0].action == "scroll_page_down"
            assert "r" not in app._bindings.key_to_bindings
            assert "pagedown" not in app._bindings.key_to_bindings

    asyncio.run(scenario())


def test_tui_protocol_page_scrolls_when_its_form_exceeds_the_terminal(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test(size=(100, 24)) as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            await pilot.pause()
            scroll = app.query_one("#protocol-scroll", VerticalScroll)
            assert scroll.virtual_size.height > scroll.size.height
            app.action_scroll_page_down()
            await pilot.pause()
            assert scroll.scroll_y > 0
            scroll.scroll_end(animate=False)
            await pilot.pause()
            button = app.query_one("#start-protocol", Button)
            assert button.region.bottom <= scroll.region.bottom

    asyncio.run(scenario())


def test_tui_adapts_the_ph_form_to_the_selected_product_and_study(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            assert all(widget.display for widget in app.query(".raise-only"))
            assert all(not widget.display for widget in app.query(".lower-only"))

            app.query_one("#new-mode", Select).value = ProtocolMode.LOWER_PH_MONITORING.value
            await pilot.pause()
            assert all(not widget.display for widget in app.query(".raise-only"))
            assert all(widget.display for widget in app.query(".lower-only"))
            assert "acide sulfurique 15 %" in str(
                app.query_one("#new-mode-guidance", Static).render()
            )

            app.query_one(
                "#new-mode", Select
            ).value = ProtocolMode.SODIUM_CARBONATE_ASSESSMENT.value
            await pilot.pause()
            assert all(widget.display for widget in app.query(".carbonate-only"))
            assert "il ne crée jamais de dose" in str(
                app.query_one("#new-mode-guidance", Static).render()
            )

    asyncio.run(scenario())


def test_tui_archives_a_sodium_carbonate_study_without_creating_a_dose(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            app.query_one(
                "#new-mode", Select
            ).value = ProtocolMode.SODIUM_CARBONATE_ASSESSMENT.value
            await pilot.pause()

            assert all(widget.display for widget in app.query(".carbonate-only"))
            assert all(not widget.display for widget in app.query(".raise-only"))
            app.query_one("#new-ph", Input).value = "6.8"
            app.query_one("#new-tac", Input).value = "50"
            app.query_one("#new-target-tac", Input).value = "80"
            app.query_one("#new-carbonate-label", Input).value = "pH+ TUI"
            app.query_one("#new-carbonate-purity", Input).value = "99"
            app.query_one("#new-carbonate-source", Select).value = "fds"
            app._start_protocol()
            await pilot.pause()

            result = str(app.query_one("#carbonate-study-result", Static).render())
            assert "AUCUNE DOSE" in result
            assert "ce n’est pas une dose ni un lot" in result

    asyncio.run(scenario())

    repository = JsonProtocolRepository(tmp_path)
    assert repository.active() is None
    archive = repository.archives()[0]
    assert archive.step is ProtocolStep.COMPLETE
    assert archive.sodium_carbonate_assessment is not None
    assert archive.sodium_carbonate_assessment.product.label == "pH+ TUI"


def test_tui_starts_a_tac_correction_from_its_dedicated_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("tac")
            app._start_tac_protocol()
            await pilot.pause()
            assert "Archive :" in str(app.query_one("#dashboard-status", Static).render())

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state is not None
    assert state.config.mode is ProtocolMode.RAISE_TAC


def test_tui_can_chain_a_new_protocol_from_a_terminal_archive(tmp_path) -> None:
    repository = JsonProtocolRepository(tmp_path)
    parent = ProtocolService(repository).start(
        ProtocolConfig(
            mode=ProtocolMode.SODIUM_CARBONATE_ASSESSMENT,
            initial_ph=6.8,
            initial_tac_ppm=50,
            sodium_carbonate_product={
                "label": "pH+ archive",
                "purity_percent": 99,
                "purity_source": "etiquette",
            },
        )
    , treatment=declared_treatment())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app.query_one("#json-archive", Select).value = parent.archive_name
            app._select_follow_up_archive()
            await pilot.pause()
            assert app.query_one("#tac-ph", Input).value == "6.80"
            assert app.query_one("#tac-initial", Input).value == "50"
            app._open_page("tac")
            app._start_tac_protocol()
            await pilot.pause()

    asyncio.run(scenario())

    child = ProtocolService(repository).active()
    assert child is not None
    assert child.parent_archive_name == parent.archive_name


def test_tui_starts_the_water_monitoring_from_its_dedicated_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("measurements")
            app.query_one("#water-start-ph", Input).value = "7.2"
            app.query_one("#water-target-ph", Input).value = "7.2"
            app.query_one("#water-start-tac", Input).value = "80"
            app._start_water_monitoring()
            await pilot.pause()
            assert "Relevé en cours" in str(
                app.query_one("#measurement-page-intro", Static).render()
            )

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state is not None
    assert state.config.mode is ProtocolMode.WATER_MONITORING


def test_tui_starts_disinfection_management_from_its_dedicated_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("treatment")
            app._start_disinfection_monitoring()
            await pilot.pause()
            assert "saisissez pH, TAC et chlore libre" in str(
                app.query_one("#measurement-instructions", Static).render()
            )

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state is not None
    assert state.config.mode is ProtocolMode.DISINFECTION_MONITORING


def test_tui_prepares_an_acid_lot_from_the_ph_correction_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            app.query_one("#new-mode", Select).value = ProtocolMode.LOWER_PH_MONITORING.value
            app.query_one("#new-ph", Input).value = "7.4"
            app.query_one("#new-target-ph", Input).value = "7.2"
            app.query_one("#new-tac", Input).value = "80"
            app._start_protocol()
            await pilot.pause()
            assert "calculé automatiquement" in str(
                app.query_one("#acid-auto-lot-info", Static).render()
            )
            app._prepare_acid()
            await pilot.pause()

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state is not None
    assert state.pending_acid is not None


def test_tui_allows_copying_a_collapsible_section_title(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("protocol")
            await pilot.pause()
            section = app.query_one(CopyableCollapsible)
            title = section.query_one(CopyableCollapsibleTitle)
            assert title.allow_select

            title.text_select_all()
            await pilot.press("super+c" if platform == "darwin" else "ctrl+c")
            assert app._clipboard == "▼ 1. Ouvrir une correction pH ou une étude (`start`)"

            app.screen.clear_selection()
            await pilot.click(title)
            assert section.collapsed

    asyncio.run(scenario())


def test_tui_reduces_a_protocol_validation_error_to_its_actionable_message() -> None:
    with pytest.raises(ValueError) as captured:
        ProtocolConfig(initial_ph=7.3, intermediate_ph=6.0, target_ph=7.2)

    message = PiscinePhTui._error_message(captured.value)

    assert message == "Les pH doivent respecter : initial < palier < cible."
    assert "input_value" not in message


def test_tui_records_a_high_ph_monitoring_measurement(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(
            mode=ProtocolMode.HIGH_PH_MONITORING,
            initial_ph=7.4,
            target_ph=7.2,
            initial_tac_ppm=80,
        )
    , treatment=declared_treatment())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            assert "saisissez pH, TAC et chlore libre" in str(
                app.query_one("#measurement-instructions", Static).render()
            )
            action = str(app.query_one("#dashboard-action", Static).render())
            assert "Surveillance pH haut" in action
            assert "aucun dosage d’acide ou de chlore" in action
            assert "pH 7.40 au-dessus de la cible 7.20" in action
            app.query_one(TabbedContent).active = "measurements"
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "7.3"
            app.query_one("#measurement-tac", Input).value = "80"
            app.query_one("#measurement-chlorine", Input).value = "3"
            app._save_measurement()
            await pilot.pause()

    asyncio.run(scenario())

    state = service.active()
    assert state.step is ProtocolStep.HIGH_PH_MONITORING
    assert state.water_measurements[-1].free_chlorine_ppm == 3.0


def test_tui_displays_and_copies_the_active_json(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(ProtocolConfig(), treatment=declared_treatment())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            assert app.query_one("#json-archive", Select).value == state.archive_name
            await pilot.click("#guided-view-active-json")
            await pilot.pause()
            assert isinstance(app.screen, JsonViewerScreen)
            summary = app.screen.query_one("#json-summary", Static)
            assert "Dernières mesures" in str(summary.render())
            content = app.screen.query_one("#json-content", Static)
            assert f'"archive_name": "{state.archive_name}"' in str(content.render())

            content.text_select_all()
            await pilot.press("super+c" if platform == "darwin" else "ctrl+c")
            assert f'"archive_name": "{state.archive_name}"' in app._clipboard

    asyncio.run(scenario())


def test_tui_records_the_confirmation_measurement_for_low_ph_correction(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig(), treatment=declared_treatment())
    service.prepare_naoh(50.0)

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            assert "Mesure après NaOH" in str(
                app.query_one("#measurement-instructions", Static).render()
            )
            app.query_one(TabbedContent).active = "measurements"
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "5.0"
            app.query_one("#measurement-tac", Input).value = "50"
            app._save_measurement()
            await pilot.pause()

    asyncio.run(scenario())

    state = service.active()
    assert len(state.naoh_doses) == 1
    assert state.current_ph == 5.0


def test_tui_names_the_active_disinfection_and_each_device(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig(), treatment=declared_treatment())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app.query_one(TabbedContent).active = "treatment"
            await pilot.pause()
            assert app.query_one("#disinfection", Select)
            rendered = "\n".join(str(widget.render()) for widget in app.query(Static))
            assert "Désinfection active" in rendered
            assert "Électrolyseur au sel" in rendered
            assert "Doseur de galets stabilisés" in rendered
            assert "Régulateur de pH" in rendered

    asyncio.run(scenario())


def test_tui_cancels_a_protocol_only_after_confirmation(tmp_path) -> None:
    repository = JsonProtocolRepository(tmp_path)
    service = ProtocolService(repository)
    created = service.start(ProtocolConfig(), treatment=declared_treatment())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            await pilot.click("#guided-cancel-protocol")
            await pilot.pause()
            await pilot.click("#confirm-cancel-protocol")
            await pilot.pause()
            assert "Aucun protocole actif" in str(
                app.query_one("#dashboard-status", Static).render()
            )

    asyncio.run(scenario())

    archived = repository.load(tmp_path / created.archive_name)
    assert archived.step is ProtocolStep.CANCELLED
    assert repository.active() is None


def test_tui_indexes_every_cli_command(tmp_path) -> None:
    commands = (
        "start",
        "status",
        "configure-naoh",
        "treatment",
        "record-tablets",
        "measure-cya",
        "record-water",
        "dose",
        "cancel-dose",
        "cancel-tac-plan",
        "cancel-protocol",
        "correct-last-measurement",
        "measure",
        "plan-tac",
        "measure-tac",
        "menu",
        "tui",
        "history",
        "json",
    )

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            text = str(app.query_one("#command-index", Static).render())
            for command in commands:
                assert command in text

    asyncio.run(scenario())


def test_tui_starts_a_low_ph_protocol_from_its_start_form(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app.query_one(TabbedContent).active = "protocol"
            await pilot.pause()
            app._start_protocol()
            await pilot.pause()
            assert "Archive :" in str(app.query_one("#dashboard-status", Static).render())

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state.config.mode is ProtocolMode.RAISE_PH_TAC


def test_tui_disinfection_bilan_measurement_history_and_follow_up_survive_restart(tmp_path):
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    parent = service.start(ProtocolConfig(
        mode=ProtocolMode.DISINFECTION_MONITORING,
        initial_ph=7.3, initial_tac_ppm=90,
        free_chlorine_min_ppm=2, free_chlorine_max_ppm=5,
    ), treatment=declared_treatment())
    service.record_water_measurement(7.2, 80, 2.5)

    async def scenario():
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._continue_guided()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "treatment"
            assert not app.query_one("#disinfection-start-section").display
            summary = str(app.query_one("#treatment-summary", Static).render())
            for value in ("pH 7.20", "TAC 80", "min 2", "max 5", "2.5 ppm", str(tmp_path)):
                assert value in summary
            button = app.query_one("#treatment-measurements", Button)
            button.scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click(button)
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "measurements"
            assert app.focused is app.query_one("#measurement-ph", Input)
            assert "2.5 ppm" in str(app.query_one("#measurement-log-content", Static).render())
            app.query_one("#measurement-ph", Input).value = "7.1"
            app.query_one("#measurement-tac", Input).value = "80"
            app.query_one("#measurement-chlorine", Input).value = "3"
            app._save_measurement()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "treatment"
            assert "pH 7.10" in str(app.query_one("#treatment-summary", Static).render())
            finish = app.query_one("#complete-disinfection", Button)
            finish.scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click(finish)
            await pilot.pause()
            assert service.repository.active() is None
            assert app.query_one(TabbedContent).active == "guided"
            app._open_page("history")
            await pilot.pause()
            assert "min 2" in str(app.query_one("#archive-summary", Static).render())
            history = str(app.query_one("#archive-measurements", Static).render())
            assert "2.5 ppm" in history and "3 ppm" in history
            app._open_measurement_start()
            app._start_water_monitoring()
            await pilot.pause()
            child = service.active()
            assert child.parent_archive_name == parent.archive_name
            assert child.config.free_chlorine_min_ppm == 2
            assert child.config.free_chlorine_max_ppm == 5

    asyncio.run(scenario())
    saved = service.repository.archive(parent.archive_name)
    assert len(saved.water_measurements) == 2
    assert saved.current_ph == 7.1


def test_tui_disinfection_highlights_recharge_then_requests_a_new_measurement(tmp_path):
    from piscine_ph.models import DisinfectionMethod, StabilizedTabletStatus

    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING),
                  treatment=declared_treatment(
                      disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
                      stabilized_tablet_status=StabilizedTabletStatus.CONSUMED))
    service.record_water_measurement(7.3, 80, 0.5)
    service.record_cyanuric_acid_measurement(20)

    async def scenario():
        app = PiscinePhTui(tmp_path)
        async with app.run_test(size=(100, 40)) as pilot:
            app._continue_guided()
            await pilot.pause()
            title = app.query_one("#disinfection-action-title", Static)
            assert "Chlore trop bas" in str(title.render())
            assert title.region.y < 10
            assert "0.5 ppm" in str(app.query_one("#disinfection-action-detail", Static).render())
            await pilot.click("#open-tablet-recharge")
            await pilot.pause()
            assert app.focused is app.query_one("#tablets-count", Input)
            app.query_one("#tablets-count", Input).value = "2"
            await pilot.click("#record-tablets")
            await pilot.pause()
            assert "Recharge enregistrée" in str(title.render())
            assert "2 galet(s)" in str(app.query_one("#disinfection-action-detail", Static).render())
            assert not app.query_one("#open-tablet-recharge").display
            app.query_one("#disinfection-next-measurement").scroll_visible(animate=False)
            await pilot.pause()
            await pilot.click("#disinfection-next-measurement")
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "measurements"
            assert app.focused is app.query_one("#measurement-ph", Input)

    asyncio.run(scenario())


@pytest.mark.parametrize("chlorine,cya,status,expected", [
    (0.5, 50, "consommes", "ne pas ajouter de galets stabilisés"),
    (0.5, 20, "en_place", "Des galets sont déjà en place"),
    (2, 20, "consommes", "Aucune recharge"),
    (5, 20, "consommes", "ne pas ajouter de chlore"),
])
def test_disinfection_decision_does_not_propose_an_inappropriate_recharge(
    tmp_path, chlorine, cya, status, expected,
):
    from piscine_ph.models import DisinfectionMethod, StabilizedTabletStatus

    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING),
                  treatment=declared_treatment(
                      disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
                      stabilized_tablet_status=StabilizedTabletStatus(status)))
    service.record_water_measurement(7.3, 80, chlorine)
    service.record_cyanuric_acid_measurement(cya)
    action = service.disinfection_action(service.active())
    assert expected in action.label + action.instruction
    assert action.trigger != "record_tablets"


def test_tui_reads_an_archive_with_unmeasured_chlorine(tmp_path):
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig(mode=ProtocolMode.WATER_MONITORING), treatment=declared_treatment())
    state = service.record_water_measurement(7.2, 80)
    app = PiscinePhTui(tmp_path)
    assert "chlore libre non mesuré" in app._json_summary(state)


def test_tui_archive_row_selection_reads_and_keeps_the_selected_values(tmp_path):
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    first = service.start(ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING,
                                       free_chlorine_min_ppm=2, free_chlorine_max_ppm=5), treatment=declared_treatment())
    service.record_water_measurement(7.2, 80, 2.5)
    service.complete_disinfection_monitoring()
    service.start(ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING), treatment=declared_treatment())

    async def scenario():
        from textual.widgets import DataTable

        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            declare_tui_context(app)
            await pilot.pause()
            app._open_page("history")
            await pilot.pause()
            table = app.query_one("#history-table", DataTable)
            table.focus()
            await pilot.press("down", "enter")
            await pilot.pause()
            assert app.query_one("#json-archive", Select).value == first.archive_name
            assert "min 2" in str(app.query_one("#archive-summary", Static).render())
            app.refresh_views()
            await pilot.pause()
            assert app.query_one("#json-archive", Select).value == first.archive_name

    asyncio.run(scenario())


@pytest.mark.parametrize("destination", ["protocol", "tac", "measurements", "treatment"])
def test_tui_requires_installation_first_for_every_new_workflow(tmp_path, destination):
    async def scenario():
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "avant tout protocole" in str(app.query_one("#guided-step", Static).render())
            app.query_one("#menu-protocols", Select).value = destination
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "treatment"
            for selector in ("disinfection", "electrolysis", "ph-regulator", "tablets"):
                assert app.query_one(f"#{selector}", Select).value == "inconnu"
            app._start_disinfection_monitoring()
            assert app.protocol_service.repository.archives() == []
            declare_tui_context(app)
            app._save_treatment()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == (
                destination if destination != "treatment" else "guided"
            )
            starts = {"protocol": app._start_protocol, "tac": app._start_tac_protocol,
                      "measurements": app._start_water_monitoring,
                      "treatment": app._start_disinfection_monitoring}
            starts[destination]()
            await pilot.pause()
            assert app.protocol_service.active().treatment == declared_treatment()

    asyncio.run(scenario())


def test_tui_recovers_an_archived_context_only_after_explicit_save(tmp_path):
    from piscine_ph.models import DisinfectionMethod, StabilizedTabletProduct, TreatmentContext

    service = ProtocolService(JsonProtocolRepository(tmp_path))
    context = declared_treatment(
        disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
        stabilized_tablet_product=StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC,
    )
    parent = service.start(ProtocolConfig(mode=ProtocolMode.WATER_MONITORING), context)
    service.record_water_measurement(7.2, 80, 2)
    service.complete_water_monitoring()
    legacy = service.start(ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING), context)
    legacy.treatment = TreatmentContext()
    service.repository.save(legacy)  # Archive ancienne créée avant le prérequis de contexte.

    async def scenario():
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Contexte incomplet" in str(app.query_one("#guided-step", Static).render())
            app._continue_guided()
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "treatment"
            assert app.focused is app.query_one("#disinfection", Select)
            app._open_page("history")
            app.query_one("#json-archive", Select).value = parent.archive_name
            app._prepare_archived_treatment()
            await pilot.pause()
            assert service.active().treatment == TreatmentContext()
            assert "non encore enregistré" in str(
                app.query_one("#treatment-context-status", Static).render())
            app._save_treatment()
            await pilot.pause()
            assert service.active().treatment == context
            assert app.query_one("#disinfection", Select).value == context.disinfection_method.value
            app.refresh_views()
            assert app.query_one("#electrolysis", Select).value == context.electrolysis_status.value

    asyncio.run(scenario())
    assert service.repository.archive(parent.archive_name).treatment == context
