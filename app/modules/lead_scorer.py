import json
import logging

from openai import AsyncOpenAI

from app import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

SCORING_PROMPT = """
You are a B2B sales qualification expert. Score the following lead from 1 to 10.

Scoring weights:
- Budget: high weight. "$20,000+" = top score, "Under $1,000" = low score
- Timeline: high weight. "Immediately" = top score, "No fixed timeline" = low score
- Decision maker: high weight. "Yes, I make the final call" = top score
- Company size: medium weight. Larger = higher
- Current situation: medium weight. "specific problem now" = top score

Return ONLY valid JSON, no markdown, no explanation outside the JSON:
{
  "score": <int 1-10>,
  "reasoning": "<2-3 sentences explaining the score>"
}

Lead data:
{lead_data}
"""


async def score_lead(payload: dict) -> dict:
    lead_text = "\n".join(f"{k}: {v}" for k, v in payload.items())
    prompt = SCORING_PROMPT.replace("{lead_data}", lead_text)

    logger.info(f"Scoring lead: {payload.get('full_name')} / {payload.get('company_name')}")

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )

    raw = response.choices[0].message.content.strip()

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        logger.error(f"Failed to parse OpenAI response: {raw}")
        raise ValueError(f"Invalid JSON from OpenAI: {raw}")

    return result