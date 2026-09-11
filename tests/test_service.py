"""Non-régressions des transitions et de la persistance du protocole."""

import json

import pytest

from piscine_ph.models import (
    DisinfectionMethod,
    ElectrolysisStatus,
    NaOHConcentrationSource,
    PhRegulatorStatus,
    ProtocolConfig,
    ProtocolMode,
    ProtocolStep,
    StabilizedTabletProduct,
    StabilizedTabletStatus,
    TreatmentContext,
)
from piscine_ph.repository import JsonProtocolRepository
from piscine_ph.service import ProtocolService


def test_service_moves_to_tac_after_intermediate_ph(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig())
    service.prepare_naoh(250)

    state = service.record_naoh_measurement(ph=6.0, tac_ppm=50.0)

    assert state.step is ProtocolStep.TAC_TO_TARGET
    assert state.pending_naoh is None
    assert len(state.naoh_doses) == 1
    assert state.cumulative_additions.naoh_solution_ml == 250
    assert state.cumulative_additions.theoretical_tac_from_naoh_ppm == pytest.approx(2.04, abs=0.05)


def test_service_rejects_tac_not_matching_the_test_resolution(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig())
    service.prepare_naoh(250)

    with pytest.raises(ValueError, match="pas de 10 ppm"):
        service.record_naoh_measurement(ph=5.0, tac_ppm=52.0)


def test_stabilized_chlorine_context_is_journalized_and_warns_on_measurement(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig())
    state = service.set_treatment(ElectrolysisStatus.STOPPED, DisinfectionMethod.STABILIZED_TABLETS)
    state = service.record_stabilized_tablets(2, 200.0, "galets 200 g")
    state = service.record_cyanuric_acid_measurement(55.0)

    assert state.treatment.electrolysis_status is ElectrolysisStatus.STOPPED
    assert state.treatment.stabilized_tablet_status is StabilizedTabletStatus.ACTIVE
    assert state.stabilized_tablets[-1].count == 2
    assert state.cyanuric_acid_measurements[-1].cya_ppm == 55.0
    assert any("CYA mesure a 55 ppm" in warning for warning in service.treatment_warnings(state))

    service.prepare_naoh(50.0)
    state = service.record_naoh_measurement(ph=5.0, tac_ppm=50.0)
    warnings = state.naoh_doses[-1].coherence.warnings
    assert any("prediction de pH est indicative" in warning for warning in warnings)
    assert any("Electrolyse arretee" in warning for warning in warnings)


def test_legacy_treatment_context_migrates_to_one_active_disinfection_method() -> None:
    salt = TreatmentContext.model_validate(
        {"electrolysis_status": "arretee", "chlorine_treatment": "chlore_non_stabilise"}
    )
    tablets = TreatmentContext.model_validate({"chlorine_treatment": "galets_stabilises"})

    assert salt.disinfection_method is DisinfectionMethod.SALT_ELECTROLYSIS
    assert tablets.disinfection_method is DisinfectionMethod.STABILIZED_TABLETS


