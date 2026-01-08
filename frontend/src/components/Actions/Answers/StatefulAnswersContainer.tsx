"use client";

import { useCallback } from "react";

import { ThActionsKeys, ThDockingKeys } from "@/preferences/models/enums";
import { StatefulActionContainerProps } from "../models/actions";

import answersStyles from "./assets/styles/answers.module.css";

import { StatefulSheetWrapper } from "../../Sheets/StatefulSheetWrapper";

import { useDocking } from "../../Docking/hooks/useDocking";
import { useI18n } from "@/i18n/useI18n";

import { useAppDispatch, useAppSelector } from "@/lib/hooks";
import { setActionOpen } from "@/lib/actionsReducer";

export const StatefulAnswersContainer = ({
  triggerRef,
}: StatefulActionContainerProps) => {
  const { t } = useI18n();

  const actionState = useAppSelector(
    (state) => state.actions.keys[ThActionsKeys.answers],
  );
  const dispatch = useAppDispatch();

  const docking = useDocking(ThActionsKeys.answers);
  const sheetType = docking.sheetType;

  const setOpen = useCallback(
    (value: boolean) => {
      dispatch(
        setActionOpen({
          key: ThActionsKeys.answers,
          isOpen: value,
        }),
      );
    },
    [dispatch],
  );

  return (
    <>
      <StatefulSheetWrapper
        sheetType={sheetType}
        sheetProps={{
          id: ThActionsKeys.answers,
          triggerRef: triggerRef,
          heading: t("reader.answers.heading"),
          className: answersStyles.answers,
          placement: "bottom",
          isOpen: actionState?.isOpen || false,
          onOpenChange: setOpen,
          onClosePress: () => setOpen(false),
          docker: docking.getDocker(),
        }}
      >
        <div className={answersStyles.answersContent}>
          <div className={answersStyles.placeholder}>
            {/* Placeholder content - to be implemented */}
            AI Answers will appear here
          </div>
        </div>
      </StatefulSheetWrapper>
    </>
  );
};
