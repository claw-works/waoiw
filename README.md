# waoiw 💣

> WoW + AI + Overseer — a supervised automation agent for World of Warcraft

## What is this?

A vision-based AI agent that "sees" the WoW game window via screenshots,
understands what's happening (HP, cooldowns, gather nodes), and performs
actions via keyboard/mouse simulation.

**Key design principle:** Supervised, not fully autonomous.
You stay in control. The agent works, you watch and can take over anytime.

## Architecture

```
You: "开始采矿"
    ↓
Agent Loop (LLM — understands intent, selects skill, observes results)
    ↓
Skill Registry (GatherMining / GatherHerb / ...)
    ↓
Screenshot (mss)
    ↓
Vision Layer (OpenCV + OCR)
    ↓
State Machine (rules-based decisions)
    ↓
Executor (pydirectinput — humanized mouse curves + random delays)
    ↓
Supervisor Panel (terminal UI — what the agent is thinking)
```

### Key Design: Think First, Act Later

The LLM agent is not frame-rate bound. It reasons fully before acting.
In solo PvE content, this "think pause" actually makes behavior more human-like.
Skills report progress back to the agent periodically; the agent decides whether to continue, adjust, or switch tasks.

## Phases

- **Phase 1 — Eyes**: Screenshot + recognize HP, mana, cooldowns, gather nodes
- **Phase 2 — Brain**: Simple state machine (detect node → move → gather)
- **Phase 3 — Supervised Run**: Human-in-the-loop with pause/resume control

## Stack

| Layer | Library |
|-------|---------|
| Screenshot | `mss` |
| OCR (numbers) | `pytesseract` |
| Image matching | `opencv-python` |
| Input simulation | `pydirectinput` |
| Vision AI (optional) | `anthropic` |
| Config | `pydantic-settings` |

## Requirements

- Windows 10/11
- Python 3.11+
- WoW running in windowed or borderless windowed mode
- Tesseract OCR installed

## Setup

```bash
pip install -r requirements.txt
python -m waoiw.capture test        # test screenshot
python -m waoiw.tools.vision_test   # test element detection
python -m waoiw.tools.calibrate     # calibrate screen regions
python waoiw/agent.py               # start agent loop (natural language)
python -m waoiw.run                 # start supervised session (direct)
```

## ⚠️ Disclaimer

**This project is for AI/computer vision research and educational purposes only.**

waoiw is an experiment in applying vision-based AI agents to a real-time game environment.
The goal is to study:
- Screen understanding via OCR and template matching
- State machine design for real-world event-driven systems
- Human-in-the-loop supervised automation patterns
- Randomized behavior generation to study bot-detection evasion as a security research topic

Using automation software in World of Warcraft may violate [Blizzard's Terms of Service](https://www.blizzard.com/en-us/legal/fba4d00f-c7e4-4883-b8b9-1b4500a402ea/blizzard-end-user-license-agreement).
The authors do not condone or encourage ToS violations. Use at your own risk.
