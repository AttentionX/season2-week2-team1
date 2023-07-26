import os
import openai
import tiktoken
import json
# from dotenv import load_dotenv

# load_dotenv()

# OpenAI API Key 세팅하기
openai.api_key = "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"

model = "gpt-3.5-turbo"
system_message = "You are a helpful assistant"
query = "Explain self-attention"

class OpenAI_API:
    def __init__(self, model=model, system_message=system_message):
        self.model = model
        self.system_message = system_message

    def chatgpt(self, query):
        messages = [
            {"role":"system", "content":self.system_message},
            {"role":"user", "content":query}
        ]
        response = openai.ChatCompletion.create(model=self.model, messages=messages).choices[0].message.content
        return response
    
    def function_call(self, query):
        messages = [
            {"role":"user", "content":query}
        ]
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-0613",
            messages=messages,
            functions=functions,
            function_call="auto",  # auto is default, but we'll be explicit
        )
        response_message = response["choices"][0]["message"]
        function_name = response_message["function_call"]["name"]
        function_args = json.loads(response_message["function_call"]["arguments"])

        

        return function_name, function_args
        
        
    @staticmethod
    def get_embedding(query):
        query = query.replace("\n", " ")
        return openai.Embedding.create(input = [query], model="text-embedding-ada-002")['data'][0]['embedding']
    
    def token_count(self, text):
        encoding = tiktoken.encoding_for_model(self.model)
        num_tokens = len(encoding.encode(text))
        return num_tokens
