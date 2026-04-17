"use client";

import React, {
  Fragment,
  RefObject,
  useCallback,
  useMemo,
  useRef,
} from "react";

import { ThActionsTriggerVariant } from "@/core/Components/Actions/ThActionsBar";
import { useActions } from "@/core/Components/Actions/hooks/useActions";

import selectionToolbarStyles from "./assets/styles/selectionToolbar.module.css";
import ExpandSelectionIcon from "./assets/icons/expand-selection.svg";

import { usePreferenceKeys } from "@/preferences/hooks/usePreferenceKeys";
import { usePlugins } from "../Plugins/PluginProvider";
import { useAppDispatch, useAppSelector } from "@/lib/hooks";
import { useTouchDevice } from "@/hooks/useTouchDevice";
import { useEpubNavigator } from "@/core/Hooks/Epub/useEpubNavigator";
import { setSelection } from "@/lib/selectionReducer";

interface SelectionToolbarActionItem {
  key: string;
  Trigger: React.ComponentType<{ variant: ThActionsTriggerVariant }>;
  Target?: React.ComponentType<{ triggerRef: RefObject<HTMLElement | null> }>;
}

export const StatefulSelectionToolbar = () => {
  const { selectionToolbarKeys } = usePreferenceKeys();
  const { actionsComponentsMap } = usePlugins();
  const toolbarRef = useRef<HTMLDivElement>(null);
  const isTouchDevice = useTouchDevice();
  const { expandSelectionToSentences, getSelectionRect } = useEpubNavigator();
  const dispatch = useAppDispatch();

  const selection = useAppSelector((state) => state.selection);
  const actionsMap = useAppSelector((state) => state.actions.keys);
  const { anyOpen } = useActions(actionsMap);

  // Hide toolbar when any action sheet is open
  const isAnySheetOpen = anyOpen();

  const listActionItems = useCallback((): SelectionToolbarActionItem[] => {
    const actionItems: SelectionToolbarActionItem[] = [];

    if (actionsComponentsMap && Object.keys(actionsComponentsMap).length > 0) {
      selectionToolbarKeys.forEach((key) => {
        if (actionsComponentsMap[key]) {
          actionItems.push({
            key,
            Trigger: actionsComponentsMap[key].Trigger,
            Target: actionsComponentsMap[key].Target,
          });
        } else {
          console.warn(
            `Action key "${key}" not found in the plugin registry for selection toolbar.`,
          );
        }
      });
    }

    return actionItems;
  }, [selectionToolbarKeys, actionsComponentsMap]);

  const actionItems = useMemo(() => listActionItems(), [listActionItems]);

  const isVisible = selection.isVisible && actionItems.length > 0;

  const handleExpandToSentence = useCallback(() => {
    const expandedText = expandSelectionToSentences();
    if (expandedText) {
      const rect = getSelectionRect();
      if (rect) {
        dispatch(setSelection({ text: expandedText, rect }));
      }
    }
  }, [expandSelectionToSentences, getSelectionRect, dispatch]);

  // Calculate toolbar style based on device type
  const toolbarStyle = useMemo(() => {
    if (isTouchDevice) {
      // Touch devices: fixed bottom bar (position handled by CSS class)
      const style: React.CSSProperties = {};

      if (!isVisible) {
        style.display = "none";
      } else if (isAnySheetOpen) {
        style.visibility = "hidden";
        style.opacity = 0;
        style.pointerEvents = "none";
      }

      return style;
    } else {
      // Desktop: floating popover above selection
      if (!selection.rect) return { display: "none" } as React.CSSProperties;
      const { top, left, width, height } = selection.rect;

      const style: React.CSSProperties = {
        position: "fixed",
        top: `${top - 8}px`,
        left: `${left + width / 2}px`,
        transform: "translate(-50%, -100%)",
      };

      if (!isVisible) {
        style.display = "none";
      } else if (isAnySheetOpen) {
        style.visibility = "hidden";
        style.opacity = 0;
        style.pointerEvents = "none";
        style.top = top + height / 2;
        style.transform = "translate(-50%, -50%)";
      }

      return style;
    }
  }, [isTouchDevice, isVisible, selection.rect, isAnySheetOpen]);

  const toolbarClassName = isTouchDevice
    ? selectionToolbarStyles.toolbarTouch
    : selectionToolbarStyles.toolbarDesktop;

  return (
    <div
      ref={toolbarRef}
      className={toolbarClassName}
      style={toolbarStyle}
      role="toolbar"
      aria-label="Selection actions"
    >
      <div className={selectionToolbarStyles.toolbarContent}>
        {isTouchDevice && (
          <button
            type="button"
            onClick={handleExpandToSentence}
            aria-label="Expand selection to sentence"
            title="Expand to sentence"
          >
            <ExpandSelectionIcon aria-hidden="true" focusable="false" />
          </button>
        )}
        {actionItems.map(({ key, Trigger, Target }) => (
          <Fragment key={key}>
            <Trigger variant={ThActionsTriggerVariant.selectionButton} />
            {Target && <Target triggerRef={toolbarRef} />}
          </Fragment>
        ))}
      </div>
      {!isTouchDevice && <div className={selectionToolbarStyles.arrow} />}
    </div>
  );
};
