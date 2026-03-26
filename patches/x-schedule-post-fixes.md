# x-schedule-post fixes (applied to /tmp/x-post/x_schedule_post/cli.py)

These changes need to be re-applied after x-post reinstall.

## 1. Preflight: allow quote/paragraph as first block (line ~862)

```python
# OLD:
if normalized_blocks[0].block_type != "hero_heading":
    errors.append("first_block_must_be_hero_heading")

# NEW:
if normalized_blocks[0].block_type not in {"hero_heading", "quote", "paragraph"}:
    errors.append("first_block_must_be_hero_heading_or_quote_or_paragraph")
```

## 2. Quote exit: Enter once to leave quote mode (line ~2806)

```python
# OLD:
await mcp.call("type_text", {"text": block_text})
await try_set_article_text_style(mcp, "body", context=f"{block_type}_reset")

# NEW:
await mcp.call("type_text", {"text": block_text})
# Exit quote block: Enter once exits quote in X Articles editor
await mcp.call("press_key", {"key": "Enter"})
await anyio.sleep(0.2)
await try_set_article_text_style(mcp, "body", context=f"{block_type}_reset")
```

## 3. Block separator: quote no longer needs 2 Enter (line ~1996)

```python
# OLD:
def block_separator_key_presses(previous_block_type: str) -> int:
    if previous_block_type in {"bullet_list", "quote"}:
        return 2
    return 1

# NEW:
def block_separator_key_presses(previous_block_type: str) -> int:
    if previous_block_type == "bullet_list":
        return 2
    return 1
```
