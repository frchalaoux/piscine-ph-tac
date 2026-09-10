"""Tests d'intégration légers de l'interface Textual."""

import asyncio
from sys import platform

import pytest
from textual.containers import VerticalScroll
from textual.widgets import Button, Input, Select, Static, TabbedContent

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
            await pilot.pause()
            dashboard = app.query_one("#dashboard-status", Static)
            assert "Aucun protocole actif" in str(dashboard.render())

    asyncio.run(scenario())


def test_tui_top_menu_opens_the_requested_page(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#menu-treatment")
            await pilot.pause()
            assert app.query_one(TabbedContent).active == "treatment"

    asyncio.run(scenario())


def test_tui_uses_the_platform_refresh_shortcut(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
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


def test_tui_adapts_the_protocol_form_to_the_selected_mode(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert all(widget.display for widget in app.query(".raise-only"))
            assert all(not widget.display for widget in app.query(".monitor-only"))

            app.query_one("#new-mode", Select).value = ProtocolMode.HIGH_PH_MONITORING.value
            await pilot.pause()
            assert all(not widget.display for widget in app.query(".raise-only"))
            assert all(widget.display for widget in app.query(".monitor-only"))
            assert "aucune dose ne sera préparée" in str(
                app.query_one("#new-mode-guidance", Static).render()
            )

    asyncio.run(scenario())


def test_tui_allows_copying_a_collapsible_section_title(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app._open_page("protocol")
            await pilot.pause()
            section = app.query_one(CopyableCollapsible)
            title = section.query_one(CopyableCollapsibleTitle)
            assert title.allow_select

            title.text_select_all()
            await pilot.press("super+c" if platform == "darwin" else "ctrl+c")
            assert app._clipboard == "▼ 1. Créer ou reprendre un protocole (`start`)"

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
    )

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert "Surveillance pH haut" in str(
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
    state = service.start(ProtocolConfig())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.query_one("#json-archive", Select).value == state.archive_name
            await pilot.click("#view-active-json")
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
    service.start(ProtocolConfig())
    service.prepare_naoh(50.0)

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
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
    service.start(ProtocolConfig())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
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
    created = service.start(ProtocolConfig())

    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.click("#cancel-protocol")
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
            await pilot.pause()
            text = str(app.query_one("#command-index", Static).render())
            for command in commands:
                assert command in text

    asyncio.run(scenario())


def test_tui_starts_a_low_ph_protocol_from_its_start_form(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one(TabbedContent).active = "protocol"
            await pilot.pause()
            app._start_protocol()
            await pilot.pause()
            assert "Archive :" in str(app.query_one("#dashboard-status", Static).render())

    asyncio.run(scenario())

    state = ProtocolService(JsonProtocolRepository(tmp_path)).active()
    assert state.config.mode is ProtocolMode.RAISE_PH_TAC
