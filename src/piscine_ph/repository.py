"""Archivage JSON atomique, lecture et migration des protocoles.

Le dépôt ne décide jamais d'une transition métier : il persiste un
``ProtocolState`` par archive et sélectionne l'archive la plus récente active.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .models import JournalEvent, ProtocolConfig, ProtocolState, ProtocolStep


class JsonProtocolRepository:
    """Gère les archives datées sous un répertoire de données donné."""

    def __init__(self, root: Path | str = "data/protocoles") -> None:
        """Initialise le dépôt et recrée le répertoire de données s'il manque.

        Ainsi, un clone GitHub — qui ne contient pas les journaux ignorés — est
        immédiatement prêt à recevoir sa première archive.
        """
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def create_path(self) -> Path:
        """Réserve un chemin daté non existant, avec suffixe si nécessaire."""
        self.root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
        candidate = self.root / f"protocole_{stamp}.json"
        index = 2
        while candidate.exists():
            candidate = self.root / f"protocole_{stamp}_{index}.json"
            index += 1
        return candidate

    def save(self, state: ProtocolState) -> Path:
        """Sérialise ``state`` de façon atomique et retourne son chemin d'archive."""
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / state.archive_name
        temporary = path.with_suffix(".tmp")
        temporary.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
        return path

    def load(self, path: Path) -> ProtocolState:
        """Charge et valide une archive JSON Pydantic depuis ``path``."""
        return ProtocolState.model_validate_json(path.read_text(encoding="utf-8"))

    def active(self) -> ProtocolState | None:
        """Retourne l'archive active la plus récente ou ``None`` si elle n'existe pas."""
        self._migrate_legacy_if_needed()
        if not self.root.exists():
            return None
        for path in sorted(self.root.glob("protocole_*.json"), reverse=True):
            try:
                state = self.load(path)
            except (OSError, json.JSONDecodeError, ValueError):
                # Une archive illisible ne doit pas empêcher la reprise d'une
                # archive valide plus ancienne ; elle reste intacte sur disque.
                continue
            if state.step not in {ProtocolStep.COMPLETE, ProtocolStep.CANCELLED}:
                return state
        return None

    def archives(self) -> list[ProtocolState]:
        """Retourne les archives lisibles de la plus récente à la plus ancienne."""
        self._migrate_legacy_if_needed()
        if not self.root.exists():
            return []
        states: list[ProtocolState] = []
        for path in sorted(self.root.glob("protocole_*.json"), reverse=True):
            try:
                states.append(self.load(path))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
        return states

    def _migrate_legacy_if_needed(self) -> None:
        """Archive une fois le suivi historique sans supprimer sa source.

        L'identifiant ``legacy:...`` enregistré dans l'archive évite une seconde
        importation du même fichier ancien.
        """
        legacy_paths = (
            self.root.parent / "suivi_protocole_naoh_tac.json",
            self.root.parent.parent / "suivi_protocole_naoh_tac.json",
        )
        legacy_path = next((path for path in legacy_paths if path.exists()), None)
        if legacy_path is None:
            return
        legacy_id = f"legacy:{legacy_path.name}"
        if self.root.exists():
            for path in self.root.glob("protocole_*.json"):
                try:
                    if self.load(path).protocol_id == legacy_id:
                        return
                except (OSError, json.JSONDecodeError, ValueError):
                    continue
        try:
            legacy = json.loads(legacy_path.read_text(encoding="utf-8"))
            defaults = ProtocolConfig()
            config = ProtocolConfig(
                pool_volume_m3=legacy.get("volume_m3", defaults.pool_volume_m3),
                initial_ph=legacy.get("ph_depart", defaults.initial_ph),
                intermediate_ph=legacy.get("ph_palier", defaults.intermediate_ph),
                target_ph=legacy.get("ph_final", defaults.target_ph),
                initial_tac_ppm=legacy.get("tac_initial_ppm", defaults.initial_tac_ppm),
                bucket_volume_l=legacy.get("seau_l", defaults.bucket_volume_l),
            )
        except (OSError, json.JSONDecodeError, ValueError):
            return
        step_by_name = {
            "naoh_vers_palier": ProtocolStep.PH_TO_INTERMEDIATE,
            "tac_vers_80": ProtocolStep.TAC_TO_TARGET,
            "naoh_final": ProtocolStep.PH_TO_TARGET,
            "termine": ProtocolStep.COMPLETE,
        }
        after_bicarbonate = legacy.get("apres_bicarbonate", {})
        archive = self.create_path()
        state = ProtocolState(
            protocol_id=legacy_id,
            archive_name=archive.name,
            config=config,
            step=step_by_name.get(legacy.get("etape"), ProtocolStep.PH_TO_INTERMEDIATE),
            current_ph=legacy.get("ph_actuel", config.initial_ph),
            current_tac_ppm=after_bicarbonate.get("tac_ppm", config.initial_tac_ppm),
            journal=[
                JournalEvent(event=event.get("evenement", "Evenement ancien non detaille"))
                for event in legacy.get("journal", [])
            ],
        )
        state.add_event("Ancien suivi JSON migre ; le fichier original est conserve.")
        self.save(state)
