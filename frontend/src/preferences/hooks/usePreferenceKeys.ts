"use client";

import { ThSpacingPresetKeys } from "@/preferences/models/enums";
import {
  defaultSpacingSettingsSubpanel,
  defaultTextSettingsMain,
  defaultTextSettingsSubpanel,
  defaultSpacingSettingsMain,
  defaultSpacingPresetsOrder,
} from "@/preferences/models/const";

import { usePreferences } from "./usePreferences";

export const usePreferenceKeys = () => {
  const { preferences } = usePreferences();

  const reflowActionKeys = preferences.actions.reflowOrder;
  const fxlActionKeys = preferences.actions.fxlOrder;
  const selectionToolbarKeys = preferences.actions.selectionToolbarOrder ?? [];

  const reflowThemeKeys = preferences.theming.themes.reflowOrder;
  const fxlThemeKeys = preferences.theming.themes.fxlOrder;

  const reflowSettingsKeys = preferences.settings.reflowOrder;
  const fxlSettingsKeys = preferences.settings.fxlOrder;

  const mainTextSettingsKeys =
    preferences.settings.text?.main ?? defaultTextSettingsMain;
  const subPanelTextSettingsKeys =
    preferences.settings.text?.subPanel ?? defaultTextSettingsSubpanel;
  const mainSpacingSettingsKeys =
    preferences.settings.spacing?.main ?? defaultSpacingSettingsMain;
  const subPanelSpacingSettingsKeys =
    preferences.settings.spacing?.subPanel ?? defaultSpacingSettingsSubpanel;

  const reflowSpacingPresetKeys =
    preferences.settings.spacing?.presets?.reflowOrder ??
    defaultSpacingPresetsOrder;
  const fxlSpacingPresetKeys: ThSpacingPresetKeys[] = [];

  return {
    reflowActionKeys,
    fxlActionKeys,
    selectionToolbarKeys,
    reflowThemeKeys,
    fxlThemeKeys,
    reflowSettingsKeys,
    fxlSettingsKeys,
    mainTextSettingsKeys,
    subPanelTextSettingsKeys,
    mainSpacingSettingsKeys,
    subPanelSpacingSettingsKeys,
    reflowSpacingPresetKeys,
    fxlSpacingPresetKeys,
  };
};
