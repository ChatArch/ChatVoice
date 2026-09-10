# Markdown Todo

Discuss ideas first, then decide whether to make an action plan. Todo is an independent Markdown document, not an automatic executor.

| Goal | Action |
| --- | --- |
| Convert an existing summary | Click Convert to Todo below the summary |
| Start empty or write manually | Open the Todo tab and edit |
| Split steps, reorder or clarify completion | Use the Todo conversation panel |
| Restore pre-revision content | Undo the model change |
| Use another tool | Copy Markdown or export `.md` |

## Explicit conversion

1. Generate or refine the current meeting summary.
2. Decide that the idea should move forward and click **Convert to Todo**.
3. Review groups, tasks and substeps. Do not treat invented owners, dates or commitments as agreed facts.

Opening the tab and refreshing a summary never trigger conversion. Regeneration asks before replacing an existing Todo, and the prior text can be restored in the current page. The source summary and transcript stay unchanged.

## Edit and continue the conversation

The left panel is a Markdown text editor. The right panel is a conversation dedicated to this Todo. Ask to split the first task into concrete steps, reorder dependencies or preserve completed work. The model returns the full document and a short explanation.

```markdown
# Technical article

## Prepare
- [x] Confirm the topic
- [ ] Collect key conclusions and sources

## Write
- [ ] Draft the article
  - [ ] Outline the sections
  - [ ] Add examples
- [ ] Check citations before publishing
```

Change `- [ ]` to `- [x]` to mark completion. The undo button restores model-revision/regeneration history kept in the current page, not a full cross-device version archive.

Cancellation, request errors and stale responses do not overwrite newer manual edits. A source without actionable commitments can remain without tasks.

## Save, export and boundaries

- Todo and its refinement conversation belong to the meeting: server storage for accounts, current-browser storage for guests.
- Copy Markdown and export `.md` preserve ordinary text for other tools.
- No mind-map view, external task synchronization, reminders or task execution are included.
- Todo reuses the configured notes model. Conversion sends the summary; refinement sends the summary, current Todo and relevant conversation.

See [HTTP API](api-access.md#todo) for `todo_markdown` and `todo_chat_messages`.
