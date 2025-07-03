import os

import requests
from dotenv import load_dotenv
from openai import OpenAI

from mcp_server import KaliToolsClient

MCP_URL = "http://localhost:5000/api/command"

load_dotenv()

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)

# Create a chat completion request
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system",
         "content": """
                    You are an expert cybersecurity assistant specialized in solving web-based CTF challenges. 
                    Carefully analyze the user's prompt and produce multiple potential step-by-step solutions before executing any commands.
                    
                    For each step, suggest a variety of potential commands (using tools such as curl, Hydra, gobuster, 
                    sqlmap, Burp Suite, wget, nmap, and Postman), explain the reasoning behind each suggested command,
                     and discuss why it might be helpful in progressing toward solving the challenge.
                    
                    Extract the suggested commands clearly (in separate code blocks), 
                    along with concise explanations of what each does. Do not execute or finalize any command until you have presented the
                     options and reasoning.
                    
                    Once you and the user agree on the final command(s) to execute,
                     produce the final command(s) that should be run and stop suggesting further commands. 
                     If you find the flag in the response at any point, report it immediately and stop suggesting further
                      commands, ask the user whether the flag is working.
"""},
        {"role": "user", "content": "Hello, how can I use OpenAI API in Python?"}
    ]
)

print("Response:\n", response.choices[0].message.content.strip())

# Print the response
print(response.choices[0].message.content)

# Initialize Kali Tools client
kali_client = KaliToolsClient("http://localhost:5000")

messages = [
    {"role": "system",
     "content": """You are an expert cybersecurity assistant specialized in solving web-based CTF challenges. 
                    Carefully analyze the user's prompt and produce multiple potential step-by-step solutions
                     before executing any commands. You have the power to use tools such as url, Hydra, gobuster, 
                    sqlmap, Burp Suite, wget, nmap, and Postman). So if the user asks you to execute a command check
                    which tool you can use for executing it. and then build the command to execute in a clear way so
                    that it can be sent to mcp server.Do not execute or finalize any command until
                     you have presented the options and reasoning.    Once you and the user agree on the final command(s) to execute,
                     produce the final command(s) that should be run and stop suggesting further commands. 
                     
                     
                    
                    Whenever the user expresses an intent to execute a tool or needs to interact with a server, do the following:
                    
                    1. Identify the type of tool they want to use (e.g., curl, gobuster, sqlmap, etc.).
                    2. Determine the *goal* of the execution (e.g., directory enumeration, GET request, brute force login).
                    3. Generate a clean, ready-to-run command in the appropriate syntax.
                    4. Return **only** the suggested command in a code block.
                    5. Do not execute the command — only suggest it.
                    6. Wait for confirmation from the user before any follow-up.
                    
                    Example triggers to watch for:
                    - "I want to test the website with curl"
                    - "Can I brute-force this login?"
                    - "Let's try directory fuzzing"
                    - "Can I run gobuster on this?"
                    - "curl the website 
                    - "Run this command "
                    Do not mention that you cannot execute codes if you are asked to execute it
"""},
    {"role": "user", "content": "Hello, how can I use OpenAI API in Python?"}
]

messages = []


def should_execute(response_text: str) -> bool:
    """
    Determines if the LLM is suggesting execution or active analysis steps.
    """
    trigger_phrases = [
        # Command-related phrases
        "run", "you should try", "execute", "use this command", "run this", "try this", "to solve this", "launch",

        # Developer tool suggestions
        "open the developer tools", "inspect the page", "inspect element", "go to the sources tab",
        "look at the console", "check the network tab", "check network activity", "inspect html",

        # Searching for flags manually
        "search for picoctf", "search for flag", "search the page", "look for hidden", "check html comments",
        "check javascript files", "check inline javascript", "check embedded scripts", "check hidden elements",

        # Resource-level suggestions
        "go to the sources tab", "view the html source", "review the page", "analyze the scripts",
        "check console messages", "reload the page and inspect", "inspect various aspects", "use your web browser"
    ]

    response_lower = response_text.lower()
    return any(phrase in response_lower for phrase in trigger_phrases)


def extract_all_commands_from_codeblocks(text: str) -> list[str]:
    """
    Extracts all shell commands from all ```bash ...``` or ```...``` code blocks.
    Returns a list of cleaned command strings.
    """
    import re
    matches = re.findall(r"```(?:bash)?\s*(.*?)\s*```", text, re.DOTALL)
    return [match.strip() for match in matches if match.strip()]


def send_to_mcp(command):
    payload = {"command": command}
    response = requests.post(MCP_URL, json=payload)
    response.raise_for_status()
    return response.json()  # expect JSON dict with stdout, etc.


def handle_possible_execution(response_text: str):
    """
    Checks if execution is needed, extracts all commands, and runs them via MCP server.
    Combines and returns all outputs.
    """
    if should_execute(response_text):
        commands = extract_all_commands_from_codeblocks(response_text)
        if commands:
            combined_results = []
            for idx, command in enumerate(commands, 1):
                print(f"\n🚀 Running command #{idx}:\n{command}")
                result = send_to_mcp(command)
                print(f"\n📥 Output from MCP for command #{idx}:\n", result)
                combined_results.append(result)
            return combined_results
        else:
            print("⚠️ No valid commands could be extracted.")
    else:
        print("✅ No command to execute.")

    return None


