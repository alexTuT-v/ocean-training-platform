# Selected bulk issue checklist

- [x] A single checkbox selects only that eligible learner.
- [x] Header checkbox selects and deselects eligible learners on the visible page.
- [x] Selection persists across pages and the selected count is accurate.
- [x] Ineligible learners have no actionable selection.
- [x] New issue is disabled with no selection; confirmation shows the selected count.
- [x] Request body contains only selected learner IDs.
- [x] Invalid or cross-tenant IDs write nothing.
- [x] Concurrent or repeated requests with the same key yield one result and one audit per issued certificate.
- [x] Uncertain requests can replay the saved key and body after refresh.
- [x] Successful issue refreshes the current page and clears selection.
- [x] The 100,000-row course still loads one page at a time.
