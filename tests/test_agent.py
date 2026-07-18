from __future__ import annotations

from lightcoder.agent import CodingAgent


def test_parse_action_uses_first_complete_json_object() -> None:
    content = (
        '<tool_calls>\n'
        '{"action":"read","path":"first.txt"}\n'
        '{"action":"read","path":"second.txt"}'
    )
    assert CodingAgent.parse_action(content) == {
        "action": "read",
        "path": "first.txt",
    }


def test_parse_action_recovers_fenced_bash() -> None:
    action = CodingAgent.parse_action(
        "I will run the check.\n\n```bash\npython3 /app/check.py\n```"
    )
    assert action["action"] == "bash"
    assert action["command"] == "python3 /app/check.py"
    assert action["background"] is False


def test_parse_action_combines_multiple_fenced_bash_blocks() -> None:
    content = """Create the script.
```bash
cat > /app/check.py <<'PY'
print('ok')
PY
```
Run it.
```sh
python3 /app/check.py
```
"""
    action = CodingAgent.parse_action(content)
    assert action["action"] == "bash"
    assert action["command"] == (
        "cat > /app/check.py <<'PY'\nprint('ok')\nPY\npython3 /app/check.py"
    )


def test_parse_action_recovers_deepseek_xml_batch_with_inner_quotes() -> None:
    content = """<batch>
  <action action="bash" command="ls -la /app/networks/" cwd="." timeout_seconds="10" background="false" rationale="Inspect files"/>
  <action action="bash" command="head -5 /app/a && echo "---" && head -5 /app/b" cwd="." timeout_seconds="10" background="false" rationale="Check formats"/>
</batch>"""
    action = CodingAgent.parse_action(content)
    assert action["action"] == "batch"
    assert len(action["actions"]) == 2
    assert action["actions"][1]["command"] == (
        'head -5 /app/a && echo "---" && head -5 /app/b'
    )


def test_parse_action_recovers_unescaped_multiline_bash_json() -> None:
    content = '''```json
{
  "action": "bash",
  "command": "cd /app && python3 -c "
print('ok')
" 2>&1
",
  "cwd": ".",
  "timeout_seconds": 60,
  "rationale": "Run inline Python"
}
```'''
    action = CodingAgent.parse_action(content)
    assert action["action"] == "bash"
    assert action["command"] == 'cd /app && python3 -c "\nprint(\'ok\')\n" 2>&1\n'
    assert action["timeout_seconds"] == 60.0
