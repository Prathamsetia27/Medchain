

import random


def generate_captcha() -> dict:
    """
    Generates a simple arithmetic CAPTCHA question.
    Even though validation is disabled, this keeps the UI intact.
    """
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    op = random.choice(["+", "-", "*"])

    if op == "+":
        question = f"{a} + {b}"
        answer = a + b
    elif op == "-":
        a, b = max(a, b), min(a, b)
        question = f"{a} - {b}"
        answer = a - b
    else:
        a, b = random.randint(1, 5), random.randint(1, 5)
        question = f"{a} × {b}"
        answer = a * b

    return {
        "question": question,
        "answer": answer
    }


def validate_captcha(user_answer: str, expected_answer: int) -> bool:
    """
    🚫 CAPTCHA FORCE DISABLED
    Always returns True.
    """
    return True