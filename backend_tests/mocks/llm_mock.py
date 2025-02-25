"""Mock LLM for testing."""

from typing import Any, List, Optional, Sequence
from langchain_core.language_models.base import BaseLanguageModel
from langchain_core.outputs import LLMResult, Generation
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from pydantic import ConfigDict

class MockLLM(BaseLanguageModel):
    """Mock LLM for testing."""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    def invoke(
        self,
        input: str,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> str:
        """Mock LLM invocation that returns a fixed response."""
        return "This is a mock LLM response for testing purposes."
    
    async def ainvoke(
        self,
        input: str,
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> str:
        """Mock async LLM invocation that returns a fixed response."""
        return self.invoke(input, config, **kwargs)
    
    def batch(
        self,
        inputs: List[str],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> List[str]:
        """Mock batch invocation that returns fixed responses."""
        return [self.invoke(input, config, **kwargs) for input in inputs]
    
    async def abatch(
        self,
        inputs: List[str],
        config: Optional[RunnableConfig] = None,
        **kwargs: Any
    ) -> List[str]:
        """Mock async batch invocation that returns fixed responses."""
        return [await self.ainvoke(input, config, **kwargs) for input in inputs]
    
    @property
    def _llm_type(self) -> str:
        """Return identifier of mock LLM."""
        return "mock_llm"
    
    @property
    def _identifying_params(self) -> dict:
        """Return empty params for mock."""
        return {} 