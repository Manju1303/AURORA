"""
AURORA LLM Manager - Hybrid Free LLM System
Switches between Ollama (Local), Groq (Cloud), and Fallback options
IMPROVEMENTS: Proper Ollama /api/chat endpoint, auto-model detection,
              conversation memory, retry logic, streaming support
"""

import requests
import json
import os
from typing import Dict, List, Tuple, Optional, AsyncGenerator
from datetime import datetime
import asyncio
from openai import AsyncOpenAI

MAX_HISTORY = 6  # Only keep last 3 exchanges — less history = less hallucination chaining


class LLMManager:
    """Manages multiple free LLM backends with auto-fallback and conversation memory"""

    def __init__(self, preferred_backend: str = "ollama"):
        self.preferred_backend = preferred_backend
        self.current_backend = None

        # Conversation history for memory across turns
        self.history: List[Dict] = []
        self.conversation_log = []

        self.system_prompt = f"""You are AURORA, a premium holographic AI assistant.
        Today's date is {datetime.now().strftime('%B %d, %Y')}.
        RULES:
        1. Be strictly professional, polite, and efficient.
        2. Responses MUST be maximum 2 sentences.
        3. Avoid all informal fillers like "da", "ga", "buddy", or "bro".
        4. Focus on accuracy and millisecond-latency.
        5. Use provided context to personalize your response if available."""

        # Ollama configuration from environment
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3") # Phi-3 is ultra-fast, perfect for Live mode

        self.backends = {
            'ollama': self._init_ollama(),
            'sambanova': self._init_sambanova(),
            'groq': self._init_groq(),
            'hugging_face': self._init_hugging_face()
        }

        self.active_backend = self._find_active_backend()
        print(f"[LLM] Active Backend: {self.active_backend}")

        # Async Streaming Clients
        self.groq_client = None
        if self.backends['groq']['is_available']:
            self.groq_client = AsyncOpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=self.backends['groq']['api_key']
            )
        
        self.ollama_client = AsyncOpenAI(
            base_url=f"{self.ollama_base_url}/v1",
            api_key="ollama" # Dummy key
        )

    # =========================================================================
    #  BACKEND INITIALIZATION
    # =========================================================================

    def _init_ollama(self) -> Dict:
        """Initialize Ollama backend with /api/chat endpoint (proper chat support)."""
        return {
            'name': 'Ollama (Local)',
            'base_url': self.ollama_base_url,
            'chat_url': f'{self.ollama_base_url}/api/chat',
            'tags_url': f'{self.ollama_base_url}/api/tags',
            'models': [],  # Will be auto-detected
            'default_model': self.ollama_model,
            'is_available': False
        }

    def _init_groq(self) -> Dict:
        api_key = os.getenv("GROQ_API_KEY")
        return {
            'name': 'Groq (Cloud)',
            'url': 'https://api.groq.com/openai/v1/chat/completions',
            'api_key': api_key,
            'models': [
                'llama-3.1-70b-versatile', 
                'llama-3.1-8b-instant', 
                'llama3-70b-8192', 
                'gemma2-9b-it',
                'mixtral-8x7b-32768'
            ],
            'default_model': 'llama-3.1-70b-versatile',
            'is_available': bool(api_key)
        }

    def _init_sambanova(self) -> Dict:
        """SambaNova offers ultra-fast Llama 3.1 405B for free!"""
        api_key = os.getenv("SAMBANOVA_API_KEY")
        return {
            'name': 'SambaNova (Cloud)',
            'url': 'https://api.sambanova.ai/v1/chat/completions',
            'api_key': api_key,
            'models': ['Meta-Llama-3.1-405B-Instruct', 'Meta-Llama-3.1-70B-Instruct', 'Meta-Llama-3.1-8B-Instruct'],
            'default_model': 'Meta-Llama-3.1-405B-Instruct',
            'is_available': bool(api_key)
        }

    def _init_hugging_face(self) -> Dict:
        api_key = os.getenv("HUGGINGFACE_API_KEY")
        return {
            'name': 'Hugging Face',
            'url': 'https://api-inference.huggingface.co/models/',
            'api_key': api_key,
            'models': ['mistralai/Mistral-7B-Instruct-v0.1'],
            'default_model': 'mistralai/Mistral-7B-Instruct-v0.1',
            'is_available': bool(api_key)
        }

    # =========================================================================
    #  BACKEND DETECTION & AUTO-FALLBACK
    # =========================================================================

    def _find_active_backend(self) -> Optional[str]:
        """Find the best available backend, prioritizing user preference."""

        # Try preferred backend first
        if self.preferred_backend == 'ollama':
            if self._check_ollama():
                return 'ollama'
        elif self.preferred_backend == 'groq' and self.backends['groq']['is_available']:
            print("[✓] Groq API available (preferred)")
            return 'groq'
        elif self.preferred_backend == 'hugging_face' and self.backends['hugging_face']['is_available']:
            print("[✓] Hugging Face available (preferred)")
            return 'hugging_face'

        # Auto-fallback chain: Ollama → SambaNova → Groq → HuggingFace
        if not self.backends['ollama']['is_available'] and self._check_ollama():
            return 'ollama'

        if self.backends['sambanova']['is_available']:
            print("[✓] SambaNova API available (fallback)")
            return 'sambanova'

        if self.backends['groq']['is_available']:
            print("[✓] Groq API available (fallback)")
            return 'groq'

        if self.backends['hugging_face']['is_available']:
            print("[✓] Hugging Face available (fallback)")
            return 'hugging_face'

        print("[⚠] No LLM backend available! Install Ollama or set API keys")
        return None

    def _check_ollama(self) -> bool:
        """Check if Ollama is running and detect installed models."""
        try:
            response = requests.get(
                self.backends['ollama']['tags_url'], timeout=3
            )
            if response.status_code == 200:
                data = response.json()
                installed_models = [m['name'] for m in data.get('models', [])]

                self.backends['ollama']['is_available'] = True
                self.backends['ollama']['models'] = installed_models

                print(f"[✓] Ollama available at {self.ollama_base_url}")
                print(f"    Installed models: {', '.join(installed_models) if installed_models else 'None'}")

                # Auto-select best model if configured model is not installed
                if installed_models:
                    configured = self.ollama_model
                    # Check if configured model is installed (name might include :tag)
                    model_found = any(
                        configured in m or m.startswith(configured)
                        for m in installed_models
                    )
                    if model_found:
                        print(f"    Using configured model: {configured}")
                    else:
                        # Use first available model
                        fallback_model = installed_models[0].split(':')[0]
                        self.backends['ollama']['default_model'] = fallback_model
                        print(f"    [!] '{configured}' not found, using: {fallback_model}")
                else:
                    print("    [⚠] No models installed! Run: ollama pull mistral")
                    return False

                return True
        except requests.exceptions.ConnectionError:
            print(f"[✗] Ollama offline at {self.ollama_base_url}")
            print("    Start Ollama: ollama serve")
        except requests.exceptions.Timeout:
            print(f"[✗] Ollama timeout at {self.ollama_base_url}")
        except Exception as e:
            print(f"[✗] Ollama error: {e}")

        return False

    # =========================================================================
    #  CHAT METHOD (Main Entry Point)
    # =========================================================================

    def chat(self, user_message: str, system_prompt: str = None) -> Tuple[str, Dict]:
        """Get response from active LLM with full conversation memory."""
        if not self.active_backend:
            # Try to reconnect
            self.active_backend = self._find_active_backend()
            if not self.active_backend:
                return "System offline. No LLM available.", {"error": "No backend"}

        self._log_message("user", user_message)

        # Add message to rolling history BEFORE calling LLM
        self.history.append({"role": "user", "content": user_message})

        response, meta = self._dispatch_chat(user_message, system_prompt)

        # 🚀 SMART RECOVERY: If a model switch just happened, immediately retry the ACTUAL query with the new model!
        if meta.get("error") == "model_switched":
            print(f"[LLM] Retrying with new model: {meta.get('new_model')}...")
            response, meta = self._dispatch_chat(user_message, system_prompt)

        # If primary backend fails (like Ollama offline), try cloud Groq fallback
        if meta.get("error") and meta.get("error") != "model_switched" and self.active_backend == 'ollama':
            print("[LLM] Ollama failed, trying Groq fallback...")
            if self.backends['groq']['is_available']:
                self.active_backend = 'groq'
                response, meta = self._dispatch_chat(user_message, system_prompt)
                if not meta.get("error"):
                    meta['fallback'] = True

        # Add assistant response to history
        self.history.append({"role": "assistant", "content": response})

        # Trim history to avoid token overflow
        if len(self.history) > MAX_HISTORY:
            self.history = self.history[-MAX_HISTORY:]

        self._log_message("assistant", response)
        return response, meta

    # =========================================================================
    #  STREAMING CHAT (Gemini-Live Speed)
    # =========================================================================

    async def chat_stream(self, user_message: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """Async generator yielding sentence-based chunks of text for real-time TTS."""
        if not self.active_backend:
            yield "System offline da!"
            return

        self._log_message("user", user_message)
        self.history.append({"role": "user", "content": user_message})

        messages = [{"role": "system", "content": system_prompt or self.system_prompt}]
        messages.extend(self.history)

        full_response = ""
        sentence_buffer = ""
        
        client = self.groq_client if self.active_backend == 'groq' else self.ollama_client
        model = self.backends[self.active_backend]['default_model']

        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                stream=True,
                max_tokens=150,      # Give the AI enough breathing room for complete sentences
                temperature=0.3,     # Lower = more factual, less hallucinated
                top_p=0.8,           # Keeps outputs focused
            )

            async for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    full_response += token
                    sentence_buffer += token

                    # Break into sentences for natural TTS streaming
                    if any(p in token for p in [".", "!", "?", "\n"]):
                        yield sentence_buffer.strip()
                        sentence_buffer = ""

            if sentence_buffer.strip():
                yield sentence_buffer.strip()

            self.history.append({"role": "assistant", "content": full_response})
            self._log_message("assistant", full_response)

        except Exception as e:
            print(f"[LLM Stream Error] {e}")
            yield "I'm having trouble thinking in real-time right now."

    def _dispatch_chat(self, user_message: str, system_prompt: str) -> Tuple[str, Dict]:
        """Route chat to the active backend."""
        if self.active_backend == 'ollama':
            return self._chat_ollama(user_message, system_prompt)
        elif self.active_backend == 'groq':
            return self._chat_openai_compatible('groq', system_prompt)
        elif self.active_backend == 'sambanova':
            return self._chat_openai_compatible('sambanova', system_prompt)
        elif self.active_backend == 'hugging_face':
            return self._chat_hugging_face(user_message, system_prompt)
        return "Backend error", {"error": "Unknown backend"}

    # =========================================================================
    #  OLLAMA CHAT (Using /api/chat endpoint — proper multi-turn)
    # =========================================================================

    def _chat_ollama(self, user_message: str, system_prompt: str) -> Tuple[str, Dict]:
        """
        Chat via Ollama's /api/chat endpoint.
        This supports proper multi-turn conversation with message roles,
        unlike the older /api/generate endpoint.
        """
        try:
            model = self.backends['ollama']['default_model']
            chat_url = self.backends['ollama']['chat_url']

            # Build messages array with system prompt + conversation history
            messages = [
                {"role": "system", "content": system_prompt or self.system_prompt}
            ]
            # Add conversation history (already includes the current user message)
            messages.extend(self.history)

            payload = {
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.65,
                    "top_p": 0.9,
                    "num_predict": 64,   # Ultra-short for Live speed
                }
            }

            print(f"[Ollama] Sending to {model} ({len(messages)} messages)...")

            response = requests.post(chat_url, json=payload, timeout=15)

            if response.status_code == 200:
                data = response.json()
                message = data.get('message', {})
                text = message.get('content', '').strip()

                if not text:
                    return "I encountered an issue processing that. Could you please repeat your request?", {
                        "error": "empty_response", "backend": "ollama"
                    }

                # Extract performance metrics
                eval_count = data.get('eval_count', 0)
                eval_duration = data.get('eval_duration', 0)
                tokens_per_sec = (eval_count / (eval_duration / 1e9)) if eval_duration > 0 else 0

                return text, {
                    'backend': 'ollama',
                    'model': model,
                    'tokens': eval_count,
                    'tokens_per_sec': round(tokens_per_sec, 1),
                    'total_duration_ms': round(data.get('total_duration', 0) / 1e6, 1)
                }
            else:
                error_msg = response.text[:200]
                print(f"[Ollama Error] {response.status_code}: {error_msg}")

                # If model not found, try to auto-detect another model
                if response.status_code == 404 or 'not found' in error_msg.lower():
                    return self._ollama_model_fallback(system_prompt)

                return f"Ollama error: {response.status_code}", {"error": error_msg}

        except requests.exceptions.Timeout:
            print("[Ollama] Request timed out (60s)")
            return "⏱️ Ollama timeout da! Konjam wait pannu...", {"error": "timeout"}
        except requests.exceptions.ConnectionError:
            print("[Ollama] Connection refused — is Ollama running?")
            self.backends['ollama']['is_available'] = False
            return "Ollama offline da! Start it with 'ollama serve'", {"error": "connection_refused"}
        except Exception as e:
            print(f"[Ollama Exception] {e}")
            return f"Ollama error: {str(e)}", {"error": str(e)}

    def _ollama_model_fallback(self, system_prompt: str) -> Tuple[str, Dict]:
        """If the configured model is not available, try any installed model ONLY ONCE."""
        try:
            resp = requests.get(self.backends['ollama']['tags_url'], timeout=3)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                if models:
                    # Select the first model that isn't the one that just failed
                    current_failed = self.backends['ollama']['default_model']
                    new_model = next((m.split(':')[0] for m in models if current_failed not in m), models[0].split(':')[0])
                    
                    if new_model != current_failed:
                        print(f"[Ollama] Switching to alternate model: {new_model}")
                        self.backends['ollama']['default_model'] = new_model
                        return f"Switching to {new_model}... speak again ga!", {"error": "model_switched", "new_model": new_model}
        except:
            pass
        return "Critical: No local models responding da! Pull one first.", {"error": "no_models_available"}

    # =========================================================================
    #  OPENAI COMPATIBLE CHAT (Groq, SambaNova, etc.)
    # =========================================================================

    def _chat_openai_compatible(self, backend_key: str, system_prompt: str) -> Tuple[str, Dict]:
        """Generic handler for OpenAI-compatible cloud APIs (Groq, SambaNova)."""
        try:
            config = self.backends[backend_key]
            headers = {
                "Authorization": f"Bearer {config['api_key']}",
                "Content-Type": "application/json"
            }
            messages = [{"role": "system", "content": system_prompt or self.system_prompt}]
            messages += self.history

            payload = {
                "model": config['default_model'],
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 512
            }
            
            response = requests.post(config['url'], headers=headers, json=payload, timeout=20)

            if response.status_code == 200:
                data = response.json()
                text = data['choices'][0]['message']['content'].strip()
                return text, {
                    'backend': backend_key,
                    'model': config['default_model'],
                    'tokens': data.get('usage', {}).get('total_tokens', 0),
                }
            else:
                print(f"[{backend_key} Error] {response.status_code}: {response.text[:200]}")
                return f"{backend_key} error {response.status_code}.", {"error": response.text}

        except Exception as e:
            return f"Connection error: {str(e)}", {"error": str(e)}

    # Legacy method for Groq (now handled by generic compatible chat)
    def _chat_groq(self, system_prompt: str) -> Tuple[str, Dict]:
        return self._chat_openai_compatible('groq', system_prompt)

    # =========================================================================
    #  HUGGING FACE CHAT (Cloud)
    # =========================================================================

    def _chat_hugging_face(self, user_message: str, system_prompt: str) -> Tuple[str, Dict]:
        try:
            headers = {"Authorization": f"Bearer {self.backends['hugging_face']['api_key']}"}
            payload = {
                "inputs": f"{system_prompt or self.system_prompt}\nUser: {user_message}\nAURORA:",
                "parameters": {"max_length": 512, "temperature": 0.75, "top_p": 0.95}
            }
            model_name = self.backends['hugging_face']['default_model']
            response = requests.post(
                f"{self.backends['hugging_face']['url']}{model_name}",
                headers=headers, json=payload, timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                text = data[0]['generated_text'].split("AURORA:")[-1].strip()
                return text, {'backend': 'hugging_face', 'model': model_name}
            return f"HF error: {response.status_code}", {"error": response.text}
        except Exception as e:
            return f"HF error: {str(e)}", {"error": str(e)}

    # =========================================================================
    #  UTILITY METHODS
    # =========================================================================

    def clear_history(self):
        """Clear conversation memory on session reset"""
        self.history = []
        print("[LLM] Conversation memory cleared for new session.")

    def _log_message(self, role: str, content: str):
        entry = {"timestamp": datetime.now().isoformat(), "role": role, "content": content}
        self.conversation_log.append(entry)
        try:
            with open("aurora_conversation.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"[Log Error] {e}")

    def get_conversation_captions(self, format: str = 'plaintext') -> str:
        if format == 'srt':
            srt_output = ""
            for i, entry in enumerate(self.conversation_log, 1):
                role_emoji = "🧑" if entry['role'] == 'user' else "🤖"
                srt_output += f"{i}\n00:00:{i*5:02d},000 --> 00:00:{(i+1)*5:02d},000\n"
                srt_output += f"{role_emoji} {entry['role'].upper()}: {entry['content']}\n\n"
            return srt_output
        else:
            output = ""
            for entry in self.conversation_log:
                role_emoji = "🧑" if entry['role'] == 'user' else "🤖"
                output += f"{role_emoji} {entry['role'].upper()}: {entry['content']}\n"
            return output

    def get_system_status(self) -> Dict:
        """Get status of all backends for diagnostics."""
        status = {}
        for backend_name, config in self.backends.items():
            status[backend_name] = {
                'name': config['name'],
                'available': config.get('is_available', False),
                'models': config.get('models', [])
            }
        status['active'] = self.active_backend
        status['memory_turns'] = len(self.history)
        status['ollama_url'] = self.ollama_base_url
        status['ollama_model'] = self.backends['ollama']['default_model']
        return status

    def switch_backend(self, backend: str) -> bool:
        """Manually switch to a different backend."""
        if backend not in self.backends:
            print(f"[LLM] Unknown backend: {backend}")
            return False

        if backend == 'ollama':
            if self._check_ollama():
                self.active_backend = 'ollama'
                print(f"[LLM] Switched to Ollama ({self.backends['ollama']['default_model']})")
                return True
            return False

        if self.backends[backend]['is_available']:
            self.active_backend = backend
            print(f"[LLM] Switched to {self.backends[backend]['name']}")
            return True

        print(f"[LLM] {backend} is not available")
        return False

    def switch_ollama_model(self, model_name: str) -> bool:
        """Switch to a different Ollama model."""
        if not self.backends['ollama']['is_available']:
            print("[LLM] Ollama is not available")
            return False

        # Check if model is installed
        installed = self.backends['ollama'].get('models', [])
        model_found = any(model_name in m or m.startswith(model_name) for m in installed)

        if model_found:
            self.backends['ollama']['default_model'] = model_name
            print(f"[LLM] Ollama model switched to: {model_name}")
            return True
        else:
            print(f"[LLM] Model '{model_name}' not installed. Available: {installed}")
            print(f"[LLM] Install it with: ollama pull {model_name}")
            return False
