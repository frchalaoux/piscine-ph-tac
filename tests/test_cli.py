"""Tests de consultation non destructive des archives via la CLI."""

from typer.testing import CliRunner

from piscine_ph import cli
from piscine_ph.models import ProtocolConfig
from piscine_ph.repository import JsonProtocolRepository
from piscine_ph.service import ProtocolService


def test_json_command_displays_the_active_and_named_archive(tmp_path, monkeypatch) -> None:
    repository = JsonProtocolRepository(tmp_path)
    state = ProtocolService(repository).start(ProtocolConfig())
    monkeypatch.setattr(cli, "service", lambda: ProtocolService(repository))
    runner = CliRunner()

    active = runner.invoke(cli.app, ["json"])
    named = runner.invoke(cli.app, ["json", state.archive_name])

    assert active.exit_code == 0
    assert named.exit_code == 0
    assert active.output == named.output
    assert f'"archive_name": "{state.archive_name}"' in active.output


def test_json_command_rejects_an_unknown_archive(tmp_path, monkeypatch) -> None:
    repository = JsonProtocolRepository(tmp_path)
    monkeypatch.setattr(cli, "service", lambda: ProtocolService(repository))

    result = CliRunner().invoke(cli.app, ["json", "absent.json"])

    assert result.exit_code == 1
    assert "Archive introuvable" in result.output


def test_protocols_command_lists_the_three_families_and_safety_limit() -> None:
    result = CliRunner().invoke(cli.app, ["protocols"])

    assert result.exit_code == 0
    assert "Correction pH" in result.output
    assert "Correction TAC" in result.output
    assert "Desinfectant" in result.output
    assert "ne jamais melanger acide et galets au trichlore" in result.output
