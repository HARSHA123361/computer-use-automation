from __future__ import annotations

import json
import os
from typing import List, Optional

from .schema import CapabilityArtifact


class ArtifactStore:
    def __init__(self, directory: str = "artifacts"):
        self.directory = directory
        os.makedirs(directory, exist_ok=True)

    def save(self, artifact: CapabilityArtifact) -> str:
        filename = f"{artifact.name.lower().replace(' ', '_')}_{artifact.version}.json"
        path = os.path.join(self.directory, filename)
        with open(path, "w") as f:
            f.write(artifact.model_dump_json(indent=2))
        return path

    def load(self, path: str) -> CapabilityArtifact:
        with open(path) as f:
            data = json.load(f)
        return CapabilityArtifact.model_validate(data)

    def load_by_name(self, name: str, version: Optional[str] = None) -> Optional[CapabilityArtifact]:
        candidates = []
        for filename in os.listdir(self.directory):
            if not filename.endswith(".json"):
                continue
            normalized_name = name.lower().replace(" ", "_")
            if filename.startswith(normalized_name):
                candidates.append(filename)

        if not candidates:
            return None

        if version:
            for filename in candidates:
                if filename.endswith(f"_{version}.json"):
                    return self.load(os.path.join(self.directory, filename))
            return None

        candidates.sort(reverse=True)
        return self.load(os.path.join(self.directory, candidates[0]))

    def list_all(self) -> List[CapabilityArtifact]:
        results = []
        for filename in sorted(os.listdir(self.directory)):
            if filename.endswith(".json"):
                try:
                    artifact = self.load(os.path.join(self.directory, filename))
                    results.append(artifact)
                except Exception:
                    pass
        return results
