"use client";

import { ThActionsKeys } from "@/preferences/models/enums";

import AnswersIcon from "./assets/icons/answers.svg";

import { StatefulActionTriggerProps } from "../models/actions";
import { ThActionsTriggerVariant } from "@/core/Components/Actions/ThActionsBar";

import { StatefulActionIcon } from "../Triggers/StatefulActionIcon";
import { StatefulOverflowMenuItem } from "../Triggers/StatefulOverflowMenuItem";

import { usePreferences } from "@/preferences/hooks/usePreferences";
import { useI18n } from "@/i18n/useI18n";

import { useAppDispatch, useAppSelector } from "@/lib/hooks";
import { setActionOpen } from "@/lib/actionsReducer";

export const StatefulAnswersTrigger = ({
  variant,
}: StatefulActionTriggerProps) => {
  const { preferences } = usePreferences();
  const { t } = useI18n();
  const actionState = useAppSelector(
    (state) => state.actions.keys[ThActionsKeys.answers],
  );
  const dispatch = useAppDispatch();

  const setOpen = (value: boolean) => {
    dispatch(
      setActionOpen({
        key: ThActionsKeys.answers,
        isOpen: value,
      }),
    );
  };

  return (
    <>
      {variant && variant === ThActionsTriggerVariant.menu ? (
        <StatefulOverflowMenuItem
          label={t("reader.answers.trigger")}
          SVGIcon={AnswersIcon}
          shortcut={preferences.actions.keys[ThActionsKeys.answers].shortcut}
          id={ThActionsKeys.answers}
          onAction={() => setOpen(!actionState?.isOpen)}
        />
      ) : (
        <StatefulActionIcon
          visibility={
            preferences.actions.keys[ThActionsKeys.answers].visibility
          }
          aria-label={t("reader.answers.trigger")}
          placement="bottom"
          tooltipLabel={t("reader.answers.tooltip")}
          onPress={() => setOpen(!actionState?.isOpen)}
        >
          <AnswersIcon aria-hidden="true" focusable="false" />
        </StatefulActionIcon>
      )}
    </>
  );
};
