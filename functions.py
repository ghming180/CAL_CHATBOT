# functions.py
def get_openai_function_definitions():
    return [
        {
            "name": "book_event",
            "description": "Book a new meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"},
                    "date": {"type": "string", "description": "Meeting date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Meeting time in HH:MM format"},
                    "reason": {"type": "string", "description": "Meeting purpose"}
                },
                "required": ["email", "date", "time", "reason"]
            }
        },
        {
            "name": "list_events",
            "description": "List user's scheduled events",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"}
                },
                "required": ["email"]
            }
        },
        {
            "name": "cancel_event",
            "description": "Cancel a scheduled meeting",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "description": "User's email address"},
                    "date": {"type": "string", "description": "Meeting date in YYYY-MM-DD format"},
                    "time": {"type": "string", "description": "Meeting time in HH:MM format"}
                },
                "required": ["email", "date", "time"]
            }
        }
    ]

if __name__ == "__main__":
    print(get_openai_function_definitions())
