import re
import os
from openai import OpenAI
from dotenv import load_dotenv
from mcp_server import KaliToolsClient

load_dotenv()  # load .env variables

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
                     If you find the flag in the response at any point, report it immediately and stop suggesting further commands.
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
     "content": """
                    You are an expert cybersecurity assistant specialized in solving web-based CTF challenges. 
                    Carefully analyze the user's prompt and produce multiple potential step-by-step solutions
                     before executing any commands.

                    For each step, suggest a variety of potential commands (using tools such as curl, Hydra, gobuster, 
                    sqlmap, Burp Suite, wget, nmap, and Postman), explain the reasoning behind each suggested command,
                     and discuss why it might be helpful in progressing toward solving the challenge.

                    Extract the suggested commands clearly (in separate code blocks), 
                    along with concise explanations of what each does. Do not execute or finalize any command until
                     you have presented the options and reasoning.

                    Once you and the user agree on the final command(s) to execute,
                     produce the final command(s) that should be run and stop suggesting further commands. 
                     If you find the flag in the response at any point, report it immediately and stop suggesting
                    further commands.
"""},
    {"role": "user", "content": "Hello, how can I use OpenAI API in Python?"}
]

while True:
    user_prompt = input("\nEnter CTF challenge description: ")
    messages.append({"role": "user", "content": user_prompt})

    # Send prompt to ChatGPT
    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    answer = response.choices[0].message.content.strip()

    print("\n🤖 GPT Response:\n", answer)
    messages.append({"role": "assistant", "content": answer})

    # Stop if flag found
    if "The flag is" in answer or "flag{" in answer.lower():
        print("\n✅ Flag found! Stopping.")
        break

    # Extract bash commands from the GPT response
    commands = re.findall(r"```bash\n(.*?)```", answer, re.DOTALL)
    cleaned_commands = [cmd.strip() for cmd in commands if cmd.strip()]

    if not commands:
        print("\n No executable commands found in the response.")
        continue

    system_prompt = (
        "You are a cybersecurity assistant helping to analyze the combined output of multiple commands "
        "executed during a CTF challenge. Examine the following text carefully and determine if it contains "
        "any flags (typically formatted like flag{...}). If you find a flag, clearly announce it by printing "
        "‘Flag found:’ followed by the flag. If no flag is found, say so clearly."
    )

    combined_output = ""

    for cmd in cleaned_commands:
        print(f"\n Executing: {cmd}")
        result = kali_client.execute_command(cmd)
        print("\n🖥️ MCP Command Output:\n", result)

        combined_output += f"\nOutput of `{cmd}`:\n{result}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": combined_output}
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages
    )

    analysis = response.choices[0].message.content
    print("\n🔎 Analysis Result:\n", analysis)

    if "flag{" in analysis.lower():
        print("\n ✅ Flag detected by analysis!")
