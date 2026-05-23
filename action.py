"""Action role — ArtifactStore + pure MCP dispatch, no LLM."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from schemas import Artifact, ToolCall

_ARTIFACTS_DIR = Path(__file__).resolve().parent / "state" / "artifacts"
_COUNTER_FILE = _ARTIFACTS_DIR / "_counter.json"
ARTIFACT_THRESHOLD_BYTES = 4 * 1024  # 4 KB


class ArtifactStore:
    def __init__(self) -> None:
        _ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        if _COUNTER_FILE.exists():
            self._next_id: int = json.loads(_COUNTER_FILE.read_text())["next_id"]
        else:
            self._next_id = 1

    def _bin_path(self, artifact_id: int) -> Path:
        return _ARTIFACTS_DIR / f"{artifact_id:06d}.bin"

    def _meta_path(self, artifact_id: int) -> Path:
        return _ARTIFACTS_DIR / f"{artifact_id:06d}.json"

    def put(self, blob: bytes, content_type: str, source: str, descriptor: str) -> int:
        """Store blob and return a new incrementing int ID."""
        artifact_id = self._next_id
        self._next_id += 1

        self._bin_path(artifact_id).write_bytes(blob)
        meta = Artifact(
            id=artifact_id,
            content_type=content_type,
            size_bytes=len(blob),
            source=source,
            descriptor=descriptor,
        )
        self._meta_path(artifact_id).write_text(meta.model_dump_json(indent=2))
        _COUNTER_FILE.write_text(json.dumps({"next_id": self._next_id}))
        return artifact_id

    def get_bytes(self, artifact_id: int) -> bytes:
        return self._bin_path(artifact_id).read_bytes()

    def get_meta(self, artifact_id: int) -> Artifact:
        return Artifact.model_validate_json(self._meta_path(artifact_id).read_text())

    def exists(self, artifact_id: int) -> bool:
        return self._bin_path(artifact_id).exists()


class Action:
    def __init__(self, store: Optional[ArtifactStore] = None) -> None:
        self.store = store or ArtifactStore()

    def _resolve_art_handles(self, arguments: dict) -> dict:
        """Replace 'art:<id>' or 'artifact:<id>' arguments with artifact text content."""
        import re
        _pattern = re.compile(r"^(?:art|artifact):(\d+)$", re.IGNORECASE)
        resolved = {}
        for key, val in arguments.items():
            m = _pattern.match(val) if isinstance(val, str) else None
            if m:
                try:
                    blob = self.store.get_bytes(int(m.group(1)))
                    resolved[key] = blob.decode("utf-8", errors="replace")
                except Exception:
                    resolved[key] = val
            else:
                resolved[key] = val
        return resolved

    async def execute(
        self,
        session,  # mcp.ClientSession
        tool_call: ToolCall,
    ) -> tuple[str, Optional[int]]:
        """Dispatch tool via MCP. Returns (descriptor_or_text, artifact_id?)."""
        arguments = self._resolve_art_handles(tool_call.arguments)

        # If any argument was resolved from an art handle into full content
        # (long string, clearly not a valid file path or URL), the LLM tried
        # to pass artifact bytes to a path/url tool. Skip the MCP call and
        # return the resolved content directly so it re-enters the loop.
        for val in arguments.values():
            if isinstance(val, str) and len(val) > 512:
                blob = val.encode("utf-8")
                descriptor = f"{tool_call.name}[artifact-resolved] → {val[:80].strip()}"
                if len(blob) > ARTIFACT_THRESHOLD_BYTES:
                    artifact_id = self.store.put(
                        blob=blob, content_type="text/plain",
                        source="artifact-resolved", descriptor=descriptor,
                    )
                    return descriptor, artifact_id
                return val, None

        result = await session.call_tool(tool_call.name, arguments=arguments)

        if result.isError:
            error_text = " ".join(
                getattr(b, "text", str(b)) for b in (result.content or [])
            )
            raise RuntimeError(f"Tool {tool_call.name!r} error: {error_text}")

        parts = []
        for block in result.content or []:
            text = getattr(block, "text", None)
            if text is not None:
                parts.append(text)
            else:
                parts.append(json.dumps(block, default=str))
        result_text = "\n".join(parts) if parts else ""

        blob = result_text.encode("utf-8")
        descriptor = f"{tool_call.name} → {result_text[:80].strip()}"

        if len(blob) > ARTIFACT_THRESHOLD_BYTES:
            artifact_id = self.store.put(
                blob=blob,
                content_type="text/plain",
                source=tool_call.name,
                descriptor=descriptor,
            )
            return descriptor, artifact_id

        return result_text, None


# module-level singletons
store = ArtifactStore()
action = Action(store)
