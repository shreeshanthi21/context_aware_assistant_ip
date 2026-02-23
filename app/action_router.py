class ActionRouter:

    def handle_action(self, intent, user_input):

        if intent == "set_reminder":
            return f"Reminder scheduled for: {user_input}"

        elif intent == "save_habit":
            return "Habit stored successfully."

        elif intent == "save_preference":
            return "Preference stored successfully."

        return None