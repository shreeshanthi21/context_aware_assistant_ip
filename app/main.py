from intent import IntentDetector
<<<<<<< HEAD

detector = IntentDetector()

print("\nIntent Test Ready\n")

while True:
    text = input("You: ")
    intent = detector.detect_intent(text)
    print("Intent:", intent)
=======
from llm_engine import LLMEngine
from context_builder import ContextBuilder
from memory import MemoryManager
from action_router import ActionRouter
import uuid

# Initialize modules
detector = IntentDetector()
llm = LLMEngine()
context_builder = ContextBuilder()
memory_manager = MemoryManager()
action_router = ActionRouter()

print("\nAssistant Ready\n")

while True:
    text = input("You: ")

    # Detect intent
    intent = detector.detect_intent(text)

    # Store habits and preferences
    if intent in ["save_habit", "save_preference"]:
        memory_manager.add_memory(
            text,
            intent,
            str(uuid.uuid4())
        )

    # Retrieve context (if any)
    context = context_builder.get_context(text, intent)

    # Generate assistant response
    response = llm.generate_response(
        user_input=text,
        intent=intent,
        context=context
    )

    print("Assistant:", response)

    # Execute action layer
    action_result = action_router.handle_action(intent, text)

    if action_result:
        print("System:", action_result)
>>>>>>> 5ca6a8e (Added reasoning layer, context-aware memory, and action orchestration)
