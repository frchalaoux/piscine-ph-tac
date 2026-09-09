"""Tests d'intégration légers de l'interface Textual."""

import asyncio

from textual.widgets import Input, Static, TabbedContent

from piscine_ph.models import ProtocolConfig, ProtocolMode, ProtocolStep
from piscine_ph.repository import JsonProtocolRepository
from piscine_ph.service import ProtocolService
from piscine_ph.tui import PiscinePhTui


def test_tui_explains_how_to_create_a_protocol_when_none_is_active(tmp_path) -> None:
    async def scenario() -> None:
        app = PiscinePhTui(tmp_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            dashboard = app.query_one("#dashboard-status", Static)
            assert "Aucun protocole actif" in str(dashboard.render())

    asyncio.run(scenario())


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
            app.query_one(TabbedContent).active = "measurements"
            await pilot.pause()
            app.query_one("#measurement-ph", Input).value = "7.3"
            app.query_one("#measurement-tac", Input).value = "80"
            app.query_one("#measurement-chlorine", Input).value = "3"
            await pilot.click("#save-measurement")
            await pilot.pause()

    asyncio.run(scenario())

    state = service.active()
    assert state.step is ProtocolStep.HIGH_PH_MONITORING
    assert state.water_measurements[-1].free_chlorine_ppm == 3.0
