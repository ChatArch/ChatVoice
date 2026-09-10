# Markdown Todo

Turn selected ideas into an action plan only when you choose to.

## Convert a summary

Generate or refine a meeting summary, then click **转为 Todo** below it. The dedicated **Todo** tab receives a Markdown plan without changing the transcript or summary. It starts empty; opening the tab or refreshing the summary never creates tasks automatically. Regeneration asks before replacing existing text, and the previous version can be undone in the current page.

## Refine and export

Edit Markdown directly or use the conversation panel to split steps, reorder work, and clarify completion criteria. Cancellation, model errors, and stale responses must not overwrite manual edits. The task syntax is standard Markdown:

```markdown
# Release preparation
- [x] Confirm scope
- [ ] Prepare a test report
  - [ ] Collect failed cases
  - [ ] Document reproduction steps
```

Copy Markdown or download `.md` to use elsewhere. There is no mind-map integration, external task creation, or automatic execution in this version.

## Storage and privacy

Todo text and its refinement conversation belong to the meeting. Signed-in users use the existing meeting database; guest records stay in the current browser. Generation sends the supplied summary, Todo and relevant conversation to the existing summary model. No additional model configuration is required. Old meetings start with an empty Todo. Clearing a meeting also clears its Todo; switching meetings must not mix records. Review AI suggestions before treating them as agreed commitments.

## API

- `POST /api/meeting-notes/todo` takes `summary`, returns `content` (Markdown) and `model`.
- `POST /api/meeting-notes/todo/revise` takes `summary`, `current_todo`, `instruction` and optional `messages`; returns the complete `content`, a short `reply`, and `model`.
- Meeting detail and authorized data exports contain `todo_markdown` and `todo_chat_messages`. Older clients omitting these fields do not clear saved Todo content.
