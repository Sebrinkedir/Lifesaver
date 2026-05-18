from crewai import Agent, LLM
from bandit_tool import bandit_scanner

llm_security = LLM(
    model="ollama/llama3.1:8b",
    base_url="http://localhost:11434",
    temperature=0.1
)

llm_performance = LLM(
    model="ollama/gemma3:4b",
    base_url="http://localhost:11434",
    temperature=0.1
)

llm_logic = LLM(
    model="ollama/deepseek-r1:7b",
    base_url="http://localhost:11434",
    temperature=0.1
)

security_agent = Agent(
    role="Senior Security Auditor",
    goal=(
        "Find ALL security vulnerabilities in the submitted code.\n"
        "For Python code use BanditSecurityScanner tool first.\n"
        "For other languages use your own expertise.\n\n"
        "Report each finding in this EXACT format:\n"
        "ISSUE: [description]\n"
        "SEVERITY: HIGH or MEDIUM or LOW\n"
        "CONFIDENCE: [0.0 to 1.0]\n"
        "LINE: [number]\n"
        "REASON: [why dangerous]\n\n"
        "If nothing found: NO SECURITY ISSUES FOUND"
    ),
    backstory=(
        "You are a world-class cybersecurity expert with 10 years of experience "
        "auditing code in Python, JavaScript, Java, PHP, C++, C#, Go and Ruby. "
        "You use BanditSecurityScanner for Python and your expertise for other languages. "
        "You never miss a security vulnerability."
    ),
    tools=[bandit_scanner],
    llm=llm_security,
    verbose=False,
    allow_delegation=False,
    max_iter=1,
    max_rpm=10
)

performance_agent = Agent(
    role="Senior Performance Engineer",
    goal=(
        "Find ONLY performance and efficiency issues in the submitted code.\n"
        "Do NOT report security issues — only performance problems.\n\n"
        "Report each finding in this EXACT format:\n"
        "ISSUE: [description]\n"
        "SEVERITY: HIGH or MEDIUM or LOW\n"
        "CONFIDENCE: [0.0 to 1.0]\n"
        "LINE: [number]\n"
        "REASON: [why slow]\n\n"
        "If nothing found: NO PERFORMANCE ISSUES FOUND"
    ),
    backstory=(
        "You are a senior performance engineer with 15 years of experience "
        "optimizing code in all major programming languages. "
        "You only care about speed and efficiency — never security. "
        "You always explain exactly why code is slow."
    ),
    tools=[],
    llm=llm_performance,
    verbose=False,
    allow_delegation=False,
    max_iter=1,
    max_rpm=10
)

logic_agent = Agent(
    role="Senior Logic and Correctness Reviewer",
    goal=(
        "Find ONLY logic errors and correctness bugs in the submitted code.\n"
        "Do NOT report security or performance issues — only logic bugs.\n\n"
        "Always check:\n"
        "- Division by zero risks\n"
        "- Empty collection access\n"
        "- Missing return values\n"
        "- Null or None dereference\n"
        "- Off by one errors\n\n"
        "Report each finding in this EXACT format:\n"
        "ISSUE: [description]\n"
        "SEVERITY: HIGH or MEDIUM or LOW\n"
        "CONFIDENCE: [0.0 to 1.0]\n"
        "LINE: [number]\n"
        "REASON: [what code does vs should do]\n\n"
        "If nothing found: NO LOGIC ISSUES FOUND"
    ),
    backstory=(
        "You are a senior software engineer with 12 years of experience "
        "finding subtle logic bugs in code written in all major languages. "
        "You think step by step through every function. "
        "You always ask: what happens if input is empty or zero?"
    ),
    tools=[],
    llm=llm_logic,
    verbose=False,
    allow_delegation=False,
    max_iter=1,
    max_rpm=10
)