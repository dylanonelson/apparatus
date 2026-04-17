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

  /**
   * Expands the current text selection in the active iframe to the nearest
   * sentence boundaries. If the selection spans multiple sentences, all
   * overlapping sentences are fully included.
   *
   * A sentence boundary is a period, exclamation mark, or question mark
   * followed by whitespace or end-of-text. Abbreviation-like patterns
   * (single uppercase letter followed by a period, e.g. "Mr.") are skipped.
   *
   * Returns the expanded text, or null if there is no active selection.
   */
  const expandSelectionToSentences = useCallback((): string | null => {
    const frames = navigatorInstance?._cframes ?? [];

    for (const frame of frames ?? []) {
      const frameWindow = extractFrameWindow(frame);
      const selection = frameWindow?.getSelection();
      if (!selection || selection.rangeCount === 0 || selection.isCollapsed) {
        continue;
      }

      const range = selection.getRangeAt(0);
      const selectedText = selection.toString();
      if (!selectedText.trim()) continue;

      // Find the block-level ancestor that contains the full sentence context
      const blockTags = new Set([
        "P", "DIV", "SECTION", "ARTICLE", "BLOCKQUOTE",
        "LI", "TD", "TH", "H1", "H2", "H3", "H4", "H5", "H6",
        "FIGCAPTION", "BODY",
      ]);

      const findBlockAncestor = (node: Node): Element => {
        let current: Node | null = node;
        while (current) {
          if (
            current.nodeType === Node.ELEMENT_NODE &&
            blockTags.has(current.nodeName)
          ) {
            return current as Element;
          }
          current = current.parentNode;
        }
        return frameWindow!.document.body;
      };

      const startBlock = findBlockAncestor(range.startContainer);
      const endBlock = findBlockAncestor(range.endContainer);

      // Get all the text content and build a map of text nodes to character positions
      const rootNode = startBlock.contains(endBlock) ? startBlock : startBlock.parentElement || startBlock;

      const textNodes: { node: Text; start: number }[] = [];
      const walker = frameWindow!.document.createTreeWalker(
        rootNode,
        NodeFilter.SHOW_TEXT,
      );

      let fullText = "";
      let tNode: Text | null;
      while ((tNode = walker.nextNode() as Text | null)) {
        textNodes.push({ node: tNode, start: fullText.length });
        fullText += tNode.textContent || "";
      }

      if (textNodes.length === 0 || !fullText) continue;

      // Find the selection's start and end positions within the full text
      let selStart = -1;
      let selEnd = -1;

      for (const { node, start } of textNodes) {
        if (node === range.startContainer) {
          selStart = start + range.startOffset;
        }
        if (node === range.endContainer) {
          selEnd = start + range.endOffset;
        }
      }

      // If the container is an element (not a text node), we need to find it
      // by child node index
      if (selStart === -1 && range.startContainer.nodeType === Node.ELEMENT_NODE) {
        const childNode = range.startContainer.childNodes[range.startOffset];
        if (childNode) {
          for (const { node, start } of textNodes) {
            if (node === childNode || childNode.contains(node)) {
              selStart = start;
              break;
            }
          }
        }
      }
      if (selEnd === -1 && range.endContainer.nodeType === Node.ELEMENT_NODE) {
        const childNode = range.endContainer.childNodes[range.endOffset - 1];
        if (childNode) {
          for (const { node, start } of textNodes) {
            if (node === childNode || childNode.contains(node)) {
              selEnd = start + (node.textContent?.length || 0);
              break;
            }
          }
        }
      }

      if (selStart === -1 || selEnd === -1) continue;

      // Find sentence boundaries. Sentence-ending punctuation: . ! ?
      // Followed by a space, quote, or end of text.
      // Skip single uppercase letter abbreviations (e.g. "A." "B.")
      const sentenceEndPattern =
        /(?<![A-Z])([.!?])(?=\s|["'\u201C\u201D\u2018\u2019)\]]|$)/g;

      const boundaries: number[] = [0];
      let match: RegExpExecArray | null;
      while ((match = sentenceEndPattern.exec(fullText)) !== null) {
        // The boundary is right after the punctuation mark
        boundaries.push(match.index + 1);
      }
      boundaries.push(fullText.length);

      // Find the sentence start (last boundary before or at selStart)
      let sentenceStart = 0;
      for (const b of boundaries) {
        if (b <= selStart) {
          sentenceStart = b;
        } else {
          break;
        }
      }

      // Find the sentence end (first boundary at or after selEnd)
      let sentenceEnd = fullText.length;
      for (const b of boundaries) {
        if (b >= selEnd) {
          sentenceEnd = b;
          break;
        }
      }

      // Skip leading whitespace in the sentence
      while (sentenceStart < sentenceEnd && /\s/.test(fullText[sentenceStart])) {
        sentenceStart++;
      }

      // Map the character positions back to DOM text nodes
      let newStartNode: Text | null = null;
      let newStartOffset = 0;
      let newEndNode: Text | null = null;
      let newEndOffset = 0;

      for (let i = 0; i < textNodes.length; i++) {
        const { node, start } = textNodes[i];
        const end = start + (node.textContent?.length || 0);

        // Find the node containing sentenceStart
        if (!newStartNode && sentenceStart >= start && sentenceStart < end) {
          newStartNode = node;
          newStartOffset = sentenceStart - start;
        }

        // Find the node containing sentenceEnd
        if (sentenceEnd > start && sentenceEnd <= end) {
          newEndNode = node;
          newEndOffset = sentenceEnd - start;
        }
      }

      // Fallback: use last text node if end wasn't found
      if (!newEndNode && textNodes.length > 0) {
        const last = textNodes[textNodes.length - 1];
        newEndNode = last.node;
        newEndOffset = last.node.textContent?.length || 0;
      }

      if (newStartNode && newEndNode) {
        range.setStart(newStartNode, newStartOffset);
        range.setEnd(newEndNode, newEndOffset);
        selection.removeAllRanges();
        selection.addRange(range);
        return selection.toString().trim();
      }
    }

    return null;
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
    expandSelectionToSentences,
    preferencesEditor: navigatorInstance?.preferencesEditor,
    getSetting,
    submitPreferences,
    getCframes,
    onFXLPositionChange: (cb: (locator: Locator) => void) => {
      FXLPositionChangedCallback = cb;
    },
  };
};
