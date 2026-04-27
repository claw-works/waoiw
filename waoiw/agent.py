"""
agent.py — LLM 驱动的 Agent Loop

设计原则：
- 你说一句自然语言，agent 理解意图，选择 skill，执行，观察结果，再决策
- 没有节拍限制：让 LLM 充分推理再行动（反而更像真人）
- skill 执行过程中定期汇报，agent 可以调整策略
- 支持多轮对话：你可以随时说"停"、"换去采草药"、"先去卖东西"

流程：
  用户输入
      ↓
  Agent (LLM) 分析 → 选 Skill → 填参数
      ↓
  Skill 执行（可运行数分钟）
      ↓
  Skill 汇报进度 → Agent 判断：继续 / 调整 / 停止
      ↓
  等待下一条用户指令 or 自主继续
"""
import json
import threading
from typing import Optional

from anthropic import Anthropic
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.markdown import Markdown

from waoiw.skills import skill_descriptions, get_skill, all_skills, SkillContext, SkillResult
from waoiw.config import config

console = Console()

# ── System Prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """你是 waoiw，一个运行在 World of Warcraft 里的 AI 游戏助手。
你通过截图理解游戏画面，通过技能（Skill）执行操作，模拟真实玩家的行为。

你的特点：
- 你不是机器人，你是一个会"想"的玩家。操作前先思考，不需要跟上严格节拍。
- solo 场景下完全可以等你推理完毕再行动，延迟反而更真实。
- 遇到异常情况（死亡、被打断、找不到节点）你会自己判断下一步。
- 你会汇报进度，但不会刷屏。

可用技能列表：
{skills}

当用户给你指令时，你需要：
1. 理解意图
2. 选择合适的 skill（从列表中选 name）
3. 提取参数（如有）
4. 用 JSON 格式输出决策

输出格式（只输出 JSON，不要其他文字）：
{{
  "skill": "skill_name",
  "params": {{}},
  "reasoning": "为什么选这个 skill，以及执行策略的简短说明"
}}

如果用户说的是"停"、"暂停"、"quit"等，输出：
{{
  "skill": "stop",
  "params": {{}},
  "reasoning": "用户要求停止"
}}

如果指令不清晰，输出：
{{
  "skill": "ask",
  "params": {{"question": "你需要问用户的问题"}},
  "reasoning": "需要更多信息"
}}
"""


class AgentLoop:
    def __init__(self):
        self.client = Anthropic()
        self.history: list[dict] = []
        self.current_ctx: Optional[SkillContext] = None
        self._skill_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _system(self) -> str:
        return SYSTEM_PROMPT.format(skills=skill_descriptions())

    def _think(self, user_message: str) -> dict:
        """
        让 LLM 理解指令，返回决策 JSON。
        这一步可以花几秒钟——完全没问题，真人也会先想想。
        """
        self.history.append({"role": "user", "content": user_message})

        console.print("[dim]🧠 thinking...[/dim]")

        response = self.client.messages.create(
            model="claude-opus-4-5",
            max_tokens=512,
            system=self._system(),
            messages=self.history,
        )

        text = response.content[0].text.strip()
        self.history.append({"role": "assistant", "content": text})

        # 解析 JSON
        try:
            # 处理可能带 markdown 代码块的情况
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            return json.loads(text.strip())
        except Exception:
            console.print(f"[red]解析失败，原文: {text}[/red]")
            return {"skill": "ask", "params": {"question": "我没理解你的意思，能再说一遍吗？"}, "reasoning": "parse error"}

    def _observe(self, result: SkillResult) -> dict:
        """
        Skill 汇报进度后，让 LLM 决定：继续 / 调整 / 停止
        """
        obs_msg = f"[skill汇报] {result.message}\n数据: {json.dumps(result.data, ensure_ascii=False)}"
        return self._think(obs_msg)

    def _run_skill(self, skill_name: str, params: dict, instruction: str):
        """在后台线程执行 skill"""
        SkillCls = get_skill(skill_name)
        if not SkillCls:
            console.print(f"[red]未知 skill: {skill_name}[/red]")
            return

        ctx = SkillContext(
            instruction=instruction,
            params=params,
            stop_requested=False,
        )
        self.current_ctx = ctx

        skill = SkillCls()
        console.print(Panel(
            f"[bold green]▶ 执行 Skill:[/] {skill_name}\n"
            f"[dim]{skill.description}[/dim]\n"
            f"参数: {params}",
            border_style="green",
        ))

        while True:
            result = skill.run(ctx)

            if result.should_continue:
                # skill 中途汇报，agent 思考是否继续
                console.print(f"\n[cyan]📊 进度汇报:[/] {result.message}")
                decision = self._observe(result)

                if decision.get("skill") == "stop":
                    console.print("[yellow]Agent 决定停止 skill[/yellow]")
                    ctx.stop_requested = True
                    break
                elif decision.get("skill") == skill_name:
                    # 继续同一个 skill
                    console.print(f"[dim]继续执行: {decision.get('reasoning', '')}[/dim]")
                    continue
                else:
                    # 切换到别的 skill
                    ctx.stop_requested = True
                    new_skill = decision.get("skill")
                    console.print(f"[yellow]切换到: {new_skill}[/yellow]")
                    self._run_skill(new_skill, decision.get("params", {}), instruction)
                    break
            else:
                # skill 正常结束
                console.print(Panel(
                    f"[bold]✅ Skill 完成[/bold]\n{result.message}",
                    border_style="green" if result.success else "red",
                ))
                break

        self.current_ctx = None

    def run(self):
        """主交互循环"""
        console.print(Panel(
            "[bold cyan]waoiw agent[/bold cyan] 💣\n"
            "[dim]输入自然语言指令，agent 会理解并执行对应的操作。\n"
            "例如：开始采矿 / 停止 / 去采草药\n"
            "Ctrl+C 退出[/dim]",
            border_style="cyan",
        ))

        while True:
            try:
                user_input = Prompt.ask("\n[bold cyan]>[/bold cyan]").strip()
                if not user_input:
                    continue

                # 如果有 skill 在跑，先停掉
                if self.current_ctx and not self.current_ctx.stop_requested:
                    console.print("[yellow]停止当前 skill...[/yellow]")
                    self.current_ctx.stop_requested = True

                # LLM 思考
                decision = self._think(user_input)
                skill_name = decision.get("skill", "")
                reasoning = decision.get("reasoning", "")
                params = decision.get("params", {})

                console.print(f"[dim]💭 {reasoning}[/dim]")

                if skill_name == "stop":
                    console.print("[bold yellow]已停止。[/bold yellow]")
                    continue

                elif skill_name == "ask":
                    question = params.get("question", "能再说清楚点吗？")
                    console.print(f"[cyan]🤔 {question}[/cyan]")
                    continue

                elif not get_skill(skill_name):
                    console.print(f"[red]没有找到 skill: {skill_name}[/red]")
                    console.print("可用 skill：")
                    for cls in all_skills():
                        console.print(f"  [dim]{cls.name}[/dim] — {cls.description[:50]}...")
                    continue

                # 在后台线程执行 skill（不阻塞交互）
                t = threading.Thread(
                    target=self._run_skill,
                    args=(skill_name, params, user_input),
                    daemon=True,
                )
                t.start()
                self._skill_thread = t

            except KeyboardInterrupt:
                if self.current_ctx:
                    self.current_ctx.stop_requested = True
                console.print("\n[bold]👋 bye[/bold]")
                break


# ── CLI 入口 ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    AgentLoop().run()
