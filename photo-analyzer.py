import base64
import requests
import json
from dataclasses import dataclass, fields
from typing import Optional, List, Any

@dataclass
class OllamaResponse:
    model: str
    created_at: str
    response: str
    done: bool
    done_reason: Optional[str] = None
    context: Optional[List[Any]] = None
    total_duration: Optional[int] = None
    load_duration: Optional[int] = None
    prompt_eval_count: Optional[int] = None
    prompt_eval_duration: Optional[int] = None
    eval_count: Optional[int] = None
    eval_duration: Optional[int] = None

def load_image_as_base64(filename: str) -> str:
    try:
        with open(filename, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    except FileNotFoundError:
        print(f"File not found: {filename}")
        exit(1)

def stream_ollama_response(image_b64: str, prompt: str) -> str:
    payload = {
        "model": "llava",
        "prompt": prompt,
        "images": [image_b64]
    }
    try:
        response = requests.post("http://localhost:11434/api/generate", json=payload, stream=True)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Request failed: {e}")
        exit(1)

    full_response = ""
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode())
            # Only pass known fields to the dataclass
            known_fields = {f.name for f in fields(OllamaResponse)}
            filtered_data = {k: v for k, v in data.items() if k in known_fields}
            resp = OllamaResponse(**filtered_data)
            print(resp.response, end="", flush=True)
            full_response += resp.response
            if resp.done:
                print()
    return full_response

if __name__ == "__main__":
    image_filename = "picture.jpg"
    prompt = "I have an instagram account on photography. Give a nice description and hashtags for this image for creating a post on instagram on my photography account."
    image_b64 = load_image_as_base64(image_filename)
    stream_ollama_response(image_b64, prompt)