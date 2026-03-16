---
name: make-change
description: A set of steps to follow whenever the user asks Claude to perform a discrete piece of work in the codebase, comparable to a Jira ticket
user-invocable: true
---

# YOUR ROLE - CODING AGENT

You are making a change to a full-stack e-reading application. You will be
prompted with a work spec. You are working in a git worktree on a branch. Your
job is to create a PR that follows the spec.

### STEP 1: GET YOUR BEARINGS (MANDATORY)

**Follow the directions in the learn-repo skill.**

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

**Follow the directions in the test-app skill.**

DO NOT OPEN A PR WITHOUT TESTING YOUR CHANGES.

### STEP 5: COMMIT AND PUSH YOUR PROGRESS

Make a descriptive git commit:

```bash
git add .
git commit -m "Implement [feature name] - verified end-to-end

- Added [specific changes]
- Tested with browser automation
"
```

Push the branch to GitHub and create a PR using the `gh` command line tool.

---

## TESTING REQUIREMENTS

**ALL testing must use browser automation tools.**

Available tools: Playwright CLI

Test like a human user with mouse and keyboard. Don't take shortcuts by using JavaScript evaluation.

---

## IMPORTANT REMINDERS

**Your Goal:** Production-quality application with all tests passing

**Quality Bar:**

- Zero console errors
- All features work end-to-end through the UI
- Fast, responsive, professional

**You have unlimited time.** Take as long as needed to get it right. The most important thing is that you
leave the code base in a clean state before terminating the session.

---

Begin by running Step 1 (Get Your Bearings).

