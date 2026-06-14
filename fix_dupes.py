"""R94: fix duplicate reply_text kwargs in test_runtime_stage_chain_explicit_reply.py."""
import re
from pathlib import Path

path = Path(r"D:\Software\project\helios\helios_v2\tests\test_runtime_stage_chain_explicit_reply.py")
text = path.read_text(encoding="utf-8")

# Pattern: `_ReplyThoughtProvider(reply_text="X", reply_text="Y")` -> `_ReplyThoughtProvider(reply_text="X")`
# Use re.sub to remove the duplicate
text = re.sub(
    r"_ReplyThoughtProvider\(reply_text=\"([^\"]*)\",\s*reply_text=\"([^\"]*)\"\)",
    r'_ReplyThoughtProvider(reply_text="\1")',
    text,
)

# Also handle the docstring that says "model fills `i_want_to_say`" — leave for context

# Add `action_intent="reply"` to each _ReplyThoughtProvider constructor that has reply_text but no action_intent
# (a follow-up step — the R94 explicit-reply path requires both)

path.write_text(text, encoding="utf-8")
print(f"Fixed: {path.name}")
