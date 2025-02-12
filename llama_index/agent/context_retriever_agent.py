"""Context retriever agent."""

from typing import List, Optional

from llama_index.agent.openai_agent import (
    DEFAULT_MAX_FUNCTION_CALLS,
    DEFAULT_MODEL_NAME,
    SUPPORTED_MODEL_NAMES,
    BaseOpenAIAgent,
)
from llama_index.bridge.langchain import print_text
from llama_index.callbacks.base import CallbackManager
from llama_index.indices.base_retriever import BaseRetriever
from llama_index.llms.base import ChatMessage
from llama_index.llms.openai import OpenAI
from llama_index.prompts.prompts import QuestionAnswerPrompt
from llama_index.response.schema import RESPONSE_TYPE
from llama_index.schema import NodeWithScore
from llama_index.tools import BaseTool

# inspired by DEFAULT_QA_PROMPT_TMPL from llama_index/prompts/default_prompts.py
DEFAULT_QA_PROMPT_TMPL = (
    "Context information is below.\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Given the context information and not prior knowledge, "
    "either pick the corresponding tool or answer the function: {query_str}\n"
)
DEFAULT_QA_PROMPT = QuestionAnswerPrompt(DEFAULT_QA_PROMPT_TMPL)


class ContextRetrieverOpenAIAgent(BaseOpenAIAgent):
    """ContextRetriever OpenAI Agent.

    This agent performs retrieval from BaseRetriever before
    calling the LLM. Allows it to augment user message with context.

    NOTE: this is a beta feature, function interfaces might change.

    Args:
        tools (List[BaseTool]): A list of tools.
        retriever (BaseRetriever): A retriever.
        qa_prompt (Optional[QuestionAnswerPrompt]): A QA prompt.
        context_separator (str): A context separator.
        llm (Optional[OpenAI]): An LLM.
        chat_history (Optional[List[ChatMessage]]): A chat history.
        verbose (bool): Whether to print debug statements.
        max_function_calls (int): Maximum number of function calls.
        callback_manager (Optional[CallbackManager]): A callback manager.

    """

    def __init__(
        self,
        tools: List[BaseTool],
        retriever: BaseRetriever,
        qa_prompt: QuestionAnswerPrompt,
        context_separator: str,
        llm: OpenAI,
        chat_history: List[ChatMessage],
        verbose: bool = False,
        max_function_calls: int = DEFAULT_MAX_FUNCTION_CALLS,
        callback_manager: Optional[CallbackManager] = None,
    ) -> None:
        super().__init__(
            llm=llm,
            chat_history=chat_history,
            verbose=verbose,
            max_function_calls=max_function_calls,
            callback_manager=callback_manager,
        )
        self._tools = tools
        self._qa_prompt = qa_prompt
        self._retriever = retriever
        self._context_separator = context_separator

    @classmethod
    def from_tools_and_retriever(
        cls,
        tools: List[BaseTool],
        retriever: BaseRetriever,
        qa_prompt: Optional[QuestionAnswerPrompt] = None,
        context_separator: str = "\n",
        llm: Optional[OpenAI] = None,
        chat_history: Optional[List[ChatMessage]] = None,
        verbose: bool = False,
        max_function_calls: int = DEFAULT_MAX_FUNCTION_CALLS,
        callback_manager: Optional[CallbackManager] = None,
    ) -> "ContextRetrieverOpenAIAgent":
        """Create a ContextRetrieverOpenAIAgent from a retriever.

        Args:
            retriever (BaseRetriever): A retriever.
            qa_prompt (Optional[QuestionAnswerPrompt]): A QA prompt.
            context_separator (str): A context separator.
            llm (Optional[ChatOpenAI]): An LLM.
            chat_history (Optional[ChatMessageHistory]): A chat history.
            verbose (bool): Whether to print debug statements.
            max_function_calls (int): Maximum number of function calls.
            callback_manager (Optional[CallbackManager]): A callback manager.

        """
        qa_prompt = qa_prompt or DEFAULT_QA_PROMPT
        chat_history = chat_history or []
        llm = llm or OpenAI(model=DEFAULT_MODEL_NAME)
        if not isinstance(llm, OpenAI):
            raise ValueError("llm must be a OpenAI instance")

        if llm.model not in SUPPORTED_MODEL_NAMES:
            raise ValueError(
                f"Model name {llm.model} not supported. "
                f"Supported model names: {SUPPORTED_MODEL_NAMES}"
            )

        return cls(
            tools=tools,
            retriever=retriever,
            qa_prompt=qa_prompt,
            context_separator=context_separator,
            llm=llm,
            chat_history=chat_history,
            verbose=verbose,
            max_function_calls=max_function_calls,
            callback_manager=callback_manager,
        )

    def _get_tools(self, message: str) -> List[BaseTool]:
        """Get tools."""
        return self._tools

    def chat(
        self, message: str, chat_history: Optional[List[ChatMessage]] = None
    ) -> RESPONSE_TYPE:
        """Chat."""
        # augment user message
        retrieved_nodes_w_scores: List[NodeWithScore] = self._retriever.retrieve(
            message
        )
        retrieved_nodes = [node.node for node in retrieved_nodes_w_scores]
        retrieved_texts = [node.get_content() for node in retrieved_nodes]

        # format message
        context_str = self._context_separator.join(retrieved_texts)
        formatted_message = self._qa_prompt.format(
            context_str=context_str, query_str=message
        )
        if self._verbose:
            print_text(formatted_message + "\n", color="yellow")

        return super().chat(formatted_message, chat_history=chat_history)
