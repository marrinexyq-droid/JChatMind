import { createContext, useContext, type Dispatch } from "react";

export type PetState = "idle" | "happy" | "think" | "curious" | "excite" | "sleep";

export type PetAction =
  | { type: "SET_STATE"; payload: PetState }
  | { type: "IDLE" }
  | { type: "HAPPY" }
  | { type: "THINK" }
  | { type: "CURIOUS" }
  | { type: "EXCITE" }
  | { type: "SLEEP" }
  | { type: "TOGGLE" };

export interface PetStateValue {
  state: PetState;
  dispatch: Dispatch<PetAction>;
  triggerAction: (action: PetAction) => void;
  morphId: string;
  setMorphId: (id: string) => void;
}

export const PetContext = createContext<PetStateValue | null>(null);

export function usePet(): PetStateValue {
  const context = useContext(PetContext);
  if (!context) {
    throw new Error("usePet must be used within PetProvider");
  }
  return context;
}

export const petActions = {
  setIdle: () => ({ type: "IDLE" as const }),
  setHappy: () => ({ type: "HAPPY" as const }),
  setThink: () => ({ type: "THINK" as const }),
  setCurious: () => ({ type: "CURIOUS" as const }),
  setExcite: () => ({ type: "EXCITE" as const }),
  setSleep: () => ({ type: "SLEEP" as const }),
};
