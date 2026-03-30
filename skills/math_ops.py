import json
import re
from typing import List, Dict, Any, Callable
from core.skill import Skill

class MathSkill(Skill):
    @property
    def name(self) -> str:
        return "math_skill"

    def get_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": "calculate",
                "description": "Perform mathematical calculations",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "expression": {"type": "STRING", "description": "The math expression, e.g. 2 + 3 * 10"}
                    },
                    "required": ["expression"]
                }
            }
        ]

    def get_functions(self) -> Dict[str, Callable]:
        return {
            "calculate": self.calculate
        }

    def calculate(self, expression: str):
        """Safely evaluate a mathematical expression"""
        try:
            # Clean expression: 'into' -> '*', 'x' -> '*'
            expr = expression.lower().replace("into", "*").replace("x", "*").replace("plus", "+").replace("minus", "-").replace("divided by", "/")
            # Remove all non-math characters except numbers and operators
            expr = re.sub(r'[^0-9+\-*/(). ]', '', expr)
            
            # Simple eval (safe-ish since we regexed it)
            result = eval(expr, {"__builtins__": {}}, {})
            return json.dumps({"status": "success", "expression": expression, "result": result})
        except Exception as e:
            return json.dumps({"status": "error", "message": "Neural math processor failed. Please simplify the query."})
