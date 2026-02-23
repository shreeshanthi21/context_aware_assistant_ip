class LLMEngine:
    def __init__(self):
        pass

    def generate_response(self, user_input, intent, context=None):

        if intent == "set_reminder":
            return "Sure, I’ll set that reminder for you."

        elif intent == "save_habit":
            return "Got it. I’ll remember that habit."

        elif intent == "save_preference":
            return "Okay, I’ve saved your preference."

        elif intent == "recall_memory":
            if context:
                return f"Here’s what I remember: {context}"
            else:
                return "I don’t have anything stored about that yet."

        else:
            return "Alright, I’m here to help."
        