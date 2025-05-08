# %%
import datetime
import json
import os
import asyncio
import signal
from pathlib import Path
from typing import List, Union, Dict, Any
import nest_asyncio

nest_asyncio.apply()

from dotenv import load_dotenv

load_dotenv()

from opentelemetry import trace
from phoenix.otel import register  # Added for Arize Phoenix tracing

from browser_use import Agent
from browser_use.browser.browser import Browser, BrowserConfig
from browser_use.agent.gif import create_history_gif

from langchain_google_genai import ChatGoogleGenerativeAI
from google.ai.generativelanguage_v1beta.types import Tool as GenAITool
from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)


PROFILE_DIR = os.path.expanduser(
    "/Users/swarajraibagi/Documents/code/servicenow_apps/chrome_profile_dir"
)  # ← copy of "~/Library/Application Support/Google/Chrome"

# Command to start chrome window with debugging
# /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
#   --remote-debugging-port=9222 \
#   --user-data-dir=./chrome_profile_dir \
#   --profile-directory=Default

register(
    project_name="servicenow-browser-use",
    auto_instrument=True,
    endpoint="http://localhost:6006/v1/traces",
)
tracer = trace.get_tracer(__name__)


# %%
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash-preview-04-17")

PLANNER_TOOLS = [GenAITool(google_search={})]


class EnhancedChatGoogleGenerativeAI(ChatGoogleGenerativeAI):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    # Do not delete below ever
    def _mask_tool_call_and_output(
        self, input: List[Union[SystemMessage, HumanMessage, AIMessage, ToolMessage]]
    ):
        new_input_messages = []
        for message in input:

            new_message = message.model_copy(deep=True)

            if isinstance(new_message, AIMessage):
                if message.tool_calls:

                    new_message.content = f"""A tool call is predicted :

{json.dumps(message.tool_calls)}
                    """
                    new_message.tool_calls = []
            elif isinstance(new_message, ToolMessage):
                new_message = HumanMessage(
                    content=f"""The tool call was made, the result is presented below 

{new_message.content}                    
                    
"""
                )
            new_input_messages.append(new_message)
        return new_input_messages

    def invoke(self, input, **kwargs):
        new_input_messages = self._mask_tool_call_and_output(input)
        if "tools" not in kwargs:
            kwargs["tools"] = PLANNER_TOOLS
            return super().invoke(new_input_messages, **kwargs)
        else:
            return super().invoke(new_input_messages, **kwargs)

    async def ainvoke(self, input, **kwargs):
        new_input_messages = self._mask_tool_call_and_output(input)
        if "tools" not in kwargs:
            kwargs["tools"] = PLANNER_TOOLS
            return await super().ainvoke(new_input_messages, **kwargs)
        else:
            return await super().ainvoke(new_input_messages, **kwargs)


planner_llm = EnhancedChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
browser = Browser(
    config=BrowserConfig(cdp_url="http://localhost:9222", disable_security=True)
)


async def save_data_after_step(agent: Agent):
    # Get the output directory from the agent's settings
    output_dir = (
        os.path.dirname(agent.settings.generate_gif)
        if isinstance(agent.settings.generate_gif, str)
        else "agent_output"
    )
    os.makedirs(output_dir, exist_ok=True)

    # Save GIF for this step
    gif_path = os.path.join(output_dir, f"recording_step_{agent.state.n_steps}.gif")
    create_history_gif(
        task=agent.task, history=agent.state.history, output_path=gif_path
    )

    # Save history for this step
    history_path = os.path.join(output_dir, f"history_step_{agent.state.n_steps}.json")
    agent.save_history(history_path)

    # Also save a "latest" version that will be overwritten each time
    latest_path = os.path.join(output_dir, "latest_history.json")
    agent.save_history(latest_path)

    print(f"Saved data for step {agent.state.n_steps}")


# %%
TASK = """
ORIGINAL TASK:
Write a script that helps me test role based access for this catalog item Request Standard Keyboard 

This script should use GlideScript apis to achieve the following 
1. Get required sys_ids of the catalog item, admin role, test step configs that we shall use in script
2. Write any additonal one-off discovery scripts to run and get info that i didn't specify above but realised we need 
3. Write script that adds all necessary test shell/steps etc 
4. Navigate me to the new test so i can run it and validate.

CORE RULE : 
SCRIPT MODE : 
ONLY USE SCRIPTS - BACKGROUND PAGE, AVOID GOING TO UI BASED CONFIGURATION. IF YOU HAVE TO USE UI ONLY FOR DISCOVERY and INFORMATION GATHERING NOT FOR CONFIGURATION.
"""

