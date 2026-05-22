"""
StatePersistence — atomic, corruption-safe save/load for Helios state files.

Handles personality, allostasis, and (future) memory state persistence with:
  · Atomic writes via tempfile + os.replace (no partial writes on crash)
  · Corruption-safe reads (JSONDecodeError, KeyError, FileNotFoundError → None + log)
  · Version-stamped JSON format for forward compatibility

File: utils/persistence.py
"""

import json
import logging
import os
import tempfile
import time
from typing import Optional

logger = logging.getLogger(__name__)


class StatePersistence:
    """
    Handles save/load for personality, allostasis, and memory states.

    All writes use the atomic pattern: write to a tempfile in the same directory,
    then os.replace() onto the target path. This guarantees that readers always
    see either the old complete file or the new complete file — never a partial write.

    All reads handle corruption gracefully: JSONDecodeError, KeyError, and
    FileNotFoundError return None (or empty dict) and log a warning.
    """

    def __init__(self, data_dir: str):
        self._data_dir = data_dir
        os.makedirs(self._data_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _path(self, filename: str) -> str:
        """Resolve a filename relative to the data directory."""
        return os.path.join(self._data_dir, filename)

    def _atomic_write(self, filepath: str, data: dict) -> None:
        """
        Write JSON data atomically using tempfile + os.replace.

        The tempfile is created in the same directory as the target so that
        os.replace() is guaranteed to be atomic (same filesystem).
        """
        dir_name = os.path.dirname(filepath)
        os.makedirs(dir_name, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            suffix=".tmp",
            prefix=".helios_",
            dir=dir_name,
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, filepath)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    def _safe_load(self, filepath: str) -> Optional[dict]:
        """
        Load JSON from filepath with corruption safety.

        Returns:
            Parsed dict on success, None on any failure (missing, corrupt, etc.)
        """
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                logger.warning(
                    "Persistence file %s contains non-dict root; ignoring.", filepath
                )
                return None
            return data
        except FileNotFoundError:
            # Expected on first run — no warning needed
            return None
        except json.JSONDecodeError as e:
            logger.warning(
                "Persistence file %s is corrupted (JSONDecodeError: %s); "
                "will use defaults.",
                filepath,
                e,
            )
            return None
        except (OSError, IOError) as e:
            logger.warning(
                "Cannot read persistence file %s (%s); will use defaults.",
                filepath,
                e,
            )
            return None

    # ------------------------------------------------------------------
    # Personality persistence
    # ------------------------------------------------------------------

    def save_personality(self, profile) -> None:
        """
        Save PersonalityProfile to data/personality.json.

        Stores Big Five traits, neuro_gains, and evolution history length
        with a version stamp for forward compatibility.
        """
        data = {
            "version": 1,
            "timestamp": time.time(),
            "traits": {
                "openness": profile.openness,
                "extraversion": profile.extraversion,
                "agreeableness": profile.agreeableness,
                "neuroticism": profile.neuroticism,
                "conscientiousness": profile.conscientiousness,
            },
            "neuro_gains": profile.neuro_gains,
            "total_emotion_cycles": profile.total_emotion_cycles,
            "evolution_history_len": len(profile.trait_history),
        }
        filepath = self._path("personality.json")
        self._atomic_write(filepath, data)
        logger.debug("Saved personality state to %s", filepath)

    def load_personality(self) -> Optional[dict]:
        """
        Load personality state from data/personality.json.

        Returns:
            Dict with keys: traits, neuro_gains, total_emotion_cycles
            on success. None if file is missing or corrupted.
        """
        filepath = self._path("personality.json")
        data = self._safe_load(filepath)
        if data is None:
            return None

        # Validate required keys
        try:
            traits = data["traits"]
            # Ensure all Big Five traits are present
            required_traits = [
                "openness",
                "extraversion",
                "agreeableness",
                "neuroticism",
                "conscientiousness",
            ]
            for trait in required_traits:
                if trait not in traits:
                    raise KeyError(f"Missing trait: {trait}")
            return data
        except KeyError as e:
            logger.warning(
                "Personality file %s has invalid structure (missing key: %s); "
                "will use defaults.",
                filepath,
                e,
            )
            return None

    # ------------------------------------------------------------------
    # Allostasis persistence
    # ------------------------------------------------------------------

    def save_allostasis(self, regulator) -> None:
        """
        Save AllostasisRegulator state to data/allostasis.json.

        Stores allostatic load, setpoints for each system, and fatigue status.
        """
        setpoints = {}
        for sys_name, state in regulator.states.items():
            setpoints[sys_name] = round(state.setpoint, 6)

        data = {
            "version": 1,
            "timestamp": time.time(),
            "allostatic_load": round(regulator.get_load_level(), 6),
            "setpoints": setpoints,
            "is_fatigued": regulator.is_fatigued(),
            "fatigue_cycles": regulator.fatigue_cycles,
            "recovery_cycles": regulator.recovery_cycles,
            "total_cycles": regulator.total_cycles,
        }
        filepath = self._path("allostasis.json")
        self._atomic_write(filepath, data)
        logger.debug("Saved allostasis state to %s", filepath)

    def load_allostasis(self) -> Optional[dict]:
        """
        Load allostasis state from data/allostasis.json.

        Returns:
            Dict with keys: allostatic_load, setpoints, is_fatigued, etc.
            on success. None if file is missing or corrupted.
        """
        filepath = self._path("allostasis.json")
        data = self._safe_load(filepath)
        if data is None:
            return None

        # Validate required keys
        try:
            _ = data["allostatic_load"]
            setpoints = data["setpoints"]
            if not isinstance(setpoints, dict):
                raise KeyError("setpoints must be a dict")
            return data
        except KeyError as e:
            logger.warning(
                "Allostasis file %s has invalid structure (missing key: %s); "
                "will use defaults.",
                filepath,
                e,
            )
            return None

    # ------------------------------------------------------------------
    # Memory system persistence
    # ------------------------------------------------------------------

    def save_memory_state(self, memory_system) -> None:
        """
        Save Memory System state to disk.

        Serializes:
        - SemanticMemory facts → data/semantic_memory.json
        - EpisodicMemory items with importance > 0.3 → data/episodic_memory.json

        Requirements: 22.1, 22.3
        """
        self._save_semantic_memory(memory_system.semantic)
        self._save_episodic_memory(memory_system.episodic)

    def load_memory_state(self) -> dict:
        """
        Load saved memory state from disk.

        Returns:
            Dict with keys:
            - "semantic_facts": list of fact dicts (or empty list on failure)
            - "episodic_items": list of episodic item dicts (or empty list on failure)

        On corruption or missing files, returns empty lists and logs a warning.

        Requirements: 22.2, 22.4, 22.5
        """
        return {
            "semantic_facts": self._load_semantic_memory(),
            "episodic_items": self._load_episodic_memory(),
        }

    def _save_semantic_memory(self, semantic) -> None:
        """
        Serialize SemanticMemory facts to data/semantic_memory.json.

        Each fact is stored with its key, value, confidence, last_accessed,
        access_count, and tags for full reconstruction on load.
        """
        facts_list = []
        for key, item in semantic.facts.items():
            facts_list.append({
                "key": key,
                "value": item.content.get("value"),
                "confidence": item.content.get("confidence", 0.5),
                "last_accessed": item.last_accessed,
                "access_count": item.access_count,
                "tags": list(item.tags),
            })

        data = {
            "version": 1,
            "timestamp": time.time(),
            "facts": facts_list,
        }
        filepath = self._path("semantic_memory.json")
        self._atomic_write(filepath, data)
        logger.debug("Saved semantic memory (%d facts) to %s", len(facts_list), filepath)

    def _load_semantic_memory(self) -> list:
        """
        Load SemanticMemory facts from data/semantic_memory.json.

        Returns:
            List of fact dicts on success, empty list on failure/missing.
        """
        filepath = self._path("semantic_memory.json")
        data = self._safe_load(filepath)
        if data is None:
            return []

        try:
            facts = data["facts"]
            if not isinstance(facts, list):
                raise KeyError("facts must be a list")
            # Validate each fact has required fields
            for fact in facts:
                if not isinstance(fact, dict):
                    raise KeyError("each fact must be a dict")
                if "key" not in fact:
                    raise KeyError("fact missing 'key' field")
            return facts
        except KeyError as e:
            logger.warning(
                "Semantic memory file %s has invalid structure (%s); "
                "will initialize empty.",
                filepath,
                e,
            )
            return []

    def _save_episodic_memory(self, episodic) -> None:
        """
        Serialize EpisodicMemory items with importance > 0.3 to
        data/episodic_memory.json.

        Only high-importance items are persisted to avoid storing
        transient low-value memories across restarts.

        Requirement: 22.3
        """
        items_list = []
        for item in episodic.items:
            if item.importance > 0.3:
                items_list.append({
                    "id": item.id,
                    "summary": item.summary,
                    "valence": round(item.valence, 4),
                    "arousal": round(item.arousal, 4),
                    "phi": round(item.phi, 4),
                    "importance": round(item.importance, 4),
                    "emotional_tag": item.emotional_tag,
                    "timestamp": item.timestamp,
                    "access_count": item.access_count,
                    "content": item.content,
                    "tags": list(item.tags),
                })

        data = {
            "version": 1,
            "timestamp": time.time(),
            "items": items_list,
        }
        filepath = self._path("episodic_memory.json")
        self._atomic_write(filepath, data)
        logger.debug(
            "Saved episodic memory (%d high-importance items) to %s",
            len(items_list), filepath,
        )

    def _load_episodic_memory(self) -> list:
        """
        Load high-importance EpisodicMemory items from data/episodic_memory.json.

        Returns:
            List of episodic item dicts on success, empty list on failure/missing.
        """
        filepath = self._path("episodic_memory.json")
        data = self._safe_load(filepath)
        if data is None:
            return []

        try:
            items = data["items"]
            if not isinstance(items, list):
                raise KeyError("items must be a list")
            # Validate each item has required fields
            for item in items:
                if not isinstance(item, dict):
                    raise KeyError("each item must be a dict")
                if "summary" not in item:
                    raise KeyError("item missing 'summary' field")
            return items
        except KeyError as e:
            logger.warning(
                "Episodic memory file %s has invalid structure (%s); "
                "will initialize empty.",
                filepath,
                e,
            )
            return []
