import os
import os
import time
from sys import platform
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

import openai
from playwright.sync_api import Browser, CDPSession, Page

from prompts import TEXT_SUMMARIZATION_PROMPT, BOOK_WRITING_PROMPT
from summarization import generate_summary

black_listed_elements: Set[str] = {
    "html",
    "head",
    "title",
    "meta",
    "iframe",
    "body",
    "script",
    "style",
    "path",
    "svg",
    "br",
    "::marker",
    "img"
}


## crawler class
class SimpleCrawler:
    def __init__(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "Could not import playwright python package. "
                "Please install it with `pip install playwright`."
            )
        self.browser: Browser = (
            sync_playwright().start().chromium.launch(headless=True)
        )
        self.page: Page = self.browser.new_page()
        self.page.set_viewport_size({"width": 1280, "height": 1080})
        self.client: CDPSession

    def go_to_page(self, url: str) -> None:
        self.page.goto(url=url if "://" in url else "http://" + url)
        self.client = self.page.context.new_cdp_session(self.page)

    def _crawl(self) -> List[str]:
        page = self.page
        start = time.time()

        page_state_as_text = []

        device_pixel_ratio: float = page.evaluate("window.devicePixelRatio")
        if platform == "darwin" and device_pixel_ratio == 1:  # lies
            device_pixel_ratio = 2

        win_upper_bound: float = page.evaluate("window.pageYOffset")
        win_left_bound: float = page.evaluate("window.pageXOffset")
        win_width: float = page.evaluate("window.screen.width")
        win_height: float = page.evaluate("window.screen.height")
        win_right_bound: float = win_left_bound + win_width
        win_lower_bound: float = win_upper_bound + win_height

        # 		percentage_progress_start = (win_upper_bound / document_scroll_height) * 100
        # 		percentage_progress_end = (
        # 			(win_height + win_upper_bound) / document_scroll_height
        # 		) * 100
        percentage_progress_start = 1
        percentage_progress_end = 2

        page_state_as_text.append(
            {
                "x": 0,
                "y": 0,
                "text": "[scrollbar {:0.2f}-{:0.2f}%]".format(
                    round(percentage_progress_start, 2), round(percentage_progress_end)
                ),
            }
        )

        tree = self.client.send(
            "DOMSnapshot.captureSnapshot",
            {"computedStyles": [], "includeDOMRects": True, "includePaintOrder": True},
        )
        strings: Dict[int, str] = tree["strings"]
        document: Dict[str, Any] = tree["documents"][0]
        nodes: Dict[str, Any] = document["nodes"]
        backend_node_id: Dict[int, int] = nodes["backendNodeId"]
        attributes: Dict[int, Dict[int, Any]] = nodes["attributes"]
        node_value: Dict[int, int] = nodes["nodeValue"]
        parent: Dict[int, int] = nodes["parentIndex"]
        node_names: Dict[int, int] = nodes["nodeName"]
        is_clickable: Set[int] = set(nodes["isClickable"]["index"])

        input_value: Dict[str, Any] = nodes["inputValue"]
        input_value_index: List[int] = input_value["index"]
        input_value_values: List[int] = input_value["value"]

        layout: Dict[str, Any] = document["layout"]
        layout_node_index: List[int] = layout["nodeIndex"]
        bounds: Dict[int, List[float]] = layout["bounds"]

        cursor: int = 0

        child_nodes: Dict[str, List[Dict[str, Any]]] = {}
        elements_in_view_port: List = []

        anchor_ancestry: Dict[str, Tuple[bool, Optional[int]]] = {"-1": (False, None)}
        button_ancestry: Dict[str, Tuple[bool, Optional[int]]] = {"-1": (False, None)}

        def convert_name(
                node_name: Optional[str], has_click_handler: Optional[bool]
        ) -> str:
            if node_name == "a":
                return "link"
            if node_name == "input":
                return "input"
            if node_name == "img":
                return "img"
            if (
                    node_name == "button" or has_click_handler
            ):  # found pages that needed this quirk
                return "button"
            else:
                return "text"

        def find_attributes(
                attributes: Dict[int, Any], keys: List[str]
        ) -> Dict[str, str]:
            values = {}

            for [key_index, value_index] in zip(*(iter(attributes),) * 2):
                if value_index < 0:
                    continue
                key = strings[key_index]
                value = strings[value_index]

                if key in keys:
                    values[key] = value
                    keys.remove(key)

                    if not keys:
                        return values

            return values

        def add_to_hash_tree(
                hash_tree: Dict[str, Tuple[bool, Optional[int]]],
                tag: str,
                node_id: int,
                node_name: Optional[str],
                parent_id: int,
        ) -> Tuple[bool, Optional[int]]:
            parent_id_str = str(parent_id)
            if not parent_id_str in hash_tree:
                parent_name = strings[node_names[parent_id]].lower()
                grand_parent_id = parent[parent_id]

                add_to_hash_tree(
                    hash_tree, tag, parent_id, parent_name, grand_parent_id
                )

            is_parent_desc_anchor, anchor_id = hash_tree[parent_id_str]

            # even if the anchor is nested in another anchor, we set the "root" for all descendants to be ::Self
            if node_name == tag:
                value: Tuple[bool, Optional[int]] = (True, node_id)
            elif (
                    is_parent_desc_anchor
            ):  # reuse the parent's anchor_id (which could be much higher in the tree)
                value = (True, anchor_id)
            else:
                value = (
                    False,
                    None,
                )  # not a descendant of an anchor, most likely it will become text, an interactive element or discarded

            hash_tree[str(node_id)] = value

            return value

        for index, node_name_index in enumerate(node_names):
            node_parent = parent[index]
            node_name: Optional[str] = strings[node_name_index].lower()

            is_ancestor_of_anchor, anchor_id = add_to_hash_tree(
                anchor_ancestry, "a", index, node_name, node_parent
            )

            is_ancestor_of_button, button_id = add_to_hash_tree(
                button_ancestry, "button", index, node_name, node_parent
            )

            try:
                cursor = layout_node_index.index(
                    index
                )  # todo replace this with proper cursoring, ignoring the fact this is O(n^2) for the moment
            except:
                continue

            if node_name in black_listed_elements:
                continue

            [x, y, width, height] = bounds[cursor]
            x /= device_pixel_ratio
            y /= device_pixel_ratio
            width /= device_pixel_ratio
            height /= device_pixel_ratio

            elem_left_bound = x
            elem_top_bound = y
            elem_right_bound = x + width
            elem_lower_bound = y + height

            partially_is_in_viewport = (
                    elem_left_bound < win_right_bound
                    and elem_right_bound >= win_left_bound
                    and elem_top_bound < win_lower_bound
                    and elem_lower_bound >= win_upper_bound
            )

            if not partially_is_in_viewport:
                continue

            meta_data: List[str] = []

            # inefficient to grab the same set of keys for kinds of objects, but it's fine for now
            element_attributes = find_attributes(
                attributes[index], ["type", "placeholder", "aria-label", "title", "alt"]
            )

            ancestor_exception = is_ancestor_of_anchor or is_ancestor_of_button
            ancestor_node_key = (
                None
                if not ancestor_exception
                else str(anchor_id)
                if is_ancestor_of_anchor
                else str(button_id)
            )
            ancestor_node = (
                None
                if not ancestor_exception
                else child_nodes.setdefault(str(ancestor_node_key), [])
            )

            if node_name == "#text" and ancestor_exception and ancestor_node:
                text = strings[node_value[index]]
                if text == "|" or text == "•":
                    continue
                ancestor_node.append({"type": "type", "value": text})
            else:
                if (
                        node_name == "input" and element_attributes.get("type") == "submit"
                ) or node_name == "button":
                    node_name = "button"
                    element_attributes.pop(
                        "type", None
                    )  # prevent [button ... (button)..]

                for key in element_attributes:
                    if ancestor_exception and ancestor_node:
                        ancestor_node.append(
                            {
                                "type": "attribute",
                                "key": key,
                                "value": element_attributes[key],
                            }
                        )
                    else:
                        meta_data.append(element_attributes[key])

            element_node_value = None

            if node_value[index] >= 0:
                element_node_value = strings[node_value[index]]
                if (
                        element_node_value == "|"
                ):  # commonly used as a separator, does not add much context - lets save ourselves some token space
                    continue
            elif (
                    node_name == "input"
                    and index in input_value_index
                    and element_node_value is None
            ):
                node_input_text_index = input_value_index.index(index)
                text_index = input_value_values[node_input_text_index]
                if node_input_text_index >= 0 and text_index >= 0:
                    element_node_value = strings[text_index]

            # remove redundant elements
            if ancestor_exception and (node_name != "a" and node_name != "button"):
                continue

            elements_in_view_port.append(
                {
                    "node_index": str(index),
                    "backend_node_id": backend_node_id[index],
                    "node_name": node_name,
                    "node_value": element_node_value,
                    "node_meta": meta_data,
                    "is_clickable": index in is_clickable,
                    "origin_x": int(x),
                    "origin_y": int(y),
                    "center_x": int(x + (width / 2)),
                    "center_y": int(y + (height / 2)),
                }
            )

        # let filter further to remove anything that does not hold any text nor has click handlers + merge text from leaf#text nodes with the parent
        elements_of_interest = []
        id_counter = 0

        for element in elements_in_view_port:
            node_index = element.get("node_index")
            node_name = element.get("node_name")
            element_node_value = element.get("node_value")
            node_is_clickable = element.get("is_clickable")
            node_meta_data: Optional[List[str]] = element.get("node_meta")

            inner_text = f"{element_node_value} " if element_node_value else ""
            meta = ""

            if node_index in child_nodes:
                for child in child_nodes[node_index]:
                    entry_type = child.get("type")
                    entry_value = child.get("value")

                    if entry_type == "attribute" and node_meta_data:
                        entry_key = child.get("key")
                        node_meta_data.append(f'{entry_key}="{entry_value}"')
                    else:
                        inner_text += f"{entry_value} "

            if node_meta_data:
                meta_string = " ".join(node_meta_data)
                meta = f" {meta_string}"

            if inner_text != "":
                inner_text = f"{inner_text.strip()}"

            converted_node_name = convert_name(node_name, node_is_clickable)

            # not very elegant, more like a placeholder
            if (
                    (converted_node_name != "button" or meta == "")
                    and converted_node_name != "link"
                    and converted_node_name != "input"
                    and converted_node_name != "img"
                    and converted_node_name != "textarea"
            ) and inner_text.strip() == "":
                continue

            if inner_text != "":
                elements_of_interest.append(
                    f"""<{converted_node_name} id={id_counter}{meta}>{inner_text}</{converted_node_name}>"""
                )
            else:
                elements_of_interest.append(
                    f"""<{converted_node_name} id={id_counter}{meta}/>"""
                )
            id_counter += 1

        print("Parsing time: {:0.2f} seconds".format(time.time() - start))
        return elements_of_interest

    def crawl(self) -> str:
        import re
        res = ''
        text_list = self._crawl()
        for t in text_list:
            if 'text' in t and (match := re.search(r'<text id=\d+>(.*?)<\/text>', t)):
                res += match.group(1) + '\n'
            elif 'link' in t and (match := re.search(r'<link id=\d+ (.*?)\/>', t)):
                res += match.group(1) + '\n'
        return res


def crawl_and_rewrite(crawler, query, url_link: str) -> str:
    crawler.go_to_page(url_link)
    crawl_result = crawler.crawl()
    # If data/ directory does not exist, create it
    if not os.path.exists('data'):
        os.makedirs('data')
    with open('data/crawling_result_query_{}.txt'.format(query), 'w') as f:
        f.write(crawl_result)
        print('saved crawling result to crawling_result_query_{}.txt'.format(query))
    summarization = generate_summary(crawl_result)
    messages = [{"role": "user", "content": BOOK_WRITING_PROMPT.format(summarization=summarization)}]
    response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages).choices[0].message.content.lower()
    # print('got response from openai: \n {}'.format(response))
    with open("data/book_{}.txt".format(query), 'a') as f:
        f.write(response)
    return response


if __name__ == "__main__":
    crawler = SimpleCrawler()
    url_link = "https://ko.wikipedia.org/wiki/%EC%98%81%ED%99%94"
    result = crawl_and_rewrite(crawler, "test", url_link)
    print('글쓰기 결과: {}'.format(result))
