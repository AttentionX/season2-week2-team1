TOOL_AGENT_PROMPT="""
You MUST use a tool to help the user.
User: {query}
"""

URL_EXTRACTION_PROMPT="""
Given a list of search results and initial user query,\
you are required to extract the most relevant URL.

You MUST not output any other text.
Only output the url.

Example output:
https://www.langchain.com

Initial user query:
{query}

Search results:
{search_results}

Now generate the URL:
"""


PLANNING_AGENT_PROMPT="""
You are required to plan and execute a sequence of actions to achieve a goal.
The ultimate goal is:
{goal}

Your previous action and corresponding result was as follows:
{previous_action}

What will you do next?
"""

