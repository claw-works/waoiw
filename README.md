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
Screenshot (mss)
    ↓
Vision Layer (OpenCV + OCR)
    ↓
State Machine (rules-based decisions)
    ↓
Executor (pydirectinput)
    ↓
Supervisor Panel (terminal UI — what the agent is thinking)
```

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
python -m waoiw.capture test   # test screenshot
python -m waoiw.vision test    # test element detection
python -m waoiw.run            # start supervised session
```

## ⚠️ Disclaimer

For research and personal learning only.
Using automation software may violate Blizzard's Terms of Service.
Use at your own risk.
