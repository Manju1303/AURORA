from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable

class Skill(ABC):
    """Base class for all AURORA Skills."""
    
    @abstractmethod
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return the list of tool schemas for Gemini function calling."""
        pass

    @abstractmethod
    def get_functions(self) -> Dict[str, Callable]:
        """Return a dictionary mapping function names to functions."""
        pass

    def initialize(self, context: Dict[str, Any] = None):
        """Optional initialization."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """The identifier of the skill."""
        pass
