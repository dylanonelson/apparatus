---
name: test-app
description: A set of steps to follow to test this app in the browser
user-invocable: true
---

# YOUR ROLE - CODING ASSISTANT

You a coding assistant for a full-stack e-reading application. You are working
in a git worktree on a branch and you are running in a Docker container.

You will be prompted with instructions for testing.

## Testing this repo

### STEP 1: Make sure the environment is ready for testing

If you haven't already, orient yourself to the repo using the learn-repo skill.

Check the current git status to understand what changes have been made.

Check the current development environment to see which services are currently running.

### STEP 2: Decide what to test

Based on the user's instructions, make a list of test cases.

IMPORTANT: test end-to-end user flows, not just superficial tests!

- Test data persistence
- Test logging in and out

### STEP 3: Run your tests

IMPORTANT: In your Docker environment, run Playwright with the browser set to chromium. The default browser 'chrome' is NOT installed.

If necessary, create a test user. You can create a user with an email address at apparatus-ebooks.com. For example: test-user-UNIQUE_TIMESTAMP@apparatus-ebooks.com.

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

### STEP 4: Report the results

Output the results of your tests in a digestible format that includes the following:

- Category of test (which type of feature it tests e.g. 'Library screen', 'E-reader navigation')
- A description of what you tested
- The result (pass / fail)
- A column with any notes about unexpected behavior or explaining the nature of the failure
