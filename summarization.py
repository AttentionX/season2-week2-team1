import asyncio
from functools import partial
from queue import Queue
from threading import Thread

import openai

from prompts import TEXT_SUMMARIZATION_PROMPT


# Thread(target=lambda lp: (
#     asyncio.set_event_loop(lp),
#     openai_loop.run_forever()
# ), args=[openai_loop]).start()


async def ask_summarization_to_openai(text):
    content = TEXT_SUMMARIZATION_PROMPT.format(text=text)
    messages = [{"role": "user", "content": content}]
    task = asyncio.get_event_loop().run_in_executor(None, partial(
        openai.ChatCompletion.create,
        model='gpt-3.5-turbo',
        messages=messages
    ))
    response = (await task).choices[0].message.content.lower()
    print('got response from openai: {}'.format(response))
    return response


def generate_summary(text) -> str:
    queue = Queue()

    def thread_func(queue):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        queue.put(loop.run_until_complete(generate_summary_async(text)))

    Thread(target=thread_func, args=(queue,)).start()
    return queue.get()


async def generate_summary_async(text) -> str:
    input_chunks = _split_text(text)

    tasks = [asyncio.get_event_loop().create_task(ask_summarization_to_openai(t)) for t in input_chunks]
    summarize_result = await asyncio.gather(*tasks)

    return '\n'.join(summarize_result)


def _split_text(text):
    max_chunk_size = 800
    chunks = []
    current_chunk = ""
    for sentence in text.split("."):
        if len(current_chunk) + len(sentence) < max_chunk_size:
            current_chunk += sentence + "."
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence + "."
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


async def main():
    await generate_summary_async("hello world")


if __name__ == "__main__":
    # asyncio.get_event_loop().run_until_complete(main())
    generate_summary("hello world")
