def get_prompt(full_text, categories):
    cat_string = ""
    for cat in categories: 
        cat_string += f"- {cat}\n"
    system_prompt = f"""
Your task is to redact the following Personally Identifiable Information (PII) from the given documents:

{cat_string}

Extract the exact string in a JSON array. Only output the JSON array. 
"""

    document_text = f"<document>{full_text}</document>"
    return system_prompt, document_text
