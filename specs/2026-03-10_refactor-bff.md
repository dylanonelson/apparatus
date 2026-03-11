Your task is to refactor the way we are calling the Python API from our TypeScript app.

## FIRST TASK: REFACTOR SHARED PROXY LOGIC

Right now all of our Next.js routes are doing the exact same thing - adding authentication credentials to a request based on the auth cookie and then proxying that request to the API.

Let's consolidate the logic into a shared helper and make it as centralized as possible. We should be able to delete a lot of redundant code.

## SECOND TASK: MAKE API CALLS TYPE SAFE

We have an openapi integration in the Python app, but the exported types are not up-to-date, and we aren't using them in our frontend or in our BFF. Let's update those types using the openapi-FastAPI-Pydantic integration and make sure ALL of the API calls that we make from the frontend and via the proxy are using the types from Python.
