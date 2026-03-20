"use client";

import React, { useCallback, useEffect, useRef } from "react";

import readerPaginationStyles from "./assets/styles/readerPagination.module.css";

import { ThBreakpoints, ThLayoutUI } from "@/preferences/models/enums";

import { ThFooter } from "@/core/Components/Reader/ThFooter";
import { StatefulReaderProgression } from "./StatefulReaderProgression";
import { ThInteractiveOverlay } from "../core/Components/Reader/ThInteractiveOverlay";
import { StatefulReaderPagination } from "./StatefulReaderPagination";
import { ThPaginationLinkProps } from "@/core/Components/Reader/ThPagination";

import { useEpubNavigator } from "@/core/Hooks/Epub/useEpubNavigator";
import { useFocusWithin } from "react-aria";
import { useI18n } from "@/i18n/useI18n";

import { setHovering } from "@/lib/readerReducer";
import { useAppDispatch, useAppSelector } from "@/lib/hooks";

export const StatefulReaderFooter = ({ layout }: { layout: ThLayoutUI }) => {
  const { t } = useI18n();
  const footerRef = useRef<HTMLDivElement>(null);
  const isImmersive = useAppSelector((state) => state.reader.isImmersive);
  const isHovering = useAppSelector((state) => state.reader.isHovering);
  const hasScrollAffordance = useAppSelector(
    (state) => state.reader.hasScrollAffordance,
  );
  const selectionIsVisible = useAppSelector(
    (state) => state.selection.isVisible,
  );
  const scroll = useAppSelector((state) => state.settings.scroll);
  const isFXL = useAppSelector((state) => state.publication.isFXL);
  const isScroll = scroll && !isFXL;
  const breakpoint = useAppSelector((state) => state.theming.breakpoint);
  const reducedMotion = useAppSelector(
    (state) => state.theming.prefersReducedMotion,
  );
  const timeline = useAppSelector(
    (state) => state.publication.unstableTimeline,
  );

  const dispatch = useAppDispatch();

  const { focusWithinProps } = useFocusWithin({
    onFocusWithin() {
      dispatch(setHovering(true));
    },
    onBlurWithin() {
      dispatch(setHovering(false));
    },
  });

  const setHover = () => {
    if (!hasScrollAffordance) {
      dispatch(setHovering(true));
    }
  };

  const removeHover = () => {
    if (!hasScrollAffordance) {
      dispatch(setHovering(false));
    }
  };

  const { previousLocator, nextLocator, go } = useEpubNavigator();

  const updateLinks = useCallback(() => {
    const links: {
      previous?: ThPaginationLinkProps;
      next?: ThPaginationLinkProps;
    } = {
      previous: undefined,
      next: undefined,
    };

    const previous = previousLocator();
    const next = nextLocator();

    if (previous) {
      links.previous = {
        node:
          breakpoint !== ThBreakpoints.compact &&
          breakpoint !== ThBreakpoints.medium ? (
            <>
              <span className="sr-only">
                {t("reader.navigation.scroll.prevA11yLabel")}
              </span>
              <span className={readerPaginationStyles.paginationLabel}>
                {timeline?.previousItem?.title ||
                  previous.title ||
                  t("reader.navigation.scroll.prevLabel")}
              </span>
            </>
          ) : (
            <>
              <span className={readerPaginationStyles.paginationLabel}>
                {t("reader.navigation.scroll.prevLabel")}
              </span>
            </>
          ),
        onPress: () => go(previous, !reducedMotion, () => {}),
      };
    }

    if (next) {
      links.next = {
        node:
          breakpoint !== ThBreakpoints.compact &&
          breakpoint !== ThBreakpoints.medium ? (
            <>
              <span className="sr-only">
                {t("reader.navigation.scroll.nextA11yLabel")}
              </span>
              <span className={readerPaginationStyles.paginationLabel}>
                {timeline?.nextItem?.title ||
                  next.title ||
                  t("reader.navigation.scroll.nextLabel")}
              </span>
            </>
          ) : (
            <>
              <span className={readerPaginationStyles.paginationLabel}>
                {t("reader.navigation.scroll.nextLabel")}
              </span>
            </>
          ),
        onPress: () => go(next, !reducedMotion, () => {}),
      };
    }

    return links;
  }, [
    go,
    previousLocator,
    nextLocator,
    t,
    timeline,
    breakpoint,
    reducedMotion,
  ]);

  useEffect(() => {
    updateLinks();
  }, [timeline, updateLinks]);

  useEffect(() => {
    // Blur any focused element when entering immersive mode
    if (isImmersive) {
      const focusElement = document.activeElement;
      if (focusElement && footerRef.current?.contains(focusElement)) {
        (focusElement as HTMLElement).blur();
      }
    }
  }, [isImmersive]);

  // Hide the footer when the selection toolbar is visible (it replaces the footer)
  if (selectionIsVisible) {
    return null;
  }

  return (
    <>
      <ThInteractiveOverlay
        id="reader-footer-overlay"
        className="bar-overlay"
        isActive={layout === ThLayoutUI.layered && isImmersive && !isHovering}
        onMouseEnter={setHover}
        onMouseLeave={removeHover}
      />

      <ThFooter
        ref={footerRef}
        id="bottom-bar"
        aria-label={t("reader.app.footer.label")}
        onMouseEnter={setHover}
        onMouseLeave={removeHover}
        {...focusWithinProps}
      >
        {isScroll && !isFXL ? (
          <StatefulReaderPagination
            aria-label={t("reader.navigation.scroll.wrapper")}
            links={updateLinks()}
            compounds={{
              listItem: {
                className: readerPaginationStyles.paginationListItem,
              },
              previousButton: {
                className: readerPaginationStyles.previousButton,
                preventFocusOnPress: true,
              },
              nextButton: {
                className: readerPaginationStyles.nextButton,
                preventFocusOnPress: true,
              },
            }}
          >
            <StatefulReaderProgression
              className={readerPaginationStyles.progression}
            />
          </StatefulReaderPagination>
        ) : (
          <StatefulReaderProgression />
        )}
      </ThFooter>
    </>
  );
};
