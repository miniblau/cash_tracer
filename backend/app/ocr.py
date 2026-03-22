import base64
import json
import os
import re

import anthropic

_PROMPT_BASE = """Extract from this receipt image:
- store: the store or merchant name
- date: the purchase date in YYYY-MM-DD format
- total: the total amount actually paid, as a number (use period as decimal separator)
- items: list of purchased products, each with:
  - name: product name
  - price: final price as a number (base price minus any per-item discount, plus any deposit/pant)
  - category: best matching category from the list below, or null if none fit

Available categories:
{categories}

Rules:
- Combine base price, per-item discounts, and deposits (pant) into a single final price per product
- Skip receipt-level lines like subtotals, total tax, receipt discounts, and loyalty point summaries
- Use period as decimal separator for all numbers

Return only JSON:
{{
  "store": "...",
  "date": "...",
  "total": 0.00,
  "items": [
    {{"name": "...", "price": 0.00, "category": "...or null"}}
  ]
}}
Use null for any field you cannot determine with confidence."""


async def extract_receipt(image_bytes: bytes, media_type: str, categories: list[str]) -> dict:
    b64 = base64.standard_b64encode(image_bytes).decode()

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    category_list = "\n".join(f"- {c}" for c in categories) if categories else "(none provided)"
    prompt = _PROMPT_BASE.format(categories=category_list)

    message = await anthropic.AsyncAnthropic(api_key=api_key).messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": b64},
                },
                {"type": "text", "text": prompt},
            ],
        }],
    )

    text = message.content[0].text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)
