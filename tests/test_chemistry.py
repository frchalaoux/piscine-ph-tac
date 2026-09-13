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


def test_sodium_carbonate_is_excluded_when_tac_is_already_at_target() -> None:
    assessment = ChemistryCalculator().sodium_carbonate_assessment(
        ProtocolConfig(), current_ph=6.8, current_tac_ppm=80, purity_percent=100
    )

    assert assessment.can_be_considered is False
    assert assessment.tac_limited_product_kg == 0
    assert any("TAC est deja" in warning for warning in assessment.warnings)


def test_sodium_carbonate_is_excluded_when_ph_is_already_at_target() -> None:
    assessment = ChemistryCalculator().sodium_carbonate_assessment(
        ProtocolConfig(), current_ph=7.2, current_tac_ppm=50, purity_percent=100
    )

    assert assessment.can_be_considered is False
    assert assessment.tac_limited_product_kg == 0
    assert any("pH est deja" in warning for warning in assessment.warnings)


def test_sodium_carbonate_uses_two_equivalents_and_flags_the_ph_risk() -> None:
    chemistry = ChemistryCalculator()
    assessment = chemistry.sodium_carbonate_assessment(
        ProtocolConfig(), current_ph=6.8, current_tac_ppm=50, purity_percent=100
    )

    assert assessment.can_be_considered is True
    assert assessment.tac_limited_product_kg == pytest.approx(1.462, abs=0.01)
    assert assessment.expected_tac_ppm == 80
    assert assessment.expected_ph_at_tac_limit is not None
    assert assessment.expected_ph_at_tac_limit > 7.2
    assert any("aucun lot carbonate" in warning for warning in assessment.warnings)


def test_sodium_carbonate_purity_changes_product_mass_not_the_closed_model_prediction() -> None:
    chemistry = ChemistryCalculator()
    pure = chemistry.sodium_carbonate_assessment(
        ProtocolConfig(), current_ph=6.8, current_tac_ppm=50, purity_percent=100
    )
    half_pure = chemistry.sodium_carbonate_assessment(
        ProtocolConfig(), current_ph=6.8, current_tac_ppm=50, purity_percent=50
    )

    assert half_pure.tac_limited_product_kg == pytest.approx(pure.tac_limited_product_kg * 2)
    assert half_pure.expected_ph_at_tac_limit == pytest.approx(pure.expected_ph_at_tac_limit)


@pytest.mark.parametrize("purity_percent", [0, -1, 100.1])
def test_sodium_carbonate_requires_a_declared_valid_purity(purity_percent: float) -> None:
    with pytest.raises(ValueError, match="purete"):
        ChemistryCalculator().sodium_carbonate_assessment(
            ProtocolConfig(), current_ph=6.8, current_tac_ppm=50, purity_percent=purity_percent
        )
