import os
import requests
from utils import save_as_json
from agent import openai_util
import prompts

SERPAPI_ENDPOINT = "https://serpapi.com"

def get_google_results(query):
    params = {
        "q": query,
        "hl": "ko",
        "gl": "kr",
        "api_key": "b6730508cb34210878b5a2919cad53d7e1c26db35fdb2d373d4827a18aa304f8",
    }

    result = requests.get(SERPAPI_ENDPOINT + "/search", params=params).json()
    print(result)
    save_as_json(result, os.path.join("data", "google_results.json"))

    organic_results = result["organic_results"]
    
    return organic_results


def extract_url(query, search_results):
    res = openai_util.chatgpt(prompts.URL_EXTRACTION_PROMPT.format(
        query=query,
        search_results=search_results
    ))
    print(res)
    
    return res
    