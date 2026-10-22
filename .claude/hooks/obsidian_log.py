"""Claude Code Stop hook: append a summary of the last turn to the Obsidian work log.

Reads the hook payload (JSON on stdin), walks the session transcript back to the last
real user prompt, and appends the prompt, the files written/edited and the tools used.
Turns without any tool calls (pure chat) are skipped.
"""
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

VAULT = Path(os.environ.get("OBSIDIAN_VAULT", r"C:\Users\User\Dropbox\Obsidian\Projects"))
LOG_NOTE = VAULT / "ANAGARIA" / "05 - Work Log.md"
EDIT_TOOLS = {"Write", "Edit", "NotebookEdit"}
PROMPT_MAX = 300


def _is_user_prompt(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return not content.startswith("<")  # skip injected command/system wrappers
    return isinstance(content, list) and any(b.get("type") == "text" for b in content)


def _prompt_text(entry):
    content = entry["message"]["content"]
    text = content if isinstance(content, str) else " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    text = " ".join(text.split())
    return text[:PROMPT_MAX] + ("…" if len(text) > PROMPT_MAX else "")


def summarize_turn(entries):
    """(prompt, edited files, tool counts) for everything after the last user prompt."""
    starts = [i for i, e in enumerate(entries) if _is_user_prompt(e)]
    if not starts:
        return None
    turn = entries[starts[-1] + 1:]
    calls = [
        b for e in turn if e.get("type") == "assistant"
        for b in e.get("message", {}).get("content", []) if isinstance(b, dict) and b.get("type") == "tool_use"
    ]
    files = sorted({c["input"].get("file_path") or c["input"].get("notebook_path", "")
                    for c in calls if c["name"] in EDIT_TOOLS} - {""})
    return _prompt_text(entries[starts[-1]]), files, Counter(c["name"] for c in calls)


def format_entry(prompt, files, tools, now):
    lines = [f"## {now:%Y-%m-%d %H:%M}", "", f"**בקשה:** {prompt}", ""]
    if files:
        lines += ["**קבצים שנערכו:**", *[f"- `{f}`" for f in files], ""]
    lines += ["**כלים:** " + ", ".join(f"{name}×{n}" for name, n in tools.most_common()), "", ""]
    return "\n".join(lines)


def main():
    payload = json.load(sys.stdin)
    transcript = Path(payload.get("transcript_path", ""))
    if not transcript.is_file() or not LOG_NOTE.parent.is_dir():
        return
    with transcript.open(encoding="utf-8") as fh:
        entries = [json.loads(line) for line in fh if line.strip()]
    summary = summarize_turn(entries)
    if summary is None or not summary[2]:
        return
    with LOG_NOTE.open("a", encoding="utf-8") as fh:
        fh.write(format_entry(*summary, datetime.now()))


if __name__ == "__main__":
    main()
