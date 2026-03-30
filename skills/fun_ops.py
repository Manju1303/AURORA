"""
AURORA Fun Skills - Jokes, Music, Weather, Fun Facts
"""
import json
import random
import webbrowser
import urllib.parse
from typing import List, Dict, Any, Callable
from core.skill import Skill


# ✅ Built-in joke bank (no API needed)
JOKES = [
    ("Why don't scientists trust atoms?", "Because they make up everything! 😂"),
    ("Why did the programmer quit?", "Because he didn't get arrays! 😂"),
    ("Why was the math book sad?", "Too many problems! 📚😭"),
    ("What do you call a fish without eyes?", "A fsh! Get it? No i's! 😂"),
    ("Why did the computer go to the doctor?", "It had a virus! 🦠💻"),
    ("What do you call a bear with no teeth?", "A gummy bear! 🐻😂"),
    ("Why is Python the best language?", "Because it is sssssuper powerful! 🐍😎"),
    ("Why did the robot break up?", "There was no connection! 🤖💔"),
]

FACTS = [
    "Did you know? Honey never spoils! 3000-year-old honey was found edible in Egyptian tombs! 🍯",
    "Octopuses have 3 hearts and blue blood! 🐙💙",
    "Bananas are technically berries, but strawberries are not! 🍌🍓",
    "A day on Venus is longer than a year on Venus! 🌍✨",
    "Humans share 60% DNA with bananas! 🍌😂",
    "There are more possible chess games than atoms in the observable universe! ♟️🤯",
    "Crows can recognize and remember human faces! 🐦🧠",
    "Hot water can freeze faster than cold water — it's called the Mpemba effect! 🧊🔥",
]


class FunSkill(Skill):
    @property
    def name(self) -> str:
        return "fun_skill"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {"name": "tell_joke", "description": "Tell a funny joke",
             "parameters": {"type": "OBJECT", "properties": {}}},
            {"name": "play_music", "description": "Play music or a song on YouTube",
             "parameters": {"type": "OBJECT", "properties": {
                 "song_name": {"type": "STRING", "description": "Song or artist name to play"}
             }, "required": ["song_name"]}},
            {"name": "fun_fact", "description": "Tell an interesting fun fact",
             "parameters": {"type": "OBJECT", "properties": {}}},
            {"name": "flip_coin", "description": "Flip a coin - heads or tails",
             "parameters": {"type": "OBJECT", "properties": {}}},
            {"name": "roll_dice", "description": "Roll a dice",
             "parameters": {"type": "OBJECT", "properties": {
                 "sides": {"type": "INTEGER", "description": "Number of sides (default 6)"}
             }}},
        ]

    def get_functions(self) -> Dict[str, Callable]:
        return {
            "tell_joke": self.tell_joke,
            "play_music": self.play_music,
            "fun_fact": self.fun_fact,
            "flip_coin": self.flip_coin,
            "roll_dice": self.roll_dice,
        }

    def tell_joke(self):
        """Tell a random joke from the built-in bank"""
        setup, punchline = random.choice(JOKES)
        return json.dumps({
            "status": "success",
            "setup": setup,
            "punchline": punchline,
            "full": f"{setup} ... {punchline}"
        })

    def play_music(self, song_name: str):
        """Open YouTube with the song search"""
        try:
            query = urllib.parse.quote(song_name + " song")
            url = f"https://www.youtube.com/results?search_query={query}"
            webbrowser.open(url)
            return json.dumps({"status": "success", "playing": song_name, "platform": "YouTube"})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

    def fun_fact(self):
        """Share a random fun fact"""
        fact = random.choice(FACTS)
        return json.dumps({"status": "success", "fact": fact})

    def flip_coin(self):
        """Flip a coin"""
        result = random.choice(["Heads! 🌝", "Tails! 🌚"])
        return json.dumps({"status": "success", "result": result})

    def roll_dice(self, sides: int = 6):
        """Roll a dice"""
        sides = max(2, min(100, int(sides)))
        result = random.randint(1, sides)
        return json.dumps({"status": "success", "rolled": result, "sides": sides})
