import { ThPlugin } from "../PluginRegistry";
import { ThActionsKeys } from "@/preferences/models/enums";

import { StatefulAnswersTrigger } from "../../Actions/Answers/StatefulAnswersTrigger";
import { StatefulAnswersContainer } from "../../Actions/Answers/StatefulAnswersContainer";

export const createAnswersPlugin = (): ThPlugin => {
  return {
    id: "answers",
    name: "AI Answers",
    description: "AI-powered answers panel",
    version: "1.0.0",
    components: {
      actions: {
        [ThActionsKeys.answers]: {
          Trigger: StatefulAnswersTrigger,
          Target: StatefulAnswersContainer,
        },
      },
    },
  };
};
