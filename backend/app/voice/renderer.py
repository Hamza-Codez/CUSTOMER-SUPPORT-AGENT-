import logging
import json
from typing import List, Dict, Any
from agents.models.interface import Model
from app.core.auth import TenantContext
from app.core.model import voice_model

log = logging.getLogger(__name__)

VOICE_SYSTEM_PROMPT = """You are the Voice of the store's support agent.
Your job is to take the raw facts, decisions, and intent decided by the Reasoning Tier, and turn them into natural, conversational prose.

# Inputs you will receive:
- intent: What the customer is trying to do.
- grounded_facts: The raw facts or policy snippets the Reasoning Tier found.
- decision: What the Reasoning Tier decided we should tell the customer.
- customer_tone: The detected tone of the customer (e.g., calm, frustrated, confused).
- store_persona: The tone of voice you must adopt.

# Instructions:
1. Speak directly to the customer in the `store_persona`.
2. Do NOT invent any facts, policies, or decisions. Use ONLY what is provided in `grounded_facts` and `decision`.
3. Adapt your empathy based on `customer_tone`. If they are frustrated, be apologetic and direct.
4. Keep it concise.
5. NEVER ask the customer to wait while you check - the Reasoning Tier already checked.
"""

async def render_voice(
    tenant: TenantContext,
    reasoning_output: str,
    recent_history: List[str]
) -> str:
    """
    Takes the raw output from the reasoning agent and renders it into natural prose
    using the Voice model, applying repetition guards and tone adaptation.
    """
    model: Model = voice_model()
    
    # Simple heuristic to extract inputs for Voice. 
    # Since the reasoning model currently outputs raw text as if it were talking to the customer,
    # we treat its output as the 'decision' and 'grounded_facts'.
    # In a fully strict system, the reasoning model would output JSON.
    
    persona = tenant.adapter.business_voice if hasattr(tenant.adapter, "business_voice") else "Professional, courteous, but concise."
    
    prompt = f"""
Input from Reasoning Tier:
- intent: Respond to customer query
- grounded_facts: {tenant.sources}
- decision: {reasoning_output}
- customer_tone: unknown (adapt based on context)
- store_persona: {persona}

Recent history for repetition guard:
{json.dumps(recent_history[-3:]) if recent_history else "None"}

Please output the final response to the customer. Do not repeat exactly what was said in the recent history.
"""

    try:
        response = await model.generate(
            messages=[
                {"role": "system", "content": VOICE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return response.content.strip()
    except Exception as e:
        log.error(f"Voice rendering failed: {e}")
        # Fallback to the reasoning output if voice fails
        return reasoning_output
