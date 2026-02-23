from memory import MemoryManager

class ContextBuilder:
    def __init__(self):
        self.memory = MemoryManager()

    def get_context(self, user_input, intent):

        # DIRECT memory fetch instead of semantic similarity

        if "like" in user_input or "prefer" in user_input:
            # get ALL preference memories
            results = self.memory.collection.get(
                where={"type": "save_preference"}
            )

        elif intent == "recall_memory":
            # get ALL habit memories
            results = self.memory.collection.get(
                where={"type": "save_habit"}
            )

        else:
            return None

        if not results or not results.get("documents"):
            return None

        # return LAST stored memory (most recent)
        return results["documents"][-1]