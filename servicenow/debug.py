import asyncio
import json
import os

from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.browser.context import BrowserContext, BrowserContextConfig
from browser_use.dom.service import DomService


def find_iframes_in_dom_tree(element_node, path=""):
    found_iframes = []

    # Check if current node is an iframe
    if element_node.tag_name == "iframe":
        found_iframes.append(
            {
                "dom_node": element_node,
                "path": path,
                "attributes": element_node.attributes,
            }
        )

    # Recursively check children
    for i, child in enumerate(element_node.children):
        if hasattr(child, "tag_name"):  # Only process element nodes, not text nodes
            child_path = f"{path} > {child.tag_name}" if path else child.tag_name
            found_iframes.extend(find_iframes_in_dom_tree(child, child_path))

    return found_iframes


async def debug_dom_and_selectors(url, target_selector=None):
    """
    Debug script to analyze DOM structure and test selectors with a focus on iframe detection.

    Args:
        url: The URL to navigate to
        target_selector: Optional specific selector to test
    """
    # Initialize browser with debugging options
    browser = Browser(config=BrowserConfig(cdp_url="http://localhost:9222"))

    # Configure context with iframe support
    context = BrowserContext(
        browser=browser,
        config=BrowserContextConfig(
            disable_security=True,  # Enable cross-origin iframe access
            include_dynamic_attributes=True,  # Include all attributes in selectors
            wait_for_network_idle_page_load_time=5,  # Ensure page is fully loaded
        ),
    )

    try:
        async with context as ctx:
            page = await ctx.get_current_page()
            await page.goto(url)
            await asyncio.sleep(3)  # Wait for 3 seconds
            # Get all iframes on the page
            # iframes = page.locator('iframe')

            # # Get count of iframes
            # iframe_count = await iframes.count()
            # print(f"Found {iframe_count} iframes on the page")

            # # Print details for each iframe
            # for i in range(iframe_count):
            #     iframe = iframes.nth(i)
            #     print(await iframe.content())

            dom_service = DomService(page)
            # iframe_urls = await dom_service.get_cross_origin_iframes()
            # print(f"Found {len(iframe_urls)} cross-origin iframes")
            els = await dom_service.get_clickable_elements()
            elt_tree, els_map = els.element_tree, els.selector_map
            target_elt = els_map[28]
            print(type(target_elt), target_elt)
            print(target_elt.parent)

            # print(f"\n{'='*50}\nAnalyzing page: {url}\n{'='*50}")

            # # 1. Get DOM state from DOM analyzer
            # print("\nGetting DOM state from analyzer...")
            # dom_state = await ctx.get_state(cache_clickable_elements_hashes=True)

            # # 2. Detect iframes on the page
            # print("\nExtracting iframes from DOM state tree...")
            # dom_iframes = find_iframes_in_dom_tree(dom_state.element_tree)
            # print(f"Found {len(dom_iframes)} iframes in DOM state tree")

            # iframe_details = []
            # for i, iframe in enumerate(dom_iframes):
            #     print(f"  DOM Iframe #{i}: Path={iframe['path']}")
            #     print(f"  Attributes: {iframe['attributes']}")

            #     # Add to iframe_details if not already there
            #     iframe_node = iframe['dom_node']
            #     iframe_info = {
            #         'index': i,
            #         'id': iframe_node.attributes.get('id', f'dom_iframe_{i}'),
            #         'src': iframe_node.attributes.get('src', 'unknown'),
            #         'selector': iframe['path'],
            #         'from_dom_tree': True
            #     }
            #     iframe_details.append(iframe_info)

            # # 4. Test DOM analyzer's selector map
            # print("\nTesting DOM analyzer's selector map...")
            # selector_map = dom_state.selector_map
            # print(f"DOM analyzer found {len(selector_map)} interactive elements")

            # # 5. Test specific selector if provided
            # if target_selector:
            #     print(f"\nTesting specific selector: {target_selector}")

            #     # First try direct selector
            #     try:
            #         element = await page.query_selector(target_selector)
            #         if element:
            #             print(f"✅ Direct selector found element")
            #             is_visible = await element.is_visible()
            #             print(f"   Element visible: {is_visible}")
            #         else:
            #             print(f"❌ Direct selector found no element")
            #     except Exception as e:
            #         print(f"❌ Error with direct selector: {str(e)}")

            #     # Try with iframe context
            #     for iframe_info in iframe_details:
            #         print(f"\nTrying selector in iframe #{iframe_info['index']} ({iframe_info['id']})")
            #         try:
            #             frame_locator = page.frame_locator(f"iframe#{iframe_info['id']}" if iframe_info['id'].startswith('unnamed_iframe_') else f"iframe[id='{iframe_info['id']}']")
            #             element = frame_locator.locator(target_selector)
            #             count = await element.count()
            #             if count > 0:
            #                 print(f"✅ Found {count} elements in iframe using selector")
            #                 is_visible = await element.is_visible()
            #                 print(f"   Element visible: {is_visible}")
            #             else:
            #                 print(f"❌ No elements found in this iframe")
            #         except Exception as e:
            #             print(f"❌ Error with iframe selector: {str(e)}")

            # # 6. Test a sample of elements from the selector map
            # print("\nTesting sample elements from DOM analyzer's selector map...")
            # sample_size = min(5, len(selector_map))
            # for i, (index, element_node) in enumerate(list(selector_map.items())[:sample_size]):
            #     print(f"\nTesting element #{index}: {element_node.tag_name}")

            #     # Get the enhanced CSS selector
            #     css_selector = ctx._enhanced_css_selector_for_element(element_node)
            #     print(f"CSS Selector: {css_selector}")

            #     # Check if element has iframe parents
            #     has_iframe_parent = False
            #     current = element_node
            #     iframe_path = []
            #     while current.parent is not None:
            #         if current.parent.tag_name == 'iframe':
            #             has_iframe_parent = True
            #             iframe_path.append(current.parent)
            #         current = current.parent

            #     if has_iframe_parent:
            #         print(f"⚠️ Element has iframe parent(s)")
            #         for iframe in iframe_path:
            #             print(f"  Iframe: {iframe.tag_name} (xpath: {iframe.xpath})")

            #     # Try to locate the element directly
            #     try:
            #         element = await page.query_selector(css_selector)
            #         if element:
            #             print(f"✅ Direct selector found element")
            #         else:
            #             print(f"❌ Direct selector found no element")

            #             # If element has iframe parent, try with frame_locator
            #             if has_iframe_parent:
            #                 print("  Trying with frame_locator...")
            #                 for iframe_info in iframe_details:
            #                     try:
            #                         frame_locator = page.frame_locator(f"iframe#{iframe_info['id']}" if iframe_info['id'].startswith('unnamed_iframe_') else f"iframe[id='{iframe_info['id']}']")
            #                         element = frame_locator.locator(css_selector)
            #                         count = await element.count()
            #                         if count > 0:
            #                             print(f"  ✅ Found {count} elements in iframe #{iframe_info['index']}")
            #                         else:
            #                             print(f"  ❌ No elements found in iframe #{iframe_info['index']}")
            #                     except Exception as e:
            #                         print(f"  ❌ Error with iframe selector: {str(e)}")
            #     except Exception as e:
            #         print(f"❌ Error with selector: {str(e)}")

            # # Add this after you've found iframes in the DOM state tree
            # print("\nTesting selector with frame prefixes...")
            # test_selector = target_selector
            # test_text = '123'

            # # Iterate over frames found in DOM state
            # for i, iframe in enumerate(dom_iframes):
            #     iframe_node = iframe['dom_node']
            #     print(f"\nTesting in iframe #{i}:")

            #     try:
            #         # Get iframe selector
            #         iframe_selector = ctx._enhanced_css_selector_for_element(iframe_node)
            #         print(f"  Iframe selector: {iframe_selector}")

            #         # Create frame locator and try to find element
            #         frame_locator = page.frame_locator(iframe_selector)
            #         element = frame_locator.locator(test_selector)

            #         # Check if element exists
            #         count = await element.count()
            #         if count > 0:
            #             print(f"  ✅ Found {count} matching elements in iframe")

            #             # Try to fill text
            #             try:
            #                 await element.fill(test_text)
            #                 print(f"  ✅ Successfully filled text: '{test_text}'")
            #             except Exception as e:
            #                 print(f"  ❌ Failed to fill text: {str(e)}")
            #         else:
            #             print(f"  ❌ No elements found with selector: {test_selector}")
            #     except Exception as e:
            #         print(f"  ❌ Error testing iframe: {str(e)}")

            # # 7. Get page structure for debugging
            # print("\nGetting page structure (including iframes)...")
            # structure = await ctx.get_page_structure()

            # # Save debug info to files
            # os.makedirs('./debug_output', exist_ok=True)

            # with open('./debug_output/dom_state.json', 'w') as f:
            #     json.dump(dom_state.element_tree.__json__(), f, indent=2)

            # with open('./debug_output/iframe_details.json', 'w') as f:
            #     json.dump(iframe_details, f, indent=2)

            # with open('./debug_output/page_structure.txt', 'w') as f:
            #     f.write(structure)

            # print("\nDebug information saved to ./debug_output/")
            # print("- dom_state.json: DOM analyzer's element tree")
            # print("- iframe_details.json: Details about iframes on the page")
            # print("- page_structure.txt: Hierarchical page structure")

            # input("\nPress Enter to close the browser...")

    finally:
        await browser.close()


async def main():
    url = "https://dev221282.service-now.com/now/nav/ui/classic/params/target/sys.scripts.modern.do"
    target_selector = 'html > body > form > div:nth-of-type(1) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(2) > div:nth-of-type(1) > div > div > div:nth-of-type(1) > textarea.inputarea.monaco-mouse-cursor-text[autocomplete="off"][aria-label="Editor content;Press Alt+F1 for Accessibility Options."][role="textbox"]'
    if not target_selector:
        target_selector = None

    await debug_dom_and_selectors(url, target_selector)


if __name__ == "__main__":
    asyncio.run(main())
