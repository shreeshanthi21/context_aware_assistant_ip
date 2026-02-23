import re

class IntentDetector:

    def detect_intent(self, text: str) -> str:
        text = text.lower().strip()

        # 🔹 recall questions FIRST (highest priority)
        if re.search(r"\b(what|when|where|do i|did i)\b", text):
            return "recall_memory"

        # 🔹 reminder intent
        if re.search(r"\b(remind|alarm|schedule)\b", text):
            return "set_reminder"

        # 🔹 preference intent
        if re.search(r"\b(prefer|like|favourite|favorite)\b", text):
            return "save_preference"

        # 🔹 habit detection
        if re.search(r"\b(wake|sleep|study|exercise|workout|eat)\b", text):
            return "save_habit"

        return "general_chat"