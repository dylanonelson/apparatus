"use client";

import { useCallback, useMemo, useRef } from "react";

import { Layout, Link, Locator, Publication } from "@readium/shared";
import {
  EpubNavigator,
  EpubNavigatorListeners,
  EpubPreferences,
  EpubSettings,
  IEpubDefaults,
  IEpubPreferences,
} from "@readium/navigator";

type cbb = (ok: boolean) => void;

// Module scoped, singleton instance of navigator
let navigatorInstance: EpubNavigator | null = null;

export interface EpubNavigatorLoadProps {
  container: HTMLDivElement | null;
  publication: Publication;
  listeners: EpubNavigatorListeners;
  positionsList?: Locator[];
  initialPosition?: Locator;
  preferences?: IEpubPreferences;
  defaults?: IEpubDefaults;
}

export const useEpubNavigator = () => {
  const container = useRef<HTMLDivElement | null>(null);
  const containerParent = useRef<HTMLElement | null>(null);
  const publication = useRef<Publication | null>(null);

  const submitPreferences = useCallback(
    async (preferences: IEpubPreferences) => {
      await navigatorInstance?.submitPreferences(
        new EpubPreferences(preferences),
      );
    },
    [],
  );

  const getSetting = useCallback(
    <K extends keyof EpubSettings>(settingKey: K) => {
      return navigatorInstance?.settings[settingKey] as EpubSettings[K];
    },
    [],
  );

  // [TMP] Working around positionChanged not firing consistently for FXL
  // We’re observing the FXLFramePoolManager spine div element’s style
  // and checking whether its translate3d has changed.
  // Sure IntersectionObserver should be the obvious one to use here,
  // observing iframes instead of the style attribute on the spine element
  // but there’s additional complexity to handle as a spread = 2 iframes
  // And keeping in sync while the FramePool is re-aligning on resize can be suboptimal
  let FXLPositionChangedCallback: ((locator: Locator) => void) | undefined;
  const FXLPositionChanged = useMemo(() => {
    return new MutationObserver((mutationsList: MutationRecord[]) => {
      for (const mutation of mutationsList) {
        const re = /translate3d\(([^)]+)\)/;
        const newVal = (mutation.target as HTMLElement).getAttribute(
          mutation.attributeName as string,
        );
        const oldVal = mutation.oldValue;
        if (newVal?.split(re)[1] !== oldVal?.split(re)[1]) {
          const locator = navigatorInstance?.currentLocator;
          if (locator) {
            FXLPositionChangedCallback?.(locator);
          }
        }
      }
    });
  }, [FXLPositionChangedCallback]);

  const EpubNavigatorLoad = useCallback(
    (config: EpubNavigatorLoadProps, cb: Function) => {
      if (config.container) {
        container.current = config.container;
        containerParent.current = container.current
          ? container.current.parentElement
          : null;

        publication.current = config.publication;

        navigatorInstance = new EpubNavigator(
          config.container,
          config.publication,
          config.listeners,
          config.positionsList,
          config.initialPosition,
          {
            preferences: config.preferences || {},
            defaults: config.defaults || {},
          },
        );

        navigatorInstance.load().then(() => {
          cb();

          if (navigatorInstance?.layout === Layout.fixed) {
            FXLPositionChanged.observe(
              // @ts-ignore
              navigatorInstance?.pool.spineElement as HTMLElement,
              {
                attributeFilter: ["style"],
                attributeOldValue: true,
              },
            );
          }
        });
      }
    },
    [FXLPositionChanged],
  );

  const EpubNavigatorDestroy = useCallback(
    (cb: Function) => {
      cb();

      if (navigatorInstance?.layout === Layout.fixed) {
        FXLPositionChanged.disconnect();
      }
      navigatorInstance?.destroy;
    },
    [FXLPositionChanged],
  );

  const goRight = useCallback((animated: boolean, callback: cbb) => {
    navigatorInstance?.goRight(animated, callback);
  }, []);

  const goLeft = useCallback((animated: boolean, callback: cbb) => {
    navigatorInstance?.goLeft(animated, callback);
  }, []);

  const goBackward = useCallback((animated: boolean, callback: cbb) => {
    navigatorInstance?.goBackward(animated, callback);
  }, []);

  const goForward = useCallback((animated: boolean, callback: cbb) => {
    navigatorInstance?.goForward(animated, callback);
  }, []);

  const goLink = useCallback((link: Link, animated: boolean, callback: cbb) => {
    navigatorInstance?.goLink(link, animated, callback);
  }, []);

  const go = useCallback(
    (locator: Locator, animated: boolean, callback: cbb) => {
      navigatorInstance?.go(locator, animated, callback);
    },
    [],
  );

  const navLayout = useCallback(() => {
    return navigatorInstance?.layout;
  }, []);

  const currentLocator = useCallback(() => {
    return navigatorInstance?.currentLocator;
  }, []);

  const getLocatorAtOffset = useCallback((offset: number) => {
    const readingOrder = navigatorInstance?.publication?.readingOrder;
    if (!readingOrder) return null;

    const currentLocator = navigatorInstance?.currentLocator;
    if (!currentLocator) return null;

    const currentLocatorIndex = readingOrder.findIndexWithHref(
      currentLocator.href,
    );
    if (currentLocatorIndex === -1) return null;

    const newIndex = currentLocatorIndex + offset;
    if (newIndex < 0 || newIndex >= readingOrder.items.length) return null;

    return readingOrder.items[newIndex];
  }, []);

  const previousLocator = useCallback(() => {
    const link = getLocatorAtOffset(-1);
    if (!link) return null;
    return navigatorInstance?.publication?.manifest?.locatorFromLink(link);
  }, [getLocatorAtOffset]);

  const nextLocator = useCallback(() => {
    const link = getLocatorAtOffset(1);
    if (!link) return null;
    return navigatorInstance?.publication?.manifest?.locatorFromLink(link);
  }, [getLocatorAtOffset]);

  const currentPositions = useCallback(() => {
    return navigatorInstance?.viewport?.positions;
  }, []);

  const collectVisibleTextFromFrameDocument = (
    document: Document,
  ): string | null => {
    const documentElement = document.documentElement;
    const minClientLeft = 0;
    const maxClientRight = documentElement.clientWidth;
    // The first line of text overflows the top of the document :shrug:
    const minClientTop = -2;
    const maxClientBottom = documentElement.clientHeight;

    const treeWalker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      null,
    );

    let rangeStart: [Node, number] | null = null;
    let rangeEnd: [Node, number] | null = null;
    while (treeWalker.nextNode()) {
      const currentNode = treeWalker.currentNode as Text;
      for (let i = 0; i < currentNode.length; i += 1) {
        const candidateRange = document.createRange();
        candidateRange.setStart(currentNode, i);
        candidateRange.setEnd(currentNode, i + 1);
        const { bottom, left, right, top } =
          candidateRange.getBoundingClientRect();
        if (
          left > minClientLeft &&
          right < maxClientRight &&
          top > minClientTop &&
          bottom < maxClientBottom
        ) {
          if (rangeStart === null) {
            rangeStart = [currentNode, i];
          }
          rangeEnd = [currentNode, i + 1];
        }
        if (right > maxClientRight || bottom > maxClientBottom) {
          break;
        }
      }
    }

    if (rangeStart && rangeEnd) {
      const resultRange = document.createRange();
      resultRange.setStart(...rangeStart);
      resultRange.setEnd(...rangeEnd);
      return resultRange.toString();
    } else {
      return null;
    }
  };

  const extractFrameWindow = (frame: unknown): Window | null => {
    if (!frame || typeof frame !== "object") return null;
    const maybeWindow = (frame as { window?: Window }).window;
    if (maybeWindow && typeof maybeWindow.document !== "undefined") {
      return maybeWindow;
    }
    const maybeIframeWindow = (frame as { iframe?: { contentWindow?: Window } })
      .iframe?.contentWindow;
    if (
      maybeIframeWindow &&
      typeof maybeIframeWindow.document !== "undefined"
    ) {
      return maybeIframeWindow;
    }
    return null;
  };

  const getVisibleText = useCallback((): string | null => {
    const frames = navigatorInstance?._cframes ?? [];
    const allText: string[] = [];

    for (const frame of frames ?? []) {
      const frameWindow = extractFrameWindow(frame);
      if (!frameWindow?.document?.body) continue;
      const visibleText = collectVisibleTextFromFrameDocument(
        frameWindow.document,
      );
      if (visibleText) {
        allText.push(visibleText);
      }
    }

    const result = allText.join("\n\n");
    return result;
  }, []);

  const getSelectionText = useCallback((): string | null => {
    const frames = navigatorInstance?._cframes ?? [];

    for (const frame of frames ?? []) {
      const frameWindow = extractFrameWindow(frame);
      const selection = frameWindow?.getSelection();
      const selectedText = selection?.toString().trim();
      if (selectedText) {
        return selectedText;
      }
    }

    const selectedText = window.getSelection()?.toString().trim();
    return selectedText || null;
  }, []);

  interface SelectionRectResult {
    top: number;
    left: number;
    width: number;
    height: number;
  }

  const getSelectionRect = useCallback((): SelectionRectResult | null => {
    const frames = navigatorInstance?._cframes ?? [];

    for (const frame of frames ?? []) {
      const frameWindow = extractFrameWindow(frame);
      const selection = frameWindow?.getSelection();
      if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
        const range = selection.getRangeAt(0);
        const rangeRects = range.getClientRects();
        const rangeRect = rangeRects[0];

        // Transform coordinates from iframe to main window
        // Find the iframe element to get its position
        const frameElement = (frame as { iframe?: HTMLIFrameElement })?.iframe;
        if (frameElement) {
          const iframeRect = frameElement.getBoundingClientRect();
          return {
            top: rangeRect.top + iframeRect.top,
            left: rangeRect.left + iframeRect.left,
            width: rangeRect.width,
            height: rangeRect.height,
          };
        }

        // Fallback: return the rect as-is if we can't find the iframe
        return {
          top: rangeRect.top,
          left: rangeRect.left,
          width: rangeRect.width,
          height: rangeRect.height,
        };
      }
    }

    // Check main window selection as fallback
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
      const range = selection.getRangeAt(0);
      const rangeRect = range.getBoundingClientRect();
      return {
        top: rangeRect.top,
        left: rangeRect.left,
        width: rangeRect.width,
        height: rangeRect.height,
      };
    }

    return null;
  }, []);

  const canGoBackward = useCallback(() => {
    return navigatorInstance?.canGoBackward;
  }, []);

  const canGoForward = useCallback(() => {
    return navigatorInstance?.canGoForward;
  }, []);

  const isScrollStart = useCallback(() => {
    return navigatorInstance?.isScrollStart;
  }, []);

  const isScrollEnd = useCallback(() => {
    return navigatorInstance?.isScrollEnd;
  }, []);

  // Warning: this is an internal member that will become private, do not rely on it
  // See https://github.com/edrlab/thorium-web/issues/25
  const getCframes = useCallback(() => {
    return navigatorInstance?._cframes;
  }, []);

  return {
    EpubNavigatorLoad,
    EpubNavigatorDestroy,
    goRight,
    goLeft,
    goBackward,
    goForward,
    goLink,
    go,
    navLayout,
    currentLocator,
    previousLocator,
    nextLocator,
    currentPositions,
    canGoBackward,
    canGoForward,
    isScrollStart,
    isScrollEnd,
    getVisibleText,
    getSelectionText,
    getSelectionRect,
    preferencesEditor: navigatorInstance?.preferencesEditor,
    getSetting,
    submitPreferences,
    getCframes,
    onFXLPositionChange: (cb: (locator: Locator) => void) => {
      FXLPositionChangedCallback = cb;
    },
  };
};
