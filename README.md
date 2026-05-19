# 🛡️ LifeSaver: Multi-Agent System for More Reliable Python Code Review

> A research-backed multi-agent AI system that provides **consistent, measurable, and trustworthy code reviews** using formal arbitration and reliability scoring.

---

## 📌 Problem Statement

Developers today use Large Language Models (LLMs) to review code, but **LLM-based code review systems are unreliable**:

- ❌ **Inconsistent** – Running the same review twice gives different results
- ❌ **False Positives** – Flags issues that aren't real problems (wasting time)
- ❌ **False Negatives** – Misses actual security vulnerabilities
- ❌ **Untrustworthy** – Hard to know which findings to act on

**Traditional code review shouldn't be a guessing game.** It needs structured reasoning, formal scoring, and consistent outputs.

---

## 💡 Solution: LifeSaver

LifeSaver combines **multi-agent AI reasoning** with **formal arbitration** to create code reviews that are:

✅ **Structured** – Uses explicit scoring formulas (WAS & Reliability)  
✅ **Measurable** – Tracks false positive rate, F1 score, and consistency  
✅ **Reliable** – Consistent results across multiple runs  
✅ **Trustworthy** – Only reports findings all agents largely agree on  

---

## 🏗️ Architecture

### Three Specialized AI Agents

```
┌─────────────────────────────────────────────────────┐
│              Input: Python Code                       │
└────────────┬──────────────────────────────────────────┘
             │
    ┌────────┴────────┬─────────────┬──────────────────┐
    │                 │             │                  │
    ▼                 ▼             ▼                  ▼
┌─────────────┐ ┌──────────────┐ ┌────────────┐  [Bandit]
│  Security   │ │ Performance  │ │   Logic    │   Scanner
│   Agent     │ │   Agent      │ │   Agent    │  (for Python)
│ (llama3.1)  │ │ (gemma3)     │ │(deepseek)  │
└──────┬──────┘ └──────┬───────┘ └──────┬─────┘
       │                │               │
       └────────────────┼───────────────┘
                        ▼
          ┌─────────────────────────────────┐
          │   Arbitration Module            │
          │  (Weighted Agreement Score)     │
          │   WAS(i) = Σ(w·S·C) / Σw       │
          └──────────┬──────────────────────┘
                     │
                     ▼
          ┌─────────────────────────────────┐
          │  Filter (WAS >= 0.6)            │
          │  Calculate Reliability Score    │
          └──────────┬──────────────────────┘
                     │
                     ▼
          ┌─────────────────────────────────┐
          │  Final Report                   │
          │  (Structured JSON + Summary)    │
          └─────────────────────────────────┘
```

### Agent Roles & Expertise

| Agent | Specialty | LLM Model | Tools |
|-------|-----------|-----------|-------|
| **🔒 Security Agent** | Finds vulnerabilities, hardcoded secrets, injection attacks | llama3.1:8b | Bandit + LLM Reasoning |
| **⚡ Performance Agent** | Detects inefficient loops, memory issues, bottlenecks | gemma3:4b | LLM Expertise |
| **🧠 Logic Agent** | Catches bugs, logic errors, null pointer issues | deepseek-r1:7b | LLM Reasoning |

---

## 📐 Weighted Agreement Score (WAS)

LifeSaver uses a **formal arbitration model** instead of simple majority voting:

```
WAS(i) = Σ(wₐ · Sₐ · Cₐ) / Σwₐ
```

Where:
- **wₐ** = Agent weight (Security: 0.5, Performance: 0.3, Logic: 0.2)
- **Sₐ** = Severity score (Critical: 1.0, Moderate: 0.6, Minor: 0.3)
- **Cₐ** = Confidence score (0.0 to 1.0, from agent)
- **Bonus** = +0.15 if Bandit also flagged it (Python only)

**Only findings with WAS ≥ 0.6 appear in the report.**

---

## 📊 Reliability Score

LifeSaver measures system reliability across multiple runs:

```
R = α·(1 − FPR) + β·wF1 + γ·Consistency
```

Where:
- **FPR** = False Positive Rate (lower is better)
- **wF1** = Weighted F1 Score (accuracy metric)
- **Consistency** = 1 − StdDev(WAS scores across 5 runs)
- **α, β, γ** = Weights (sum to 1.0, calibrated during testing)

---

## 🚀 Quick Start

### Prerequisites

- **Python 3.10+**
- **Ollama** running locally (for LLM inference)
- **Bandit** installed (for Python security scanning)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sebrinkedir/Lifesaver.git
   cd Lifesaver
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Download LLM models via Ollama:**
   ```bash
   ollama pull llama3.1:8b    # Security Agent
   ollama pull gemma3:4b      # Performance Agent
   ollama pull deepseek-r1:7b # Logic Agent
   ```

4. **Start Ollama server:**
   ```bash
   ollama serve
   ```
   (Run in a separate terminal)

### Usage

1. **Place your code file** in the repo directory, e.g., `test_code.py`

2. **Run LifeSaver:**
   ```bash
   python main.py
   ```

3. **View the report:**
   ```
   ============================================================
        LIFESAVER - FINAL REPORT
   ============================================================

   Total Issues: 3

   #1 [SECURITY] HIGH
     ISSUE: Hardcoded database password in line 15
     WAS: 0.85 | Confidence: 0.90
     >> Act on this immediately

   #2 [PERFORMANCE] MEDIUM
     ISSUE: Nested loop with O(n²) complexity
     WAS: 0.72 | Confidence: 0.80
     >> Act on this immediately

   Reliability : 87.5%
   Status      : RELIABLE
   ============================================================
   ```

### Supported Languages

✅ Python (with Bandit)  
✅ PHP  
✅ JavaScript  
✅ Java  
✅ C#  
✅ Go  
✅ Ruby  
✅ C++  

