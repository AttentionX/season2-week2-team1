from openai_api import OpenAI_API, model
from dataclasses import dataclass
from typing import List, Callable
from tool_functions import get_google_results, extract_url
import openai
import json
from utils import generate_schema
from pprint import pprint
import prompts

openai_util = OpenAI_API()

@dataclass
class Tool:
    name: str
    description: str
    function: any
    
    
@dataclass
class ExecutionResult:
    function_name: str
    function_args: dict
    function_result: any
    
    
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


generation_tool = Tool(
    name="Generation",
    description="useful for when you want to generate text with ChatGPT",
    function=openai_util.chatgpt,
)



class Agent:
    """Agent"""
    def __init__(self):
        self.tools: List[Tool] = []
        self.add_tools(search_tool, url_extraction_tool, generation_tool)
        self.memory: Memory = None
        
    def _set_goal(self, goal: str):
        self.memory.goal = goal
        
    def add_tools(self, *tools):
        self.tools.extend(tools)
        
    def _find_tool(self, name):
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None
        
    def _generate_tool_descriptions(self):
        tool_descriptions = []
        for tool in self.tools:
            tool_descriptions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": generate_schema(tool.function),
            })
        return tool_descriptions

        
    def _get_previous_action(self):
        return {
            "previous_query": self.memory.previous_query,
            "previous_execution_result": self.memory.previous_execution_result.__dict__,
        }
        
        
    def use_tools(self):
        messages = [
            {"role":"user", "content":prompts.PLANNING_AGENT_PROMPT.format(goal=self.memory.goal, previous_action=self._get_previous_action())},
        ]
        query = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages).choices[0].message.content
        messages.append(
            {"role":"user", "content":prompts.TOOL_AGENT_PROMPT.format(query=query)}
        )
        functions = self._generate_tool_descriptions()
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages,
            functions=functions,
            function_call="auto",
        )
        response_message = response["choices"][0]["message"]
        pprint(response_message)
        if response_message.get("function_call"):
            function_name = response_message["function_call"]["name"]
            if not function_name:
                raise ValueError("No function name found")
            tool_to_use = self._find_tool(function_name)
            if not tool_to_use:
                raise ValueError(f"Could not find tool with name {function_name}")
            function_args = json.loads(response_message["function_call"]["arguments"])

            print(function_name, function_args)
            
            function_result = tool_to_use.function(**function_args)
        
        self.memory.previous_query = query
        self.memory.previous_execution_result = ExecutionResult(
            function_args=function_args,
            function_name=function_name,
            function_result=function_result,
        )
        
        return function_result
    
    def run(self):
        self.memory.goal = input("What do you wish to achieve?")

        while True:
            self.use_tools()
    
    

