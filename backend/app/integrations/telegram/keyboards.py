def approval_keyboard(token: str) -> dict[str, list[list[dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [
                {"text": "Approve", "callback_data": f"th:{token}:a"},
                {"text": "Reject", "callback_data": f"th:{token}:r"},
            ]
        ]
    }