def test_legacy_protocol_state_is_marked_with_the_current_schema_when_read(tmp_path) -> None:
    repository = JsonProtocolRepository(tmp_path)
    created = ProtocolService(repository).start(ProtocolConfig())
    path = tmp_path / created.archive_name
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["version"] = 3
    payload["treatment"] = {
        "electrolysis_status": "en_marche",
        "chlorine_treatment": "chlore_non_stabilise",
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    migrated = repository.active()

    assert migrated is not None
    assert migrated.version == 6
    assert migrated.treatment.disinfection_method is DisinfectionMethod.SALT_ELECTROLYSIS


def test_supply_estimate_is_persisted_and_accounts_for_stabilized_tablets(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(ProtocolConfig())

    assert state.supply_estimate is not None
    assert state.supply_estimate.bicarbonate_theoretical_kg == pytest.approx(3.86, abs=0.01)
    assert state.supply_estimate.bicarbonate_recommended_kg == 5.0
    assert state.supply_estimate.naoh_solution_recommended_l == 2.0

    state = service.set_treatment(ElectrolysisStatus.STOPPED, DisinfectionMethod.STABILIZED_TABLETS)

    assert state.supply_estimate is not None
    assert state.supply_estimate.bicarbonate_recommended_kg == 6.0
    assert state.supply_estimate.includes_stabilized_chlorine_margin is True


def test_bicarbonate_is_prepared_and_recalculated_one_kg_at_a_time(tmp_path) -> None:
    repository = JsonProtocolRepository(tmp_path)
    service = ProtocolService(repository)
    state = service.start(ProtocolConfig())
    state.step = ProtocolStep.TAC_TO_TARGET
    state.current_ph = 6.0
    state.current_tac_ppm = 30.0
    repository.save(state)

    state = service.plan_bicarbonate(30.0)
    first_lot = state.pending_bicarbonate
    assert first_lot is not None
    assert first_lot.bicarbonate_kg == 1.0
    assert first_lot.bicarbonate_total_kg == pytest.approx(3.86, abs=0.01)

    state = service.record_bicarbonate_measurement(ph=6.1, tac_ppm=40.0)
    assert state.step is ProtocolStep.TAC_TO_TARGET
    assert state.bicarbonate_doses[-1].bicarbonate_kg == 1.0

    state = service.plan_bicarbonate(40.0)
    next_lot = state.pending_bicarbonate
    assert next_lot is not None
    assert next_lot.bicarbonate_kg == 1.0
    assert next_lot.bicarbonate_total_kg == pytest.approx(3.09, abs=0.01)


def test_start_reuses_existing_active_protocol(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    created = service.start(ProtocolConfig())

    resumed = service.start(ProtocolConfig())

    assert resumed.archive_name == created.archive_name


def test_naoh_concentration_can_be_corrected_for_an_active_protocol(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig())
    service.prepare_naoh(250)
    service.record_naoh_measurement(ph=5.0, tac_ppm=50.0)

    state = service.set_naoh_concentration(
        399.0,
        NaOHConcentrationSource.MASS_PERCENT,
        label_percent=30.0,
        density_g_ml=1.33,
    )

    assert state.config.naoh_concentration_g_l == 399.0
    assert state.config.naoh_concentration_source is NaOHConcentrationSource.MASS_PERCENT
    assert state.cumulative_additions.naoh_solution_ml == 250.0
    assert state.cumulative_additions.naoh_moles == pytest.approx(2.494, abs=0.001)
    assert "300 vers 399 g/L" in state.journal[-1].event


def test_naoh_concentration_cannot_change_while_a_dose_is_pending(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig())
    service.prepare_naoh(250)

    with pytest.raises(ValueError, match="dose de NaOH en attente"):
        service.set_naoh_concentration(399.0, NaOHConcentrationSource.GRAMS_PER_LITRE)


def test_repository_recreates_missing_data_directory(tmp_path) -> None:
    """Un clone sans journaux opérationnels peut démarrer sans préparation manuelle."""
    root = tmp_path / "data" / "protocoles"

    repository = JsonProtocolRepository(root)

    assert root.is_dir()
    assert repository.active() is None


def test_cancel_pending_naoh_preserves_last_measurements(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    created = service.start(ProtocolConfig())
    service.prepare_naoh(250)

    state = service.cancel_pending_naoh()

    assert state.pending_naoh is None
    assert state.current_ph == created.current_ph
    assert state.current_tac_ppm == created.current_tac_ppm
    assert "annulee avant ajout" in state.journal[-1].event


def test_cancel_protocol_archives_it_and_removes_it_from_active_state(tmp_path) -> None:
    repository = JsonProtocolRepository(tmp_path)
    service = ProtocolService(repository)
    service.start(ProtocolConfig())

    cancelled = service.cancel_protocol()

    assert cancelled.step is ProtocolStep.CANCELLED
    assert repository.active() is None


def test_correct_last_measurement_restores_the_appropriate_step(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(ProtocolConfig())
    service.prepare_naoh(250)
    service.record_naoh_measurement(ph=6.0, tac_ppm=50.0)

    corrected = service.correct_last_measurement(ph=5.5, tac_ppm=50.0)

    assert corrected.step is ProtocolStep.PH_TO_INTERMEDIATE
    assert corrected.current_ph == 5.5
    assert corrected.cumulative_additions.naoh_solution_ml == 250.0


def test_legacy_json_is_archived_without_deleting_it(tmp_path) -> None:
    legacy_path = tmp_path / "suivi_protocole_naoh_tac.json"
    legacy_path.write_text(
        json.dumps(
            {
                "etape": "termine",
                "volume_m3": 46,
                "ph_depart": 4.1,
                "ph_palier": 6.0,
                "ph_final": 7.2,
                "tac_initial_ppm": 50,
                "seau_l": 10,
                "ph_actuel": 7.2,
                "journal": [{"evenement": "Ancien evenement"}],
            }
        ),
        encoding="utf-8",
    )
    repository = JsonProtocolRepository(tmp_path / "suivis_protocoles")

    archives = repository.archives()

    assert legacy_path.exists()
    assert len(archives) == 1
    assert archives[0].step is ProtocolStep.COMPLETE
    assert archives[0].protocol_id.startswith("legacy:")


def test_high_ph_monitoring_archives_low_chlorine_and_stopped_equipment(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(
        ProtocolConfig(
            mode=ProtocolMode.HIGH_PH_MONITORING,
            initial_ph=7.6,
            target_ph=7.2,
            initial_tac_ppm=70,
            free_chlorine_min_ppm=1.0,
            free_chlorine_max_ppm=4.0,
        ),
        TreatmentContext(
            electrolysis_status=ElectrolysisStatus.STOPPED,
            disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
            ph_regulator_status=PhRegulatorStatus.STOPPED,
            stabilized_tablet_status=StabilizedTabletStatus.CONSUMED,
        ),
    )

    assert state.step is ProtocolStep.HIGH_PH_MONITORING
    assert state.supply_estimate is None

    state = service.record_water_measurement(ph=7.6, tac_ppm=70, free_chlorine_ppm=0.5)
    actions = service.water_actions(state)

    assert len(state.water_measurements) == 1
    assert any("sous la borne basse 1.0 ppm" in action for action in actions)
    assert any("TAC mesure 70 ppm" in action for action in actions)
    assert any("Electrolyse arretee" in action for action in actions)
    assert any("Galets declares consommes" in action for action in actions)
    assert any("Conclusion de surveillance : Decision pH" in event.event for event in state.journal)
    assert any("Conclusion de surveillance : Decision chlore" in event.event for event in state.journal)
    with pytest.raises(ValueError, match="soude n'est pas l'etape active"):
        service.prepare_naoh()


def test_high_ph_monitoring_flags_chlorine_above_the_declared_maximum(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(
            mode=ProtocolMode.HIGH_PH_MONITORING,
            initial_ph=7.4,
            target_ph=7.2,
            initial_tac_ppm=80,
            free_chlorine_min_ppm=1.0,
            free_chlorine_max_ppm=4.0,
        ),
        TreatmentContext(
            disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
            stabilized_tablet_status=StabilizedTabletStatus.ACTIVE,
        ),
    )

    state = service.record_water_measurement(ph=7.9, tac_ppm=80, free_chlorine_ppm=11.0)
    actions = service.water_actions(state)

    assert any("au-dessus de la borne haute declaree" in action for action in actions)
    assert any("ne pas ajouter de chlore" in action for action in actions)
    assert any("test DPD" in action for action in actions)


def test_high_ph_monitoring_records_when_measurements_need_no_correction(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(
            mode=ProtocolMode.HIGH_PH_MONITORING,
            initial_ph=7.4,
            target_ph=7.2,
            initial_tac_ppm=80,
            free_chlorine_min_ppm=1.0,
            free_chlorine_max_ppm=4.0,
        )
    )

    state = service.record_water_measurement(ph=7.2, tac_ppm=80, free_chlorine_ppm=3.0)

    conclusions = [event.event for event in state.journal if event.event.startswith("Conclusion")]
    assert any("Aucune correction de pH n'est a effectuer" in conclusion for conclusion in conclusions)
    assert any("Aucune action de desinfection n'est a effectuer" in conclusion for conclusion in conclusions)


def test_tac_only_protocol_starts_at_tac_and_ends_after_confirmation(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(
        ProtocolConfig(
            mode=ProtocolMode.RAISE_TAC,
            initial_tac_ppm=60,
            target_tac_ppm=80,
        )
    )

    assert state.step is ProtocolStep.TAC_TO_TARGET

    state = service.plan_bicarbonate(60)
    state = service.record_bicarbonate_measurement(ph=7.2, tac_ppm=80)

    assert state.step is ProtocolStep.COMPLETE
    assert any("protocole de correction TAC termine" in event.event for event in state.journal)


def test_lower_ph_protocol_reserves_water_measurements_for_the_acid_cycle(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(
            mode=ProtocolMode.LOWER_PH_MONITORING,
            initial_ph=7.6,
            target_ph=7.2,
        )
    )

    with pytest.raises(ValueError, match="reservee aux protocoles de surveillance"):
        service.record_water_measurement(ph=7.6, tac_ppm=80)


def test_disinfection_protocol_requires_chlorine_and_warns_for_trichlor(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(
        ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING),
        TreatmentContext(
            disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
            stabilized_tablet_product=StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC,
        ),
    )

    with pytest.raises(ValueError, match="chlore libre est requis"):
        service.record_water_measurement(ph=7.2, tac_ppm=80)

    state = service.record_water_measurement(ph=7.2, tac_ppm=80, free_chlorine_ppm=2.0)

    assert any("GCCHLLEC" in warning for warning in service.treatment_warnings(state))


def test_sulfuric_acid_protocol_limits_a_batch_and_requires_measurement(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(
        ProtocolConfig(
            mode=ProtocolMode.LOWER_PH_MONITORING,
            pool_volume_m3=46,
            initial_ph=7.5,
            target_ph=7.2,
            initial_tac_ppm=80,
        )
    )

    assert state.step is ProtocolStep.ACID_TO_TARGET
    with pytest.raises(ValueError, match="ne peut pas exceder"):
        service.prepare_sulfuric_acid(346)
    state = service.prepare_sulfuric_acid()

    assert state.pending_acid is not None
    assert state.pending_acid.acid_ml == pytest.approx(345)

    state = service.record_sulfuric_acid_measurement(ph=7.4, tac_ppm=80)

    assert state.step is ProtocolStep.ACID_TO_TARGET
    assert state.cumulative_additions.sulfuric_acid_15_ml == pytest.approx(345)
    assert ProtocolService.next_command(state) == "piscine-ph dose-acid"


def test_lower_ph_protocol_never_requests_a_chlorine_measurement(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    state = service.start(
        ProtocolConfig(
            mode=ProtocolMode.LOWER_PH_MONITORING,
            initial_ph=7.5,
            target_ph=7.2,
            initial_tac_ppm=80,
        )
    )

    assert not any("chlore libre" in action for action in service.water_actions(state))


def test_sulfuric_acid_is_blocked_by_an_active_regulator_or_active_tablets(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    config = ProtocolConfig(
        mode=ProtocolMode.LOWER_PH_MONITORING,
        initial_ph=7.4,
        target_ph=7.2,
        initial_tac_ppm=80,
    )
    service.start(config, TreatmentContext(ph_regulator_status=PhRegulatorStatus.RUNNING))

    with pytest.raises(ValueError, match="regulateur pH"):
        service.prepare_sulfuric_acid()

    service.start(
        config,
        TreatmentContext(
            disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
            stabilized_tablet_status=StabilizedTabletStatus.ACTIVE,
        ),
        replace_active=True,
    )

    with pytest.raises(ValueError, match="galets au trichlore"):
        service.prepare_sulfuric_acid()


def test_last_acid_measurement_can_be_corrected_without_changing_the_dose(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(
            mode=ProtocolMode.LOWER_PH_MONITORING,
            pool_volume_m3=20,
            initial_ph=7.4,
            target_ph=7.2,
            initial_tac_ppm=80,
        )
    )
    service.prepare_sulfuric_acid()
    service.record_sulfuric_acid_measurement(ph=7.3, tac_ppm=80)

    state = service.correct_last_measurement(ph=7.2, tac_ppm=80)

    assert state.step is ProtocolStep.COMPLETE
    assert state.acid_doses[-1].acid_ml == pytest.approx(150)
    assert state.acid_doses[-1].ph_after == pytest.approx(7.2)
    assert state.cumulative_additions.sulfuric_acid_15_ml == pytest.approx(150)


def test_tablet_guidance_uses_the_slow_trichlor_label_after_low_chlorine_measurement(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING, pool_volume_m3=46),
        TreatmentContext(
            disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
            stabilized_tablet_product=StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC,
        ),
    )
    service.record_water_measurement(ph=7.2, tac_ppm=80, free_chlorine_ppm=0.2)

    _, count, ratio = service.tablet_guidance()

    assert count == 2
    assert ratio == 25
    assert ProtocolService.next_command(service.active()) == "piscine-ph plan-tablets"


def test_tablet_guidance_refuses_a_high_cya(tmp_path) -> None:
    service = ProtocolService(JsonProtocolRepository(tmp_path))
    service.start(
        ProtocolConfig(mode=ProtocolMode.DISINFECTION_MONITORING),
        TreatmentContext(
            disinfection_method=DisinfectionMethod.STABILIZED_TABLETS,
            stabilized_tablet_product=StabilizedTabletProduct.TRICHLOR_SLOW_GCCHLLEC,
        ),
    )
    service.record_water_measurement(ph=7.2, tac_ppm=80, free_chlorine_ppm=0.2)
    service.record_cyanuric_acid_measurement(50)

    with pytest.raises(ValueError, match="CYA a 50 ppm"):
        service.tablet_guidance()
