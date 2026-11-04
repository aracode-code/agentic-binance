"""DeepSeek LLM tool.

Single responsibility: send a prompt to DeepSeek API and return the response.
- No analysis logic
- No trading logic
- No reasoning logic
- No market parsing

Reusable by any agent (Market, Risk, News, Review).
The agent decides WHAT to ask — this tool only delivers the answer.
"""
import requests

from config.settings import DEEPSEEK_API_KEY

BASE_URL = "https://api.deepseek.com"


def ask(
    prompt: str,
    system: str = "",
    model: str = "deepseek-chat",
    temperature: float = 0.3,
) -> str:
    """Send a prompt to DeepSeek API and return the response text.

    Args:
        prompt: The user prompt/question to send.
        system: Optional system prompt to set assistant behavior.
        model: DeepSeek model — "deepseek-chat" or "deepseek-reasoner".
        temperature: 0.0 = deterministic, 1.0 = creative.

    Returns:
        str: The response text from DeepSeek.

    Raises:
        requests.HTTPError: if the API request fails.
    """
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]