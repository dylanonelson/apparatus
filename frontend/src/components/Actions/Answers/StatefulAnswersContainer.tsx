"use client";

import { useCallback, useEffect, useRef } from "react";

import { ThActionsKeys } from "@/preferences/models/enums";
import { StatefulActionContainerProps } from "../models/actions";

import answersStyles from "./assets/styles/answers.module.css";

import { StatefulSheetWrapper } from "../../Sheets/StatefulSheetWrapper";

import { useDocking } from "../../Docking/hooks/useDocking";
import { useI18n } from "@/i18n/useI18n";
import { useEpubNavigator } from "@/core/Hooks/Epub/useEpubNavigator";

import { useAppDispatch, useAppSelector } from "@/lib/hooks";
import { setActionOpen } from "@/lib/actionsReducer";
import { useAskAutomaticMutation } from "@/lib/api";

export const StatefulAnswersContainer = ({
  triggerRef,
}: StatefulActionContainerProps) => {
  const { t } = useI18n();

  const actionState = useAppSelector(
    (state) => state.actions.keys[ThActionsKeys.answers],
  );
  const publicationId = useAppSelector(
    (state) => state.publication.publicationId,
  );
  const dispatch = useAppDispatch();

  const { getVisibleText, getSelectionText, currentLocator, currentPositions } =
    useEpubNavigator();

  const [askAutomatic, { data, isLoading, isError, error, reset }] =
    useAskAutomaticMutation();

  const requestMadeRef = useRef(false);

  const docking = useDocking(ThActionsKeys.answers);
  const sheetType = docking.sheetType;

  const setOpen = useCallback(
    (value: boolean) => {
      if (!value) {
        // Reset state when sidebar closes
        requestMadeRef.current = false;
        reset();
      }
      dispatch(
        setActionOpen({
          key: ThActionsKeys.answers,
          isOpen: value,
        }),
      );
    },
    [dispatch, reset],
  );

  // Trigger API call when sidebar opens
  useEffect(() => {
    if (actionState?.isOpen && !requestMadeRef.current && publicationId) {
      requestMadeRef.current = true;

      const locator = currentLocator();
      const positions = currentPositions() || [];
      const visibleText = getVisibleText() || "";
      const selectionText = getSelectionText();

      if (locator) {
        askAutomatic({
          publication_id: publicationId,
          locator: {
            href: locator.href,
            type: locator.type,
            title: locator.title ?? undefined,
            locations: locator.locations
              ? {
                  fragments: locator.locations.fragments ?? undefined,
                  position: locator.locations.position ?? undefined,
                  progression: locator.locations.progression ?? undefined,
                  totalProgression:
                    locator.locations.totalProgression ?? undefined,
                }
              : undefined,
            text: locator.text
              ? {
                  before: locator.text.before ?? undefined,
                  highlight: locator.text.highlight ?? undefined,
                  after: locator.text.after ?? undefined,
                }
              : undefined,
          },
          viewport: {
            positions,
            text: visibleText,
            selection_text: selectionText,
          },
        });
      }
    }
  }, [
    actionState?.isOpen,
    publicationId,
    askAutomatic,
    currentLocator,
    currentPositions,
    getVisibleText,
    getSelectionText,
  ]);

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className={answersStyles.loading}>
          <div className={answersStyles.loadingSpinner} />
          <span>Getting answer...</span>
        </div>
      );
    }

    if (isError) {
      const errorMessage =
        error && "data" in error
          ? String((error.data as { error?: string })?.error || "Unknown error")
          : "Failed to get answer";
      return <div className={answersStyles.error}>{errorMessage}</div>;
    }

    if (data?.answer) {
      return <div className={answersStyles.answer}>{data.answer}</div>;
    }

    return (
      <div className={answersStyles.placeholder}>
        {publicationId
          ? "Open the sidebar to get AI-powered answers about what you're reading"
          : "Loading publication..."}
      </div>
    );
  };

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
        <div className={answersStyles.answersContent}>{renderContent()}</div>
      </StatefulSheetWrapper>
    </>
  );
};
