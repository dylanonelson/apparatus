---
name: coding-task
description: A set of steps to follow whenever the user asks Claude to perform a discrete piece of work in the codebase, comparable to a Jira ticket
user-invocable: true
---

### STEP 1: GET YOUR BEARINGS (MANDATORY)

Start by orienting yourself:

```bash
# 1. See your working directory
pwd

# 2. List files to understand project structure
ls -la

# 3. Read the product and technical READMEs to understand the purpose and basic layout of the app.
cat README.md
cat docs/README.md

# 4. Check recent git history
git log --oneline -20
```

### Step 2: CLARIFY REQUIREMENTS

Review the provided work spec. Make a plan for how you plan to tackle the
work. Make sure each step of the work is accounted for. If you can't complete
this plan without further information, ask for it. Clarify anything in the work
spec that is ambiguous. It is HIGHLY IMPORTANT that once you finish with this
plan and begin work you continue to work without needing any further
clarification.

### STEP 3: MAKE THE CHANGE

Implement the asked-for feature or change thoroughly:

1. Write the code (frontend and/or backend as needed)
2. Test manually using browser automation (see Step 6)
3. Fix any issues discovered
4. Verify the feature works end-to-end

**DO:**

- Use best practices to write DRY, modular code
- Run tests at each stage of the change to make sure it was successful

**DON'T:**

- Commit code to main. ONLY work on this worktree branch.
- Make changes outside the scope of the original work spec

### STEP 4: VERIFY WITH BROWSER AUTOMATION

**CRITICAL:** You MUST verify features through the actual UI.

Use browser automation tools:

- Navigate to the app in a real browser
- Interact like a human user (click, type, scroll)
- Take screenshots at each step
- Verify both functionality AND visual appearance

**DO:**

- Test through the UI with clicks and keyboard input
- Take screenshots to verify visual appearance
- Check for console errors in browser
- Verify complete user workflows end-to-end
- Always test logged-out and logged-in scenarios
- When making changes to the data layer, make sure the data gets saved and returned correctly

**DON'T:**

- Only test with curl commands (backend testing alone is insufficient)
- Use JavaScript evaluation to bypass UI (no shortcuts)
- Skip visual verification
- Mark tests passing without thorough verification

### STEP 5: COMMIT AND PUSH YOUR PROGRESS

Make a descriptive git commit:

```bash
git add .
git commit -m "Implement [feature name] - verified end-to-end

- Added [specific changes]
- Tested with browser automation
- Updated feature_list.json: marked test #X as passing
- Screenshots in verification/ directory
"
```

Push the branch to GitHub and create a PR using the `gh` command line tool.

### STEP 6: END SESSION CLEANLY

Before context fills up:

1. Commit all working code
2. Ensure no uncommitted changes
3. Leave app in working state (no broken features)

---

## TESTING REQUIREMENTS

**ALL testing must use browser automation tools.**

Available tools: Playwright

Test like a human user with mouse and keyboard. Don't take shortcuts by using JavaScript evaluation.

---

## IMPORTANT REMINDERS

**Your Goal:** Production-quality application with all tests passing

**Quality Bar:**

- Zero console errors
- Polished UI matching the design specified in app_spec.txt
- All features work end-to-end through the UI
- Fast, responsive, professional

**You have unlimited time.** Take as long as needed to get it right. The most important thing is that you
leave the code base in a clean state before terminating the session (Step 10).

---

Begin by running Step 1 (Get Your Bearings).
