"""Non-régressions du chargement des paramètres opérationnels versionnés."""

from piscine_ph.models import ProtocolConfig
from piscine_ph.settings import SETTINGS


def test_protocol_config_uses_validated_json_defaults() -> None:
    """Les valeurs implicites du modèle proviennent du fichier defaults.json validé."""
    config = ProtocolConfig()

    assert config.pool_volume_m3 == SETTINGS.protocol.pool_volume_m3
    assert config.target_tac_ppm == SETTINGS.protocol.target_tac_ppm
    assert config.naoh_concentration_g_l == SETTINGS.protocol.naoh_concentration_g_l


def test_naoh_thresholds_are_ordered() -> None:
    """Les trois portions NaOH restent sélectionnables dans le bon ordre."""
    assert SETTINGS.workflow.naoh_medium_gap_ph < SETTINGS.workflow.naoh_large_gap_ph
