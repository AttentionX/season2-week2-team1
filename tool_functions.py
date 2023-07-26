import os
import requests
from termcolor import colored

from utils import save_as_json
from openai_api import OpenAI_API
import prompts
import time
from crawler import SimpleCrawler, crawl_and_rewrite
openai_util = OpenAI_API()

SERPAPI_ENDPOINT = "https://serpapi.com"
crawler = SimpleCrawler()


def get_google_results(query) -> str:
    params = {
        "q": query,
        "hl": "ko",
        "gl": "kr",
        "api_key": os.environ.get("SERPAPI_API_KEY"),
    }

    result = requests.get(SERPAPI_ENDPOINT + "/search", params=params).json()
    save_as_json(result, os.path.join("data", "google_results.json"))

    organic_results = result.pop("organic_results", None)
    if not organic_results:
        raise ValueError("No organic results found, please check your SerpApi account or query. \n{}".format(result))
    
    return str(organic_results)[:1000]


def extract_url(query, search_results) -> str:
    res = openai_util.chatgpt(prompts.URL_EXTRACTION_PROMPT.format(
        query=query,
        search_results=search_results
    ))
    
    return res
    
    
def crawl_and_write(query, url_link) -> str:
    result = crawl_and_rewrite(crawler, query, url_link)
    print(colored('글쓰기 결과: {}'.format(result), "green"))
    return result