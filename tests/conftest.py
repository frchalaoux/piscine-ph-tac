"""Contexte explicitement déclaré pour les scénarios métier existants."""

from textual.widgets import Select

from piscine_ph.models import (
    DisinfectionMethod,
    ElectrolysisStatus,
    PhRegulatorStatus,
    StabilizedTabletStatus,
    TreatmentContext,
)


def declared_treatment(**overrides):
    values = {
        "disinfection_method": DisinfectionMethod.UNSTABILIZED_CHLORINE,
        "electrolysis_status": ElectrolysisStatus.STOPPED,
        "ph_regulator_status": PhRegulatorStatus.STOPPED,
        "stabilized_tablet_status": StabilizedTabletStatus.NOT_NEEDED,
    }
    values.update(overrides)
    return TreatmentContext(**values)


def declare_tui_context(app):
    """Renseigne les champs inconnus, sans remplacer un contexte déjà fourni."""
    for selector, value in (
        ("disinfection", DisinfectionMethod.UNSTABILIZED_CHLORINE),
        ("electrolysis", ElectrolysisStatus.STOPPED),
        ("ph-regulator", PhRegulatorStatus.STOPPED),
        ("tablets", StabilizedTabletStatus.NOT_NEEDED),
    ):
        widget = app.query_one(f"#{selector}", Select)
        if widget.value == "inconnu":
            widget.value = value.value
    app.refresh_views()
