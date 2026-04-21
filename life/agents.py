from crewai import Agent, LLM
from bandit_tool import bandit_scanner

# ── Ollama Local LLM Setup ───────────────────────
llm = LLM(
    model="ollama/llama3.2",
    base_url="http://localhost:11434"
)

# ── Agent 1: Security Agent ──────────────────────
security_agent = Agent(
    role="Python Security Reviewer",
    goal=(
        "Detect all security vulnerabilities in the submitted "
        "Python code. Focus on dangerous patterns, hardcoded "
        "passwords, unsafe imports, and injection risks."
    ),
    backstory=(
        "You are a senior cybersecurity expert with 10 years of "
        "experience in Python security auditing. You are supported "
        "by the Bandit static analysis tool which gives you "
        "deterministic rule-based findings. You never guess — "
        "you only report what Bandit confirms or what you are "
        "very confident about. You assign a confidence score "
        "between 0.0 and 1.0 to every finding you report."
    ),
    tools=[bandit_scanner],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=3
)

# ── Agent 2: Performance Agent ───────────────────
performance_agent = Agent(
    role="Python Performance Reviewer",
    goal=(
        "Detect all performance issues in the submitted Python "
        "code. Focus on slow loops, repeated computations, "
        "unnecessary memory usage, and inefficient patterns."
    ),
    backstory=(
        "You are a senior Python performance engineer who has "
        "optimized large-scale systems for top tech companies. "
        "You have a sharp eye for inefficient code patterns. "
        "You assign a confidence score between 0.0 and 1.0 "
        "to every finding you report."
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=3
)

# ── Agent 3: Logic Agent ─────────────────────────
logic_agent = Agent(
    role="Python Logic Reviewer",
    goal=(
        "Detect all logic errors in the submitted Python code. "
        "Focus on incorrect conditions, missing return statements, "
        "wrong variable usage, and broken program flow."
    ),
    backstory=(
        "You are a senior software engineer who specializes in "
        "finding subtle logic bugs that compilers and security "
        "tools miss. You think step by step through every function "
        "and condition. You assign a confidence score between "
        "0.0 and 1.0 to every finding you report."
    ),
    tools=[],
    llm=llm,
    verbose=True,
    allow_delegation=False,
    max_iter=3
)

from crewai import Crew, Process

crew = Crew(
    agents=[security_agent, performance_agent, logic_agent],
    process=Process.sequential,
    verbose=True
)