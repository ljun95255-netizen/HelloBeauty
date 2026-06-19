from __future__ import annotations

from jesr_core import merge_feedback


FREE_TEXT_TO_TAGS = {
    "not me": "identity_not_preserved",
    "identity": "identity_not_preserved",
    "plastic": "texture_too_fake",
    "fake": "texture_too_fake",
    "lighting": "style_or_lighting_mismatch",
    "style": "style_or_lighting_mismatch",
    "unlike": "identity_not_preserved",
}


class FeedbackInterpreter:
    def pain_tags_from_text(self, text: str | None) -> list[str]:
        if not text:
            return []
        lowered = text.lower()
        tags: list[str] = []
        for keyword, tag in FREE_TEXT_TO_TAGS.items():
            if keyword in lowered and tag not in tags:
                tags.append(tag)
        return tags

    def apply(self, recipe: dict, pain_tags: list[str] | None, free_text: str | None) -> dict:
        tags = list(pain_tags or [])
        for tag in self.pain_tags_from_text(free_text):
            if tag not in tags:
                tags.append(tag)
        return merge_feedback(recipe, tags, free_text)
