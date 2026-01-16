import { createSlice, PayloadAction } from "@reduxjs/toolkit";

export interface SelectionRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export interface SelectionReducerState {
  text: string | null;
  rect: SelectionRect | null;
  isVisible: boolean;
}

const initialState: SelectionReducerState = {
  text: null,
  rect: null,
  isVisible: false,
};

export const selectionSlice = createSlice({
  name: "selection",
  initialState,
  reducers: {
    setSelection: (
      state,
      action: PayloadAction<{ text: string; rect: SelectionRect }>,
    ) => {
      state.text = action.payload.text;
      state.rect = action.payload.rect;
      state.isVisible = true;
    },
    clearSelection: (state) => {
      state.text = null;
      state.rect = null;
      state.isVisible = false;
    },
  },
});

export const { setSelection, clearSelection } = selectionSlice.actions;

export default selectionSlice.reducer;
