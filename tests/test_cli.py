"""Tests de consultation non destructive des archives via la CLI."""

from conftest import declared_treatment
from typer.testing import CliRunner

from piscine_ph import cli
from piscine_ph.models import ProtocolConfig, ProtocolMode
from piscine_ph.repository import JsonProtocolRepository
from piscine_ph.service import ProtocolService


def test_json_command_displays_the_active_and_named_archive(tmp_path, monkeypatch) -> None:
    repository = JsonProtocolRepository(tmp_path)
    state = ProtocolService(repository).start(ProtocolConfig(), treatment=declared_treatment())
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


def test_cli_exposes_acid_and_tablet_guidance_commands() -> None:
    result = CliRunner().invoke(cli.app, ["--help"])

    assert result.exit_code == 0
    assert "dose-acid" in result.output
    assert "measure-acid" in result.output
    assert "plan-tablets" in result.output


def test_cli_archives_a_sodium_carbonate_study_without_proposing_a_dose(
    tmp_path, monkeypatch
) -> None:
    repository = JsonProtocolRepository(tmp_path)
    monkeypatch.setattr(cli, "service", lambda: ProtocolService(repository))

    result = CliRunner().invoke(
        cli.app,
        [
            "start",
            "--no-guided",
            "--disinfection", "chlore_non_stabilise",
            "--electrolysis", "non_installe",
            "--ph-regulator", "non_installe",
            "--tablets", "non_necessaires",
            "--mode",
            "etude_carbonate_sodium",
            "--initial-ph",
            "6.8",
            "--initial-tac",
            "50",
            "--carbonate-product-label",
            "pH+ test",
            "--carbonate-purity-percent",
            "99",
            "--carbonate-purity-source",
            "fds",
        ],
    )

    assert result.exit_code == 0
    assert "ETUDE CARBONATE DE SODIUM" in result.output
    assert "ce n'est pas une dose ni un lot" in result.output
    assert repository.active() is None
    archive = repository.archives()[0]
    assert archive.sodium_carbonate_assessment is not None
    assert archive.sodium_carbonate_assessment.product.label == "pH+ test"


def test_cli_links_a_follow_up_without_overwriting_its_new_measurements(tmp_path, monkeypatch) -> None:
    repository = JsonProtocolRepository(tmp_path)
    parent = ProtocolService(repository).start(
        ProtocolConfig(
            mode=ProtocolMode.SODIUM_CARBONATE_ASSESSMENT,
            initial_ph=6.8,
            initial_tac_ppm=50,
            sodium_carbonate_product={
                "label": "pH+ test",
                "purity_percent": 99,
                "purity_source": "fds",
            },
        )
    , treatment=declared_treatment())
    monkeypatch.setattr(cli, "service", lambda: ProtocolService(repository))

    result = CliRunner().invoke(
        cli.app,
        [
            "start",
            "--no-guided",
            "--mode",
            "correction_hausse_tac",
            "--initial-ph",
            "7.1",
            "--initial-tac",
            "60",
            "--follow-up-from",
            parent.archive_name,
        ],
    )

    assert result.exit_code == 0
    child = ProtocolService(repository).active()
    assert child is not None
    assert child.parent_archive_name == parent.archive_name
    assert child.current_ph == 7.1
    assert child.current_tac_ppm == 60


def test_cli_refuses_a_new_protocol_without_its_installation_context(tmp_path, monkeypatch):
    repository = JsonProtocolRepository(tmp_path)
    monkeypatch.setattr(cli, "service", lambda: ProtocolService(repository))
    result = CliRunner().invoke(cli.app, ["start", "--no-guided"])
    assert result.exit_code != 0
    assert "Déclarez d’abord" in result.output
    assert repository.archives() == []


def test_cli_asks_for_installation_before_choosing_a_protocol(tmp_path, monkeypatch):
    repository = JsonProtocolRepository(tmp_path)
    monkeypatch.setattr(cli, "service", lambda: ProtocolService(repository))
    result = CliRunner().invoke(cli.app, ["start"], input="4\n4\n4\n4\n")
    assert result.output.index("TRAITEMENT EN COURS") < result.output.index(
        "Quelle famille de protocole")
    assert repository.archives() == []  # Le questionnaire est interrompu après le contexte.
