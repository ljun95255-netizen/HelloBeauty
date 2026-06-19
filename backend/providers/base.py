from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from PIL import Image


@dataclass
class ProviderResult:
    image: Image.Image
    status: str
    provider: str
    params: dict[str, Any] = field(default_factory=dict)


class ImageProvider(Protocol):
    provider_name: str

    def render(self, image: Image.Image, recipe: dict[str, Any], params: dict[str, Any] | None = None) -> ProviderResult:
        ...
