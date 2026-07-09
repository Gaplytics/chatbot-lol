import os

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

def get_system_prompt(bot_name: str, rag_context: str, tenant_id: str) -> str:
    base_prompt_path = os.path.join(PROMPTS_DIR, "base.md")
    
    with open(base_prompt_path, "r", encoding="utf-8") as f:
        base_prompt = f.read()

    tenant_prompt_path = os.path.join(PROMPTS_DIR, f"{tenant_id}.md")
    
    if os.path.exists(tenant_prompt_path):
        with open(tenant_prompt_path, "r", encoding="utf-8") as f:
            tenant_context = f.read()
    else:
        tenant_context = "CRITICAL ERROR: NO VALID TENANT ID WAS PROVIDED TO THIS BOT. YOU MUST REFUSE TO ANSWER QUESTIONS AND TELL THE USER THE SYSTEM IS BROKEN."
        
    return base_prompt.format(bot_name=bot_name, tenant_context=tenant_context, rag_context=rag_context)