---

## 📁 Project Structure

```
Lifesaver/
├── main.py              # Entry point - orchestrates the review process
├── agents.py            # Defines the 3 AI agents & their personalities
├── tasks.py             # Task descriptions for each agent
├── arbitration.py       # WAS calculation, filtering, reliability scoring
├── bandit_tool.py       # Wrapper for Bandit (Python security scanner)
├── requirements.txt     # Python dependencies
├── test_php.php         # Example PHP code to review
├── code_activate.txt    # Ollama setup instructions
└── README.md            # This file
```

### Key Files Explained

**`main.py`**  
- Orchestrates the entire review process
- Detects programming language
- Collects findings from all 3 agents
- Applies arbitration & filtering
- Prints final report

**`agents.py`**  
- Defines Security, Performance, and Logic agents
- Sets LLM models, temperature, and system prompts
- Configures Bandit tool for Security Agent

**`tasks.py`**  
- Creates detailed task descriptions for each agent
- Implements language detection
- Extracts function names from code
- Specifies output format requirements

**`arbitration.py`**  
- Parses agent findings from text
- Calculates WAS scores
- Filters findings (WAS ≥ 0.6)
- Calculates reliability metrics
- Formats and prints reports

**`bandit_tool.py`**  
- Wraps Bandit as a CrewAI tool
- Runs security scanning on Python code
- Integrates results with agent reasoning

---

## 🔬 Research Grounding

LifeSaver is built on established research:

- **Multi-Agent Frameworks:** AutoGen, METRA
- **Reasoning Approaches:** ReAct (Reasoning + Acting)
- **Code Review:** CodeReviewer (LLM-based automated review)
- **Security Analysis:** Bandit (static analysis tool)

**Key Innovation:** LifeSaver is the first to combine:
1. ✓ Formal scoring formula (WAS)
2. ✓ Explicit arbitration process
3. ✓ Consistency measurement across runs
4. ✓ Reliability as a measurable metric

---

## 🧪 Evaluation Plan

### Test Datasets

- **Juliet Test Suite** – Known vulnerabilities
- **Manually Injected Bugs** – Controlled logic errors
- **Open-Source Examples** – Real clean code (negative cases)

### Adversarial Test Cases

1. **Obfuscation Attacks** – Base64-encoded exec calls
2. **Injection Mimicry** – SQL strings via concatenation
3. **Code Splitting** – Vulnerabilities spread across functions

### Comparison Baselines

- Single-agent LLM review (no arbitration)
- Multi-agent without formal arbitration
- **LifeSaver** (with formal WAS & reliability scoring)

### Metrics

| Metric | Purpose |
|--------|---------|
| **Detection Rate** | % of real issues found |
| **False Positive Rate** | % of false alarms |
| **WAS-based Reliability** | Formal score accounting for accuracy & consistency |
| **Consistency** | Standard deviation of WAS across 5 runs |
| **Weighted F1 Score** | Harmonic mean of precision & recall |

---

## 📈 Current Status

### ✅ Completed
- [x] Three specialized AI agents (Security, Performance, Logic)
- [x] CrewAI framework integration
- [x] Bandit security scanner integration (MCP-style wrapper)
- [x] WAS arbitration model
- [x] Confidence scoring from agents
- [x] Filtering system (WAS threshold)
- [x] Multi-language support
- [x] Report formatting

### 🚧 In Progress / Planned
- [ ] Consistency measurement (5 repeated runs with deviation tracking)
- [ ] Complete Reliability Score calculation (FPR + wF1 + Consistency)
- [ ] Juliet Test Suite evaluation
- [ ] Adversarial input testing
- [ ] Comparative analysis (single-agent vs multi-agent)
- [ ] Comprehensive metrics dashboard
- [ ] Web UI for report visualization
- [ ] Docker support for easy deployment

---

## 🤝 Contributing

We welcome contributions! Areas where we need help:

1. **Testing** – Run LifeSaver on various code samples, report false positives/negatives
2. **Evaluation** – Help build test datasets and benchmark results
3. **Features** – Add support for more languages or improve agent prompts
4. **Documentation** – Improve README, add tutorials, create examples

### How to Contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Make your changes and test thoroughly
4. Commit with clear messages (`git commit -m "Add feature X"`)
5. Push to your fork and open a Pull Request

---

## 📝 Citation

If you use LifeSaver in your research, please cite:

```bibtex
@software{lifesaver2025,
  title={LifeSaver: Multi-Agent System for Reliable Python Code Review},
  author={Sebrinkedir},
  year={2025},
  url={https://github.com/Sebrinkedir/Lifesaver}
}
```

---

## 📄 License

This project is open source and available under the MIT License.

---

## 🙋 Support

- **Issues:** Open a GitHub issue for bugs or feature requests
- **Discussions:** Use GitHub Discussions for questions and ideas
- **Documentation:** Check the wiki for more detailed guides

---

## 🎯 Vision

LifeSaver aims to make **LLM-based code review trustworthy and reliable** by combining:

- 🧠 Multi-agent reasoning for diverse perspectives
- ⚖️ Formal arbitration to resolve disagreements
- 📊 Measurable reliability scores
- 🔄 Consistency guarantees across runs

Eventually, we want LifeSaver to be a **production-ready code review system** that developers can confidently use in their CI/CD pipelines.

---

## 🙏 Acknowledgments

- **CrewAI** – Multi-agent orchestration framework
- **Bandit** – Python security analyzer
- **Ollama** – Local LLM inference
- **Research Community** – AutoGen, METRA, CodeReviewer, and ReAct pioneers

---

**Made with ❤️ by [Sebrinkedir](https://github.com/Sebrinkedir)**

Last Updated: May 2025
