import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";

// Request/Response types
interface LocatorPayload {
  href: string;
  type: string;
  title?: string;
  locations?: {
    fragments?: string[];
    position?: number;
    progression?: number;
    totalProgression?: number;
  };
  text?: {
    before?: string;
    highlight?: string;
    after?: string;
  };
}

interface ViewportPayload {
  positions: number[];
  text: string;
  selection_text?: string | null;
}

interface AskAutomaticRequest {
  publication_id: string;
  locator: LocatorPayload;
  viewport: ViewportPayload;
}

interface AskAutomaticResponse {
  answer: string;
}

export const readerApi = createApi({
  reducerPath: "readerApi",
  baseQuery: fetchBaseQuery({ baseUrl: "/api" }),
  endpoints: (builder) => ({
    askAutomatic: builder.mutation<AskAutomaticResponse, AskAutomaticRequest>({
      query: (body) => ({
        url: "ask-automatic",
        method: "POST",
        body,
      }),
    }),
  }),
});

export const { useAskAutomaticMutation } = readerApi;
