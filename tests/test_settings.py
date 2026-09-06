"""Non-régressions du chargement des paramètres opérationnels versionnés."""

import pytest

from piscine_ph.models import NaOHConcentrationSource, ProtocolConfig
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


def test_mass_percent_naoh_declaration_requires_density_and_is_archived_in_config() -> None:
    config = ProtocolConfig(
        naoh_concentration_g_l=399.0,
        naoh_concentration_source=NaOHConcentrationSource.MASS_PERCENT,
        naoh_label_percent=30.0,
        naoh_density_g_ml=1.33,
    )

    assert config.naoh_concentration_g_l == 399.0
    assert config.naoh_concentration_source is NaOHConcentrationSource.MASS_PERCENT

    with pytest.raises(ValueError, match="pourcentage massique exige"):
        ProtocolConfig(
            naoh_concentration_g_l=399.0,
            naoh_concentration_source=NaOHConcentrationSource.MASS_PERCENT,
            naoh_label_percent=30.0,
        )