while True:
    # Step 1: Get CTF challenge from user
    user_prompt = input("\n🕵️‍♂️ Enter your CTF challenge description below 🧠🔍: ")
    messages.append({"role": "user", "content": user_prompt})

    # Step 2: Initial GPT response
    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    answer = response.choices[0].message.content.strip()
    print("\n🤖 GPT Response:\n", answer)
    messages.append({"role": "assistant", "content": answer})

    execution_result = handle_possible_execution(answer)
    if execution_result:
        # Step 4: Use a system prompt to explain the output
        system_prompt = {
            "role": "system",
            "content": (
                "You are an expert CTF assistant. The following is the output from running commands "
                "on a CTF challenge. Analyze it carefully and provide a clear, concise summary or extract the flag "
                "if possible. If no flag is present, explain what should be done next.\n\n"
                f"Command Output:\n{execution_result}"
            )
        }
        messages.append(system_prompt)

        # Step 5: Ask GPT to process the command output
        response = client.chat.completions.create(model="gpt-4o", messages=messages)
        followup = response.choices[0].message.content.strip()
        print("\n🧠 Follow-up Analysis:\n", followup)
        messages.append({"role": "assistant", "content": followup})

    # Step 3: Stop early if flag found
    # if "the flag is" in answer.lower() or "flag{" in answer.lower():
    #     print("\n✅ Flag found! Check if it is correct.\n")
    #     break

    # Step 4: Use GPT to extract only the executable commands
    # system_prompt = (
    #     "You are a web cybersecurity analyst. Analyze the following text to find executable commands "
    #     "based on the tools we have on our MCP Kali server. The tools are: curl, Hydra, gobuster, sqlmap, "
    #     "Burp Suite, wget, nmap, and Postman. List only executable commands you would send to the server. "
    #     "Each command should be standalone and properly formatted."
    # )

    # command_extraction_messages = [
    #     {"role": "system", "content": system_prompt},
    #     {"role": "user", "content": answer}
    # ]
    #
    # response = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=command_extraction_messages
    # )
    # extracted_commands = response.choices[0].message.content.strip()
    # print("\n📤 Extracted Commands to Send to MCP:\n", extracted_commands)

    # Step 5: Parse the commands
    # commands = re.findall(r"```(?:bash)?\n(.*?)```", extracted_commands, re.DOTALL)
    # if not commands:
    #     commands = re.findall(r"\b(?:curl|wget|nmap|gobuster|hydra|sqlmap)\s[^\n]+", extracted_commands)
    #
    # print("\n🧪 Commands Parsed:\n", "\n".join(commands))
    #
    # # Step 6: Execute the commands via MCP and combine results
    # combined_output = ""
    # for cmd in commands:
    #     print(f"\n▶️ Executing: {cmd}")
    #     result = kali_client.execute_command(cmd)
    #     print("\n📄 Result:\n", result)
    #     combined_output += f"\nOutput of `{cmd}`:\n{result}\n"

    # # Step 7: Use GPT to check if flag exists in output
    # flag_check_prompt = (
    #     "Here are the outputs of some web security commands executed on a CTF challenge. "
    #     "Check carefully if a flag is present in any of the outputs. If you find a flag, return it as: 'The flag is ...'"
    # )
    #
    # flag_check_messages = [
    #     {"role": "system", "content": flag_check_prompt},
    #     {"role": "user", "content": combined_output}
    # ]
    #
    # response = client.chat.completions.create(model="gpt-4o", messages=flag_check_messages)
    # flag_result = response.choices[0].message.content.strip()
    # print("\n🚩 Flag Check Result:\n", flag_result)

    # Step 8: If flag found, stop
    # if "the flag is" in flag_result.lower() or "flag{" in flag_result.lower():
    #     print("\n✅ Final Flag Found! 🎉")
    #     # break

    #
    # for cmd in commands:
    #     print(f"\n Executing: {cmd}")
    #     result = kali_client.execute_command(cmd)
    #     print("\n MCP Command Output:\n", result)
    #
    #     commands += f"\nOutput of `{cmd}`:\n{result}"

    # Optional: loop through and send each command to MCP server here

    # Extract bash commands from the GPT response
    # commands = re.findall(r"```bash\n(.*?)```", answer, re.DOTALL)
    # cleaned_commands = [cmd.strip() for cmd in commands if cmd.strip()]
    #
    # if not commands:
    #     print("\n No executable commands found in the response.")
    #     continue

    # combined_output = ""
    #

    # messages = [
    #     {"role": "system", "content": system_prompt},
    #     {"role": "user", "content": combined_output}
    # ]
    #
    # response = client.chat.completions.create(
    #     model="gpt-4o",
    #     messages=messages
    # )
    #
    # analysis = response.choices[0].message.content
    # print("\n🔎 Analysis Result:\n", analysis)
    #
    # if "flag{" in analysis.lower():
    #     print("\n ✅ Flag detected by analysis!")
