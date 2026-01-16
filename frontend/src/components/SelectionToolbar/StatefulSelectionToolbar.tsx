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

import { usePreferenceKeys } from "@/preferences/hooks/usePreferenceKeys";
import { usePlugins } from "../Plugins/PluginProvider";
import { useAppSelector } from "@/lib/hooks";

interface SelectionToolbarActionItem {
  key: string;
  Trigger: React.ComponentType<{ variant: ThActionsTriggerVariant }>;
  Target?: React.ComponentType<{ triggerRef: RefObject<HTMLElement | null> }>;
}

export const StatefulSelectionToolbar = () => {
  const { selectionToolbarKeys } = usePreferenceKeys();
  const { actionsComponentsMap } = usePlugins();
  const toolbarRef = useRef<HTMLDivElement>(null);

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

  // Calculate toolbar position based on selection rect
  const toolbarStyle = useMemo(() => {
    if (!selection.rect) return { display: "none" } as React.CSSProperties;
    const { top, left, width, height } = selection.rect;

    // Position the toolbar above the selection, centered horizontally
    const style: React.CSSProperties = {
      position: "fixed",
      top: `${top - 8}px`, // 8px gap above selection
      left: `${left + width / 2}px`,
      transform: "translate(-50%, -100%)",
    };

    if (!selection.isVisible || actionItems.length === 0) {
      // Fully hide when no selection or no actions
      style.display = "none";
    } else if (isAnySheetOpen) {
      // When a sheet is open, hide visually but preserve position for popover
      // positioning. Use visibility/opacity so the ref still has valid dimensions.
      style.visibility = "hidden";
      style.opacity = 0;
      style.pointerEvents = "none";
      style.top = top + height / 2;
      style.transform = "translate(-50%, -50%)";
    }

    return style;
  }, [selection.isVisible, selection.rect, actionItems.length, isAnySheetOpen]);

  return (
    <div
      ref={toolbarRef}
      className={selectionToolbarStyles.toolbar}
      style={toolbarStyle}
      role="toolbar"
      aria-label="Selection actions"
    >
      <div className={selectionToolbarStyles.toolbarContent}>
        {actionItems.map(({ key, Trigger, Target }) => (
          <Fragment key={key}>
            <Trigger variant={ThActionsTriggerVariant.selectionButton} />
            {Target && <Target triggerRef={toolbarRef} />}
          </Fragment>
        ))}
      </div>
      <div className={selectionToolbarStyles.arrow} />
    </div>
  );
};
