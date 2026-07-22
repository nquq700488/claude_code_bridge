from __future__ import annotations

from .spec import TeamSpec, TeamMember


def render_team_protocol(team: TeamSpec) -> dict[str, str]:
    """返回 {member_name: protocol_text}，每个成员的完整注入文本。

    每个成员的协议由两部分组成：
    1. 花名册（所有成员通用）——团队名、拓扑、自身身份、花名册、通信方法
    2. 拓扑协议步骤（按角色差异化）
    """
    roster = _render_roster(team)
    protocols: dict[str, str] = {}
    for member in team.members:
        identity = _render_identity(team, member)
        steps = _render_topology_steps(team, member)
        protocols[member.name] = f"{roster}\n\n{identity}\n\n{steps}"
    return protocols


def _render_roster(team: TeamSpec) -> str:
    """花名册——所有成员看到的相同部分。"""
    lines = [
        f"## Team: {team.name}",
        f"Topology: {team.topology}",
    ]
    if team.description:
        lines.append(f"Description: {team.description}")
    lines.append("")
    lines.append("### Roster")
    for i, m in enumerate(team.members, 1):
        role_info = f" — {m.description}" if m.description else ""
        lines.append(f"{i}. **{m.name}** ({m.provider}){role_info}")
    lines.append("")
    lines.append("### Communication")
    lines.append("- Use `/ask <name> <message>` to send a task to a teammate")
    lines.append("- Use `/pend --watch <job_id>` to wait for a reply")
    lines.append("- Always report final results to the user (human)")
    return "\n".join(lines)


def _render_identity(team: TeamSpec, member: TeamMember) -> str:
    """自身身份段。"""
    lines = [
        "## Your Role",
        f"You are **{member.name}** on team **{team.name}**.",
    ]
    if member.description:
        lines.append(f"Your responsibility: {member.description}")
    if member.role:
        lines.append(f"Role pack: {member.role}")
    return "\n".join(lines)


def _render_topology_steps(team: TeamSpec, member: TeamMember) -> str:
    """按拓扑类型渲染该成员的协议步骤。"""
    topology = team.topology
    policy = team.policy
    is_leader = policy.leader is not None and member.name == policy.leader
    is_synthesizer = policy.synthesizer is not None and member.name == policy.synthesizer

    if topology == 'hub-spoke':
        return _hub_spoke_steps(is_leader)
    elif topology == 'review-loop':
        return _review_loop_steps(member.name, is_leader, policy)
    elif topology == 'debate':
        return _debate_steps(is_synthesizer)
    else:  # mesh
        return _mesh_steps()


def _hub_spoke_steps(is_leader: bool) -> str:
    lines = ["## Hub-Spoke Protocol"]
    if is_leader:
        lines.extend([
            "",
            "You are the **leader** of this team. The user will only speak to you.",
            "",
            "**Your workflow:**",
            "1. Receive the task from the user",
            "2. Break it down and dispatch subtasks to members via `/ask <member>`",
            "3. Collect replies via `/pend --watch <job_id>`",
            "4. Synthesize results and report back to the user",
            "5. If a member's reply is insufficient, ask again with clarification",
        ])
    else:
        lines.extend([
            "",
            "**Your workflow:**",
            "1. Wait for the leader to send you a task",
            "2. Complete it thoroughly and reply with your results",
            "3. If you need clarification, ask the leader back",
            "4. Do NOT report directly to the user unless asked",
        ])
    return "\n".join(lines)


def _review_loop_steps(name: str, is_leader: bool, policy) -> str:
    lines = ["## Review-Loop Protocol"]
    lines.append(f"Pass threshold: {policy.pass_score}/10, Max rounds: {policy.rounds_max}")
    lines.append("")
    if is_leader:
        lines.extend([
            "You are the **leader**. Your workflow:",
            "1. Receive the task from the user",
            "2. Package task requirements + acceptance criteria",
            "3. Send the package to the coder to implement",
            "4. When the coder sends their work to the reviewer, wait for the review score",
            "5. If score < pass_score and rounds remain → ask coder to REVISE",
            "6. If score >= pass_score or max rounds reached → report result to user",
        ])
    elif 'reviewer' in name.lower():
        lines.extend([
            "You are the **reviewer**. Your workflow:",
            "1. Wait for the coder to send you their implementation + diff",
            "2. Score it against the rubric (return JSON with scores and summary)",
            f"3. If score < {policy.pass_score} and rounds remain → respond REVISE with specific feedback",
            "4. If score >= pass_score → respond PASS",
            "5. Send your review to the leader",
        ])
    else:
        lines.extend([
            "You are the **coder/implementer**. Your workflow:",
            "1. Wait for the leader to send you a task package",
            "2. Implement the solution",
            "3. Send your work + git diff to the reviewer for scoring",
            "4. If you receive REVISE, address the feedback and resubmit",
            "5. On PASS, report completion to the leader",
        ])
    return "\n".join(lines)


def _debate_steps(is_synthesizer: bool) -> str:
    lines = ["## Debate Protocol"]
    if is_synthesizer:
        lines.extend([
            "",
            "You are the **synthesizer**. Your workflow:",
            "1. Receive a question from the user",
            "2. Broadcast the same question to ALL team members",
            "3. Wait for all members to respond independently",
            "4. Compare and contrast their answers",
            "5. Present a synthesized report highlighting agreements, disagreements, and your recommendation",
        ])
    else:
        lines.extend([
            "",
            "**Your workflow:**",
            "1. When the synthesizer broadcasts a question, answer it INDEPENDENTLY",
            "2. Do NOT read other members' answers before forming your own",
            "3. Provide your reasoning, not just the conclusion",
            "4. Reply directly to the synthesizer",
        ])
    return "\n".join(lines)


def _mesh_steps() -> str:
    return "\n".join([
        "## Mesh Protocol",
        "",
        "This team uses a **mesh** topology with no fixed workflow.",
        "- Any member may ask any other member for help at any time",
        "- The user may speak directly to any member",
        "- Coordinate freely using `/ask` and `/pend`",
        "- When you finish a task, report results to the user",
    ])


__all__ = ['render_team_protocol']
