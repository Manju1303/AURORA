import webbrowser
import json
import requests
from typing import List, Dict, Any, Callable
from core.skill import Skill

class WebSkill(Skill):
    @property
    def name(self) -> str:
        return "web_skill"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "google_search",
                "description": "Search Google for a query or open a URL",
                "parameters": { 
                    "type": "OBJECT", 
                    "properties": { 
                        "query": {"type": "STRING", "description": "The search term to look for"} 
                    }, 
                    "required": ["query"] 
                }
            },
            {
                "name": "web_rag",
                "description": "Get real-time live search result snippets from the web (RAG)",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Query to search for"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "get_weather",
                "description": "Get real-time weather information for a city",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "city": {"type": "STRING", "description": "The city name"}
                    },
                    "required": ["city"]
                }
            }
        ]

    def get_functions(self) -> Dict[str, Callable]:
        return {
            "google_search": self.google_search,
            "web_rag": self.web_rag,
            "get_weather": self.get_weather
        }

    def google_search(self, query):
        """Open Google Search in the browser."""
        try:
            if not query:
                webbrowser.open("https://www.google.com")
                return json.dumps({"status": "opened google home"})
            
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            webbrowser.open(search_url)
            return json.dumps({"status": "searching", "query": query})
        except Exception as e:
             return json.dumps({"error": str(e)})

    def web_rag(self, query: str):
        """Fetch live facts using DuckDuckGo Instant Answer + Wikipedia fallback."""
        import urllib.parse
        
        # --- Source 1: DuckDuckGo Instant Answer API (100% free, JSON) ---
        try:
            url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                # Check AbstractText (best answer)
                abstract = data.get("AbstractText", "").strip()
                if abstract and len(abstract) > 30:
                    return json.dumps({"status": "success", "snippets": [abstract]})
                # Check Answer (for quick factual replies like "who is X")
                answer = data.get("Answer", "").strip()
                if answer:
                    return json.dumps({"status": "success", "snippets": [answer]})
        except Exception:
            pass
        
        # --- Source 2: Wikipedia REST API (clean, fast, 100% free) ---
        try:
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
            resp = requests.get(wiki_url, headers={"User-Agent": "AURORA-AI/3.0"}, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                extract = data.get("extract", "").strip()
                if extract:
                    # Return first 2 sentences only for conciseness
                    sentences = extract.split(". ")
                    summary = ". ".join(sentences[:2]) + "."
                    return json.dumps({"status": "success", "snippets": [summary]})
        except Exception:
            pass
        
        # --- Source 3: DuckDuckGo Robust Scraper Fallback ---
        try:
            url = f"https://duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            resp = requests.get(url, headers=headers, timeout=6)
            if resp.status_code == 200:
                from html.parser import HTMLParser
                import re
                
                # Crude extraction of highest-relevance snippets
                text = resp.text
                if "result__snippet" in text:
                    parts = text.split("result__snippet")[1:5]
                    snippets = []
                    for p in parts:
                        match = re.search(r'>(.*?)</a>', p) # For result summary
                        snippet = p.split(">")[1].split("</")[0].strip()
                        if len(snippet) > 30:
                            snippets.append(snippet)
                    if snippets:
                        return json.dumps({"status": "success", "snippets": snippets})
        except Exception:
            pass
        
        # --- Source 4: Auto-detect if User is asking about a person/place for Wikipedia ---
        if len(query.split()) < 5:
             try:
                 # Search Wikipedia specifically
                 search_url = f"https://en.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit=1&format=json"
                 sr = requests.get(search_url, timeout=5).json()
                 if sr and len(sr) > 1 and sr[1]:
                     p_title = sr[1][0]
                     p_resp = requests.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(p_title)}", timeout=5).json()
                     if "extract" in p_resp:
                         return json.dumps({"status": "success", "snippets": [p_resp["extract"]]})
             except: pass

        return json.dumps({"status": "no_results"})

    def get_weather(self, city):
        """Fetch live weather (Free data)."""
        try:
            # Using wttr.in (Fast, free, no API key required for basic info)
            resp = requests.get(f"https://wttr.in/{city}?format=%C+%t", timeout=5)
            if resp.status_code == 200:
                data = resp.text.strip()
                return json.dumps({"status": "success", "city": city, "weather": data})
            return json.dumps({"error": "could not fetch weather"})
        except Exception as e:
            return json.dumps({"error": str(e)})