COMMON_SERVICENOW_GUIDELINES = """
- After clicking "All" button and dropdown appearing, something may cause the dropdown to close, in this case you should avoid needlessly scrolling down and click the "All" button again to make the dropdown appear. Any search terms in dropdown will get reset everytime "All" is clicked.

ATF Specific Guidelines:
    - When creating tests, avoid using the "Impersonate" user feature, instead plan and execute using Create A User feature with the role/group you want to test with.  

Script Rules : 
    - User may ask you to work in script mode. This will involve using scripts for discovery eg finding sys_id of some specific thing, AND/OR they are asking for a script as the result that does read + write actions. In this mode you should bias towards writing for both purposes if asked.
    - You will be calling input_text action to add text to script. If you need to run multiple scripts follow these set of steps :
      1. You'll be on <host>.service-now.com/now/nav/ui/classic/params/target/sys.scripts.do and you'll use input_text action to add text to script.
      2. You'll click "Run script" button which shows you script output. You'll understand this output however which way 
      3. To write another script, just reload the page/tab with url `https://<host>.service-now.com/now/nav/ui/classic/params/target/sys.scripts.do` and it'll take you to script page with empty editor. 
    - DO NOT use input_text action without reloading the page or it'll append to previous script and cause syntax errors.
"""

EXTEND_SYSTEM_MESSAGE = """`
ServiceNow Specific Instructions:
- To navigate in servicenow you can either use the "All" button in the top left of the page, this is always available, once clicking this you are provided with a dropdown expandable list with a search bar at the top (Filter). You can add prefix based filters to narrow down or scroll and the click to decide which module you want to navigate to.
- Another way to navigate between recently used pages is by using the "History" button next to the "All" button at top left of the page.
- Avoid using the search bar at the top right of the page, it is not reliable and will almost never be useful.

Common Servicenow Guidelines : %s

""" % (
    COMMON_SERVICENOW_GUIDELINES
)

EXTEND_PLANNER_SYSTEM_MESSAGE = """
You are an expert ServiceNow AI Developer that uses the browser to implement servicenow implementation tasks.

Your main role in this task is to create one of the folliwing : 
1. UI MODE : a manaul UI action based plan + immediate next 4 or fewer steps. 
2. SCRIPT MODE : a script that does read + write actions and is used for both discovery, information gathering, and actual implementation. 

If Manual : 
The plan should be extremely detailed as the junior developer following your plan will require explicit UI position, text, button, layout description, known UI quirks etc. It should along with this detail provide an accurate set of steps to complete the implementation task.

If Script : 
The script should be extremely detailed as the junior developer following your plan will require steps at the granularity of script or subscript level.
One script can be for discovery, information gathering, or actual implementation.

You will be provided updates every 4 steps, feel free to perform any basic discovery as part of next immediate 4 steps if needed before running actual implementation steps.

Common Servicenow Guidelines : %s

""" % (
    COMMON_SERVICENOW_GUIDELINES
)

# %%


@tracer.start_as_current_span("run_browser_use_agent")
async def main(output_dir: str, resume_from: str = None):
    # If output dir doesn't exist, create it
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # If resuming from a history file, use the directory from that file
    # Otherwise create new output directories
    if resume_from:
        # Extract the parent directory from the resume file path
        output_dir = os.path.dirname(os.path.dirname(resume_from))
        print(f"Using existing output directory: {output_dir}")

    # Create subdirectories for conversation, recording, and history
    conversation_dir = os.path.join(output_dir, "conversation")
    recording_dir = os.path.join(output_dir, "recording")
    history_dir = os.path.join(output_dir, "history")

    os.makedirs(conversation_dir, exist_ok=True)
    os.makedirs(recording_dir, exist_ok=True)
    os.makedirs(history_dir, exist_ok=True)

    agent = Agent(
        task=TASK,
        llm=llm,
        planner_llm=planner_llm,
        browser=browser,
        # Every run gets a fresh context
        save_conversation_path=os.path.join(conversation_dir, "conversation"),
        extend_system_message=EXTEND_SYSTEM_MESSAGE,
        use_vision=True,
        use_vision_for_planner=True,
        max_input_tokens=900000,
        max_actions_per_step=20,
        generate_gif=os.path.join(recording_dir, "recording.gif"),
        planner_interval=4,
        extend_planner_system_message=EXTEND_PLANNER_SYSTEM_MESSAGE,
    )

    if resume_from:
        print(f"Resuming from history file: {resume_from}")
        # First load and rerun the history
        await agent.load_and_rerun(resume_from)
        print("History replay completed, continuing with new steps...")

    # Run the agent with our hook to save data after each step
    result = await agent.run(on_step_end=save_data_after_step)

    print(result)
    return result


if __name__ == "__main__":
    # Check if we should resume from a history file
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--resume", help="Path to history file to resume from", default=None
    )
    args = parser.parse_args()

    # Only create a new output directory if we're not resuming
    output_dir = (
        args.resume
        and os.path.dirname(os.path.dirname(args.resume))
        or f"run_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    asyncio.run(main(output_dir=output_dir, resume_from=args.resume))
