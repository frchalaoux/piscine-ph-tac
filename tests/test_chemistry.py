"""Non-régressions des conversions chimiques et des limites du modèle carbonate."""

import pytest

from piscine_ph.chemistry import ChemistryCalculator
from piscine_ph.models import ProtocolConfig


def test_bicarbonate_to_raise_tac_from_50_to_80_ppm() -> None:
    chemistry = ChemistryCalculator()
    config = ProtocolConfig()

    assert chemistry.bicarbonate_kg(config, 50) == pytest.approx(2.316, abs=0.01)


def test_250_ml_of_naoh_raises_theoretical_tac_by_about_2_ppm() -> None:
    chemistry = ChemistryCalculator()
    config = ProtocolConfig()
    check = chemistry.verify(
        config,
        ph_before=7.0,
        tac_before_ppm=50,
        ph_after=7.0,
        tac_after_ppm=52.04,
        naoh_ml=250,
    )

    assert check.expected_tac_ppm == pytest.approx(52.04, abs=0.05)


def test_bucket_keeps_freeboard() -> None:
    chemistry = ChemistryCalculator()
    preparation = chemistry.prepare_bucket(ProtocolConfig(), 250)

    assert preparation.useful_volume_l == 8.0
    assert preparation.water_l == 7.75


def test_does_not_predict_ph_when_initial_carbon_model_is_invalid() -> None:
    chemistry = ChemistryCalculator()
    check = chemistry.verify(
        ProtocolConfig(),
        ph_before=4.1,
        tac_before_ppm=50,
        ph_after=4.5,
        tac_after_ppm=50,
        naoh_ml=250,
    )

    assert check.expected_ph is None
    assert check.ph_difference is None
    assert any("ne peut pas predire" in warning for warning in check.warnings)
