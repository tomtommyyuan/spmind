"""
LLM client utilities for OpenAI and Google Gemini models.
"""

import openai
from google import genai
from google.genai import types


def get_openai_response(
    client: openai.OpenAI,
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gpt-5",
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 500,
) -> str:
    """
    Get a response from an OpenAI language model.

    Args:
        client: OpenAI client instance.
        prompt: The user prompt to send to the model.
        system_prompt: System prompt to set model behavior.
        model: OpenAI model to use.
        temperature: Controls randomness in responses.
        top_p: Controls diversity via nucleus sampling.
        max_tokens: Maximum tokens in the model response.

    Returns:
        The model's response text.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content


def get_gemini_response(
    client: genai.Client,
    prompt: str,
    system_prompt: str = "You are a helpful assistant.",
    model: str = "gemini-3-pro",
    temperature: float = 0.7,
    top_p: float = 0.95,
    max_tokens: int = 500,
) -> str:
    """
    Get a response from a Google Gemini language model.

    Args:
        client: Google GenAI client instance.
        prompt: The user prompt to send to the model.
        system_prompt: System instruction to set model behavior.
        model: Gemini model to use.
        temperature: Controls randomness in responses.
        top_p: Controls diversity via nucleus sampling.
        max_tokens: Maximum tokens in the model response.

    Returns:
        The model's response text.
    """
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_tokens,
        ),
    )

    return response.text
