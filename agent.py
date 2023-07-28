from typing import List, Dict, Callable, Optional
from openai_api import OpenAI_API, model
from dataclasses import dataclass, asdict
from tool_functions import get_google_results, extract_url, crawl_and_write
import openai
import json
from utils import generate_schema
import logger
import prompts
from termcolor import colored

openai_util = OpenAI_API()


@dataclass
class Tool:
    name: str
    description: str
    function: Callable


@dataclass
class ExecutionResult:
    function_name: str
    function_args: dict
    function_result: str


@dataclass
class Memory:
    goal: str
    previous_query: str
    previous_execution_result: ExecutionResult


search_tool = Tool(
    name="Search",
    description="useful for when you want to search something",
    function=get_google_results,
)

url_extraction_tool = Tool(
    name="Extract_Url",
    description="useful for when you want to extract url from search results",
    function=extract_url,
)

crawl_and_write_tool = Tool(
    name="Crawl_And_Write",
    description="useful for when you want to crawl url and write information",
    function=crawl_and_write,
)

generation_tool = Tool(
    name="Generation",
    description="useful for when you want to generate text with ChatGPT",
    function=openai_util.chatgpt,
)


class Agent:
    """Agent"""

    def __init__(self):
        self.tools: List[Tool] = []
        self._add_tools(search_tool, url_extraction_tool, crawl_and_write_tool, generation_tool)
        self.memory: Memory = Memory(goal=None, previous_query=None, previous_execution_result=None)

    def _set_goal(self, goal: str) -> None:
        self.memory.goal = goal

    def _add_tools(self, *tools) -> None:
        self.tools.extend(tools)

    def _find_tool(self, name) -> Optional[Tool]:
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    def _generate_tool_descriptions(self) -> List[Dict]:
        tool_descriptions = []
        for tool in self.tools:
            tool_descriptions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": generate_schema(tool.function),
            })
        return tool_descriptions

    def _get_previous_action(self) -> Dict[str, str]:
        if self.memory.previous_query is None:
            return "None"

        return {
            "previous_query": self.memory.previous_query,
            "previous_execution_result": self.memory.previous_execution_result,
        }

    def use_tools(self) -> None:
        messages = [
            {"role": "user", "content": prompts.PLANNING_AGENT_PROMPT.format(goal=self.memory.goal,
                                                                             previous_action=self._get_previous_action(),
                                                                             tools=self._generate_tool_descriptions())},
        ]
        logger.thought("What should I do next?")
        logger.memory(json.dumps(asdict(self.memory)))
        logger.system("Thinking...")
        query = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages).choices[0].message.content
        self.memory.previous_query = query
        logger.thought(query)
        messages.append(
            {"role": "user", "content": prompts.TOOL_AGENT_PROMPT.format(query=query)}
        )
        functions = self._generate_tool_descriptions()
        logger.system("Thinking...")
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages,
            functions=functions,
            function_call="auto",
        )
        response_message = response["choices"][0]["message"]
        logger.system(response_message)
        if "function_call" in response_message:
            function_name = response_message["function_call"]["name"]
            if not function_name:
                logger.error("No function name found")
            tool_to_use = self._find_tool(function_name)
            if not tool_to_use:
                logger.error(f"Could not find tool with name {function_name}")
            function_args = json.loads(response_message["function_call"]["arguments"])

            logger.action(function_name + ": " + str(function_args))

            function_result = tool_to_use.function(**function_args)

            self.memory.previous_execution_result = ExecutionResult(
                function_args=function_args,
                function_name=function_name,
                function_result=function_result[:1000],
            )
        else:
            self.memory.previous_execution_result = ExecutionResult(
                function_args="None",
                function_name="Think",
                function_result=response_message["content"][:1000],
            )

    def run(self):
        print(colored("What goal should I achieve?\n", "green"))
        goal = input(">> ")
        self._set_goal(goal)

        while True:
            self.use_tools()
            # fixme temporal stop condition
            if self.memory.previous_execution_result.function_name == "Crawl_And_Write":
                print(colored("seems i've done my job nicely!\n", "blue"))
                return
