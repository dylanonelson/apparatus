import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

import type { components } from "@/lib/api-types.generated";

export type AutomaticAnswersRequest =
  components["schemas"]["AutomaticAnswersRequestModel"];
export type AskResponse = components["schemas"]["AskResponseModel"];
export type ReadingLocationResponse =
  components["schemas"]["ReadingLocationResponseModel"];
export type StoreReadingStateRequest =
  components["schemas"]["StoreReadingStateRequestModel"];
export type ReadingStateResponse =
  components["schemas"]["ReadingStateResponseModel"];
export type UserResponse = components["schemas"]["UserResponseModel"];
export type LocatorPayload = components["schemas"]["LocatorModel"];
export type ViewportPayload = components["schemas"]["ViewportPayloadModel"];

export const readerApi = createApi({
  reducerPath: "readerApi",
  baseQuery: fetchBaseQuery({ baseUrl: "/api" }),
  endpoints: (builder) => ({
    askAutomatic: builder.mutation<AskResponse, AutomaticAnswersRequest>({
      query: (body) => ({
        url: "ask-automatic",
        method: "POST",
        body,
      }),
    }),
  }),
});

export const { useAskAutomaticMutation } = readerApi;
